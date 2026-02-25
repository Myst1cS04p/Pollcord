import asyncio
import pytest
from unittest.mock import patch
from aioresponses import aioresponses
from Pollcord import PollClient, Poll
from Pollcord.error import PollcordError


@pytest.fixture
def poll():
    return Poll(
        channel_id=12345,
        message_id=99999,
        prompt="Rate limit test",
        options=["A", "B", "C"],
        duration=1,
        on_end=None,
    )


@pytest.mark.asyncio
async def test_rate_limit_retries_and_succeeds(poll):
    """A 429 response should be retried and ultimately succeed."""
    url = (
        f"https://discord.com/api/v10/channels/{poll.channel_id}"
        f"/polls/{poll.message_id}/answers/1"
    )
    success_payload = {
        "users": [{"id": "1", "username": "alice", "discriminator": "0"}]
    }

    with aioresponses() as m:
        # First call: rate limited
        m.get(url, status=429, payload={"retry_after": 0.01})
        # Second call: success
        m.get(url, status=200, payload=success_payload)

        async with PollClient(token="fake_token") as client:
            voters = await client.fetch_option_users(poll, 0)

    assert len(voters) == 1
    assert voters[0].username == "alice"


@pytest.mark.asyncio
async def test_rate_limit_exhausts_retries(poll):
    """Exceeding max_retries on 429 should raise PollcordError."""
    url = (
        f"https://discord.com/api/v10/channels/{poll.channel_id}"
        f"/polls/{poll.message_id}/answers/1"
    )

    with aioresponses() as m:
        # Always rate limited
        for _ in range(3):
            m.get(url, status=429, payload={"retry_after": 0.01})

        async with PollClient(token="fake_token") as client:
            with pytest.raises(PollcordError, match="Exceeded maximum retries"):
                await client.fetch_option_users(poll, 0, max_retries=3)


@pytest.mark.asyncio
async def test_get_vote_users_fetches_concurrently(poll):
    """get_vote_users should fire all option requests concurrently via gather."""
    base = (
        f"https://discord.com/api/v10/channels/{poll.channel_id}"
        f"/polls/{poll.message_id}"
    )

    call_order = []

    async def mock_fetch(p, index, **kwargs):
        call_order.append(index)
        await asyncio.sleep(0)  # yield to event loop
        return []

    async with PollClient(token="fake_token") as client:
        with patch.object(client, "fetch_option_users", side_effect=mock_fetch):
            await client.get_vote_users(poll)

    # All three options should have been requested
    assert sorted(call_order) == [0, 1, 2]


@pytest.mark.asyncio
async def test_get_vote_counts_matches_user_counts(poll):
    """get_vote_counts should return lengths matching get_vote_users results."""
    base = (
        f"https://discord.com/api/v10/channels/{poll.channel_id}"
        f"/polls/{poll.message_id}"
    )
    responses = [
        {
            "users": [
                {"id": "1", "username": "a", "discriminator": "0"},
                {"id": "2", "username": "b", "discriminator": "0"},
            ]
        },
        {"users": [{"id": "3", "username": "c", "discriminator": "0"}]},
        {"users": []},
    ]

    with aioresponses() as m:
        for i, resp in enumerate(responses):
            m.get(f"{base}/answers/{i + 1}", status=200, payload=resp)

        async with PollClient(token="fake_token") as client:
            counts = await client.get_vote_counts(poll)

    assert counts == [2, 1, 0]


@pytest.mark.asyncio
async def test_rate_limit_multiple_consecutive_429s(poll):
    """Multiple consecutive 429s should each be respected before eventual success."""
    url = (
        f"https://discord.com/api/v10/channels/{poll.channel_id}"
        f"/polls/{poll.message_id}/answers/1"
    )
    success_payload = {
        "users": [{"id": "1", "username": "alice", "discriminator": "0"}]
    }

    with aioresponses() as m:
        m.get(url, status=429, payload={"retry_after": 0.01})
        m.get(url, status=429, payload={"retry_after": 0.01})
        m.get(url, status=200, payload=success_payload)

        async with PollClient(token="fake_token") as client:
            voters = await client.fetch_option_users(poll, 0, max_retries=5)

    assert len(voters) == 1
