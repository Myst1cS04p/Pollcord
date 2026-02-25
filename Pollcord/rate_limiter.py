from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from Pollcord.error import PollcordError

logger = logging.getLogger("pollcord.ratelimiter")


# ---------------------------------------------------------------------------
# Request job
# ---------------------------------------------------------------------------

@dataclass
class RequestJob:
    """
    A single HTTP request waiting to be dispatched.

    Attributes:
        method:      HTTP verb ('GET' or 'POST').
        url:         Full endpoint URL.
        payload:     JSON body for POST requests, or None.
        future:      Resolved with (status, data) on success, or an exception.
        retry_count: How many times this specific job has been retried after a 429.
    """
    method: str
    url: str
    payload: Optional[dict]
    future: asyncio.Future
    retry_count: int = 0


# ---------------------------------------------------------------------------
# Per-bucket state
# ---------------------------------------------------------------------------

@dataclass
class RateLimitBucket:
    """
    Tracks the rate limit state for a single Discord bucket.

    Attributes:
        bucket_id:   The opaque hash Discord sends in X-RateLimit-Bucket.
        remaining:   Requests remaining in the current window.
        reset_after: Seconds until the window resets.
        lock:        Ensures only one coroutine updates bucket state at a time.
        queue:       Pending jobs routed to this bucket.
        worker_task: The background coroutine draining this bucket's queue.
    """
    bucket_id: str
    remaining: int = 1
    reset_after: float = 0.0
    limit: int = 1          # total requests allowed per window (X-RateLimit-Limit)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    worker_task: Optional[asyncio.Task] = field(default=None, compare=False)

    def update_from_headers(self, headers: dict) -> None:
        """Update bucket state from Discord response headers."""
        try:
            self.remaining = int(headers.get("X-RateLimit-Remaining", self.remaining))
            self.reset_after = float(headers.get("X-RateLimit-Reset-After", 0.0))
            self.limit = int(headers.get("X-RateLimit-Limit", self.limit))
        except (ValueError, TypeError):
            pass


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Manages all HTTP traffic through Discord's rate limit system.

    Each Discord rate limit bucket gets its own queue and worker coroutine.
    The first request to an unknown route is sent solo to discover its bucket,
    then subsequent requests to that route are dispatched concurrently up to
    the bucket's remaining limit.

    Retry logic lives here, not in the caller. Each RequestJob tracks its own
    retry_count independently — a 429 on one job does not consume retries on
    any other job.
    """

    def __init__(self, session: Any, max_retries: int = 5):
        """
        Parameters:
            session:     An active aiohttp.ClientSession.
            max_retries: Maximum retries per individual request job before
                         raising PollcordError.
        """
        self._session = session
        self._max_retries = max_retries

        # Maps URL -> bucket_id (populated after first request to each route)
        self._url_to_bucket: Dict[str, str] = {}

        # Maps bucket_id -> RateLimitBucket
        self._buckets: Dict[str, RateLimitBucket] = {}

        # Holds jobs whose route has no known bucket yet.
        # These are dispatched one at a time to safely discover the bucket.
        self._unknown_queue: asyncio.Queue = asyncio.Queue()
        self._unknown_worker_task: Optional[asyncio.Task] = None

        # Set to a future timestamp when a global rate limit is hit.
        # Bucket workers check this before dispatching.
        self._global_pause_until: float = 0.0

        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the unknown-route worker. Call this when the session opens."""
        self._running = True
        self._unknown_worker_task = asyncio.get_event_loop().create_task(
            self._unknown_worker(), name="ratelimiter:unknown"
        )
        logger.debug("RateLimiter started")

    async def stop(self) -> None:
        """Drain queues and shut down all workers. Call this when the session closes."""
        self._running = False

        # Cancel the unknown worker
        if self._unknown_worker_task and not self._unknown_worker_task.done():
            self._unknown_worker_task.cancel()
            try:
                await self._unknown_worker_task
            except asyncio.CancelledError:
                pass

        # Cancel all bucket workers
        for bucket in self._buckets.values():
            if bucket.worker_task and not bucket.worker_task.done():
                bucket.worker_task.cancel()
                try:
                    await bucket.worker_task
                except asyncio.CancelledError:
                    pass

        logger.debug("RateLimiter stopped")

    # ------------------------------------------------------------------
    # Public submission
    # ------------------------------------------------------------------

    async def submit(
        self,
        method: str,
        url: str,
        payload: Optional[dict] = None,
    ) -> tuple[int, Any]:
        """
        Submit a request and await its result.

        Routes the job to either the known bucket queue or the unknown queue
        depending on whether we have seen this URL before.

        Parameters:
            method:  HTTP verb.
            url:     Full endpoint URL.
            payload: JSON body for POST requests.

        Returns:
            Tuple of (status_code, response_data).

        Raises:
            PollcordError: If max retries are exceeded for this job.
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        job = RequestJob(method=method, url=url, payload=payload, future=future)

        bucket_id = self._url_to_bucket.get(url)
        if bucket_id and bucket_id in self._buckets:
            logger.debug(f"Routing {method} {url} to known bucket {bucket_id!r}")
            await self._buckets[bucket_id].queue.put(job)
        else:
            logger.debug(f"Routing {method} {url} to unknown queue (first contact)")
            await self._unknown_queue.put(job)

        return await future

    # ------------------------------------------------------------------
    # Unknown-route worker
    # ------------------------------------------------------------------

    async def _unknown_worker(self) -> None:
        """
        Processes jobs whose bucket is not yet known, one at a time.

        After each response, registers the bucket and hands off to the
        appropriate bucket worker for all future requests to that route.
        """
        while self._running:
            try:
                job: RequestJob = await asyncio.wait_for(
                    self._unknown_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            await self._dispatch_single(job, register_bucket=True)
            self._unknown_queue.task_done()

    # ------------------------------------------------------------------
    # Bucket workers
    # ------------------------------------------------------------------

    def _ensure_bucket_worker(self, bucket: RateLimitBucket) -> None:
        """Start a worker for this bucket if one isn't already running."""
        if bucket.worker_task is None or bucket.worker_task.done():
            bucket.worker_task = asyncio.get_event_loop().create_task(
                self._bucket_worker(bucket),
                name=f"ratelimiter:bucket:{bucket.bucket_id}"
            )

    async def _bucket_worker(self, bucket: RateLimitBucket) -> None:
        """
        Drains a single bucket's queue with proper concurrency.

        Fires up to `bucket.remaining` jobs concurrently. If remaining hits 0,
        waits for `reset_after` seconds before continuing.
        """
        while self._running:
            try:
                # Block until at least one job is available
                first_job: RequestJob = await asyncio.wait_for(
                    bucket.queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            # Respect global rate limit pause before dispatching anything
            now = asyncio.get_event_loop().time()
            if self._global_pause_until > now:
                wait = self._global_pause_until - now
                logger.debug(
                    f"Bucket {bucket.bucket_id!r} waiting {wait:.2f}s for global pause"
                )
                await asyncio.sleep(wait)

            async with bucket.lock:
                # Collect a batch: the first job plus however many more
                # we can send within the remaining limit
                batch = [first_job]
                slots = max(0, bucket.remaining - 1)

                while slots > 0 and not bucket.queue.empty():
                    try:
                        batch.append(bucket.queue.get_nowait())
                        slots -= 1
                    except asyncio.QueueEmpty:
                        break

                logger.debug(
                    f"Bucket {bucket.bucket_id!r}: dispatching batch of "
                    f"{len(batch)} (remaining={bucket.remaining})"
                )

                # Fire the batch concurrently
                await asyncio.gather(
                    *[self._dispatch_single(job, bucket=bucket) for job in batch]
                )

                for _ in batch:
                    bucket.queue.task_done()

                # If the window is exhausted, wait for reset
                if bucket.remaining == 0 and bucket.reset_after > 0:
                    logger.debug(
                        f"Bucket {bucket.bucket_id!r} exhausted. "
                        f"Waiting {bucket.reset_after}s for reset."
                    )
                    await asyncio.sleep(bucket.reset_after)
                    bucket.remaining = bucket.limit  # restore full window

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    async def _dispatch_single(
        self,
        job: RequestJob,
        bucket: Optional[RateLimitBucket] = None,
        register_bucket: bool = False,
    ) -> None:
        """
        Executes one HTTP request and resolves the job's future.

        On 429: increments job.retry_count, sleeps retry_after, then requeues.
        On success: resolves the future with (status, data).
        On fatal error: resolves the future with a PollcordError exception.

        Parameters:
            job:              The request to execute.
            bucket:           Known bucket for this job, if any.
            register_bucket:  If True, register the bucket from response headers.
        """
        if job.retry_count >= self._max_retries:
            job.future.set_exception(
                PollcordError(
                    f"Exceeded maximum retries ({self._max_retries}) for "
                    f"{job.method} {job.url}"
                )
            )
            return

        try:
            async with self._session.request(
                job.method, job.url, json=job.payload
            ) as response:
                headers = dict(response.headers)

                # Register or update bucket from headers
                incoming_bucket_id = headers.get("X-RateLimit-Bucket")
                if incoming_bucket_id:
                    if register_bucket or job.url not in self._url_to_bucket:
                        self._register_bucket(job.url, incoming_bucket_id, headers)
                    elif bucket:
                        bucket.update_from_headers(headers)

                if response.status == 429:
                    try:
                        data = await response.json()
                        retry_after = float(data.get("retry_after", 1.0))
                    except Exception:
                        retry_after = 1.0

                    is_global = headers.get("X-RateLimit-Global", "false").lower() == "true"
                    scope = "global" if is_global else f"bucket {incoming_bucket_id!r}"
                    job.retry_count += 1

                    logger.warning(
                        f"429 on {job.method} {job.url} ({scope}). "
                        f"retry_after={retry_after}s "
                        f"(attempt {job.retry_count}/{self._max_retries})"
                    )

                    if is_global:
                        # Global rate limit: pause ALL bucket workers by holding
                        # their locks simultaneously would be complex, so instead
                        # we sleep here (blocking this coroutine) and let the
                        # bucket workers naturally drain while waiting for jobs.
                        logger.warning(
                            f"Global rate limit hit. Pausing {retry_after}s."
                        )
                        self._global_pause_until = asyncio.get_event_loop().time() + retry_after

                    await asyncio.sleep(retry_after)

                    # Requeue to the appropriate destination
                    target_bucket_id = self._url_to_bucket.get(job.url)
                    if target_bucket_id and target_bucket_id in self._buckets:
                        await self._buckets[target_bucket_id].queue.put(job)
                    else:
                        await self._unknown_queue.put(job)
                    return

                # Success path — parse and resolve
                try:
                    data = await response.json()
                except Exception:
                    data = await response.text()

                if not job.future.done():
                    job.future.set_result((response.status, data))

        except Exception as exc:
            if not job.future.done():
                job.future.set_exception(exc)

    # ------------------------------------------------------------------
    # Bucket registration
    # ------------------------------------------------------------------

    def _register_bucket(
        self, url: str, bucket_id: str, headers: dict
    ) -> None:
        """
        Register or update a bucket from response headers.

        If the bucket is new, creates it and starts its worker.
        """
        self._url_to_bucket[url] = bucket_id

        if bucket_id not in self._buckets:
            bucket = RateLimitBucket(bucket_id=bucket_id)
            bucket.update_from_headers(headers)
            self._buckets[bucket_id] = bucket
            self._ensure_bucket_worker(bucket)
            logger.debug(
                f"Registered new bucket {bucket_id!r} for {url} "
                f"(remaining={bucket.remaining}, reset_after={bucket.reset_after}s)"
            )
        else:
            self._buckets[bucket_id].update_from_headers(headers)