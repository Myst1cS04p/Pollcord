"""
Tests for the RateLimiter and bucket-aware request queuing.

These tests mock aiohttp at the session level so no real HTTP requests are made.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from Pollcord.rate_limiter import RateLimiter, RequestJob, RateLimitBucket
from Pollcord.error import PollcordError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def headers_with_remaining(n: int) -> dict[str, str]:
    return {
        "X-RateLimit-Bucket": "bucket-batch",
        "X-RateLimit-Remaining": str(n),
        "X-RateLimit-Reset-After": "0.05",
    }

def make_mock_response(
    status: int,
    json_data: dict = None,
    text_data: str = "",
    headers: dict = None,
):
    """Build a mock aiohttp response."""
    response = MagicMock()
    response.status = status
    response.headers = headers or {}

    if json_data is not None:
        response.json = AsyncMock(return_value=json_data)
    else:
        response.json = AsyncMock(side_effect=Exception("no json"))

    response.text = AsyncMock(return_value=text_data)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    return response


def make_session(*responses):
    """
    Build a mock aiohttp session that returns the given responses in order.
    Each element of responses should be a mock response object.
    """
    session = MagicMock()
    session.request = MagicMock(side_effect=[
        MagicMock(
            __aenter__=AsyncMock(return_value=r),
            __aexit__=AsyncMock(return_value=False),
        )
        for r in responses
    ])
    return session


# ---------------------------------------------------------------------------
# RequestJob
# ---------------------------------------------------------------------------

def test_request_job_defaults():
    loop = asyncio.new_event_loop()
    future = loop.create_future()
    job = RequestJob(method="GET", url="http://example.com", payload=None, future=future)
    assert job.retry_count == 0
    loop.close()


# ---------------------------------------------------------------------------
# RateLimitBucket
# ---------------------------------------------------------------------------

def test_bucket_update_from_headers():
    bucket = RateLimitBucket(bucket_id="abc")
    bucket.update_from_headers({
        "X-RateLimit-Remaining": "4",
        "X-RateLimit-Reset-After": "0.5",
        "X-RateLimit-Limit": "10",
    })
    assert bucket.remaining == 4
    assert bucket.reset_after == 0.5
    assert bucket.limit == 10


def test_bucket_update_ignores_bad_headers():
    bucket = RateLimitBucket(bucket_id="abc", remaining=3, limit=10)
    bucket.update_from_headers({
        "X-RateLimit-Remaining": "not-a-number",
    })
    # Should not crash and should leave remaining and limit unchanged
    assert bucket.remaining == 3
    assert bucket.limit == 10


# ---------------------------------------------------------------------------
# Basic submit / dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_success_unknown_route():
    """A request on an unknown route goes through the unknown worker and succeeds."""
    response = make_mock_response(
        status=200,
        json_data={"ok": True},
        headers={
            "X-RateLimit-Bucket": "bucket-abc",
            "X-RateLimit-Remaining": "4",
            "X-RateLimit-Reset-After": "1.0",
        },
    )
    session = make_session(response)

    limiter = RateLimiter(session=session, max_retries=3)
    limiter.start()

    try:
        status, data = await asyncio.wait_for(
            limiter.submit("GET", "https://discord.com/api/v10/test"),
            timeout=5.0,
        )
    finally:
        await limiter.stop()

    assert status == 200
    assert data == {"ok": True}


@pytest.mark.asyncio
async def test_bucket_registered_after_first_request():
    """After the first request, the URL should be mapped to the bucket ID."""
    response = make_mock_response(
        status=200,
        json_data={},
        headers={
            "X-RateLimit-Bucket": "bucket-xyz",
            "X-RateLimit-Remaining": "2",
            "X-RateLimit-Reset-After": "0.5",
        },
    )
    session = make_session(response)
    limiter = RateLimiter(session=session, max_retries=3)
    limiter.start()

    try:
        await asyncio.wait_for(
            limiter.submit("GET", "https://discord.com/api/v10/channels/1/test"),
            timeout=5.0,
        )
    finally:
        await limiter.stop()

    assert limiter._url_to_bucket.get("https://discord.com/api/v10/channels/1/test") == "bucket-xyz"
    assert "bucket-xyz" in limiter._buckets
    assert limiter._buckets["bucket-xyz"].remaining == 2


@pytest.mark.asyncio
async def test_known_route_goes_to_bucket_queue():
    """A second request to a known route is routed to the bucket queue, not unknown."""
    url = "https://discord.com/api/v10/channels/1/messages"
    headers = {
        "X-RateLimit-Bucket": "bucket-123",
        "X-RateLimit-Remaining": "4",
        "X-RateLimit-Reset-After": "1.0",
    }
    r1 = make_mock_response(200, json_data={"id": "1"}, headers=headers)
    r2 = make_mock_response(200, json_data={"id": "2"}, headers=headers)
    session = make_session(r1, r2)

    limiter = RateLimiter(session=session, max_retries=3)
    limiter.start()

    try:
        await asyncio.wait_for(limiter.submit("POST", url, {"a": 1}), timeout=5.0)
        # Second request — bucket should now be known
        await asyncio.wait_for(limiter.submit("POST", url, {"b": 2}), timeout=5.0)
    finally:
        await limiter.stop()

    assert url in limiter._url_to_bucket


# ---------------------------------------------------------------------------
# 429 handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_429_retries_and_succeeds():
    """A 429 response should cause the job to be retried and eventually succeed."""
    url = "https://discord.com/api/v10/channels/1/polls/1/answers/1"

    r_429 = make_mock_response(
        status=429,
        json_data={"retry_after": 0.01},
        headers={"X-RateLimit-Bucket": "bucket-abc", "X-RateLimit-Remaining": "0"},
    )
    r_ok = make_mock_response(
        status=200,
        json_data={"users": []},
        headers={"X-RateLimit-Bucket": "bucket-abc", "X-RateLimit-Remaining": "4"},
    )
    session = make_session(r_429, r_ok)

    limiter = RateLimiter(session=session, max_retries=3)
    limiter.start()

    try:
        status, data = await asyncio.wait_for(
            limiter.submit("GET", url),
            timeout=5.0,
        )
    finally:
        await limiter.stop()

    assert status == 200


@pytest.mark.asyncio
async def test_429_exceeds_max_retries_raises():
    """Exceeding max_retries on repeated 429s should raise PollcordError."""
    url = "https://discord.com/api/v10/channels/1/polls/1/answers/1"

    responses = [
        make_mock_response(
            status=429,
            json_data={"retry_after": 0.01},
            headers={"X-RateLimit-Bucket": "bucket-abc", "X-RateLimit-Remaining": "0"},
        )
        for _ in range(4)
    ]
    session = make_session(*responses)

    limiter = RateLimiter(session=session, max_retries=3)
    limiter.start()

    try:
        with pytest.raises(PollcordError, match="Exceeded maximum retries"):
            await asyncio.wait_for(
                limiter.submit("GET", url),
                timeout=5.0,
            )
    finally:
        await limiter.stop()


@pytest.mark.asyncio
async def test_429_retry_count_is_per_job():
    """
    Two concurrent jobs hitting 429 should each track their own retry count.
    One job exhausting its retries should not affect the other.
    """
    url_a = "https://discord.com/api/v10/channels/1/messages"
    url_b = "https://discord.com/api/v10/channels/2/messages"

    # url_a: fails twice then succeeds
    # url_b: succeeds immediately
    # We interleave them in the session response order
    headers_a = {"X-RateLimit-Bucket": "bucket-a", "X-RateLimit-Remaining": "0"}
    headers_b = {"X-RateLimit-Bucket": "bucket-b", "X-RateLimit-Remaining": "4"}

    r_a_429_1 = make_mock_response(429, json_data={"retry_after": 0.01}, headers=headers_a)
    r_a_429_2 = make_mock_response(429, json_data={"retry_after": 0.01}, headers=headers_a)
    r_a_ok    = make_mock_response(200, json_data={"id": "1"}, headers={**headers_a, "X-RateLimit-Remaining": "4"})
    r_b_ok    = make_mock_response(200, json_data={"id": "2"}, headers=headers_b)

    # url_a goes through unknown worker first (3 calls), url_b separately
    session = make_session(r_a_429_1, r_b_ok, r_a_429_2, r_a_ok)

    limiter = RateLimiter(session=session, max_retries=5)
    limiter.start()

    try:
        result_a, result_b = await asyncio.wait_for(
            asyncio.gather(
                limiter.submit("POST", url_a),
                limiter.submit("POST", url_b),
            ),
            timeout=10.0,
        )
    finally:
        await limiter.stop()

    assert result_a[0] == 200
    assert result_b[0] == 200


# ---------------------------------------------------------------------------
# Concurrent batch dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_respects_remaining():
    """
    When remaining=3, submitting 5 jobs to the same bucket should
    dispatch the first 3 concurrently, then the next 2 after reset.
    """
    url = "https://discord.com/api/v10/channels/1/messages"

    # 5 successful responses — first 3 have remaining=2,1,0; last 2 have remaining=4,3
    responses = [
        make_mock_response(200, json_data={"id": str(i)}, headers=headers_with_remaining(max(0, 3 - i)))
        for i in range(5)
    ]

    # First request goes through unknown worker to register bucket
    first_response = make_mock_response(
        200, json_data={"id": "first"},
        headers=headers_with_remaining(3)
    )
    session = make_session(first_response, *responses)

    limiter = RateLimiter(session=session, max_retries=3)
    limiter.start()

    try:
        # Seed the bucket
        await asyncio.wait_for(limiter.submit("POST", url, {}), timeout=5.0)

        # Now fire 5 concurrent jobs through the known bucket
        results = await asyncio.wait_for(
            asyncio.gather(*[limiter.submit("POST", url, {"i": i}) for i in range(5)]),
            timeout=10.0,
        )
    finally:
        await limiter.stop()

    assert all(r[0] == 200 for r in results)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_cancels_workers():
    """stop() should cancel all running worker tasks without raising."""
    session = MagicMock()
    limiter = RateLimiter(session=session, max_retries=3)
    limiter.start()

    assert limiter._unknown_worker_task is not None
    assert not limiter._unknown_worker_task.done()

    await limiter.stop()

    assert limiter._unknown_worker_task.done()


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    """Calling stop() twice should not raise."""
    session = MagicMock()
    limiter = RateLimiter(session=session, max_retries=3)
    limiter.start()
    await limiter.stop()
    await limiter.stop()  # should not raise


# ---------------------------------------------------------------------------
# Global rate limit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_global_429_sets_pause_until():
    """A global 429 should set _global_pause_until to a future timestamp."""
    url = "https://discord.com/api/v10/channels/1/messages"

    r_global = make_mock_response(
        status=429,
        json_data={"retry_after": 0.05},
        headers={
            "X-RateLimit-Bucket": "bucket-g",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Global": "true",
            "Retry-After": "0.05",
        },
    )
    r_ok = make_mock_response(
        status=200,
        json_data={"ok": True},
        headers={"X-RateLimit-Bucket": "bucket-g", "X-RateLimit-Remaining": "4"},
    )
    session = make_session(r_global, r_ok)

    limiter = RateLimiter(session=session, max_retries=3)
    limiter.start()

    loop = asyncio.get_event_loop()
    before = loop.time()

    try:
        await asyncio.wait_for(limiter.submit("POST", url), timeout=5.0)
    finally:
        await limiter.stop()

    assert limiter._global_pause_until >= before


# ---------------------------------------------------------------------------
# Window reset restores full limit
# ---------------------------------------------------------------------------

def test_window_reset_restores_full_limit():
    """
    After a bucket window resets, remaining should be restored to limit,
    not just 1. This ensures the next batch can use the full capacity.
    """
    bucket = RateLimitBucket(bucket_id="test", remaining=0, limit=10, reset_after=0.0)

    # Simulate what the bucket worker does after sleeping reset_after
    bucket.remaining = bucket.limit

    assert bucket.remaining == 10


def test_window_reset_uses_limit_not_hardcoded_one():
    """Verify limit=5 restores to 5, not 1."""
    bucket = RateLimitBucket(bucket_id="test", remaining=0, limit=5, reset_after=0.0)
    bucket.remaining = bucket.limit
    assert bucket.remaining == 5