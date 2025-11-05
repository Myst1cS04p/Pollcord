import asyncio
import pytest   
from Pollcord import Poll, PollClient, PollNotFoundError, PollcordError
from aioresponses import aioresponses

@pytest.fixture
def poll():
    """A simple fake Poll object for testing."""
    return Poll(
        channel_id=12345,
        message_id=99999,
        prompt="Favorite color?",
        options=["Red", "Blue", "Green"],
        duration=1,
        on_end=None
    )

@pytest.mark.asyncio
async def test_fetch_option_users_success(poll):
    url = f"https://discord.com/api/v10/channels/{poll.channel_id}/polls/{poll.message_id}/answers/1"
    mock_users = {"users": [{"id": "1"}, {"id": "2"}]}

    with aioresponses() as m:
        m.get(url, status=200, payload=mock_users)

        async with PollClient(token="fake_token") as client:
            users = await client.fetch_option_users(poll, 0)

    assert users == [{"id": "1"}, {"id": "2"}]
    
@pytest.mark.asyncio
async def test_fetch_option_users_not_found(poll):
    url = f"https://discord.com/api/v10/channels/{poll.channel_id}/polls/{poll.message_id}/answers/1"

    with aioresponses() as m:
        m.get(url, status=404, body="Not Found")

        async with PollClient(token="fake_token") as client:
            with pytest.raises(PollNotFoundError):
                await client.fetch_option_users(poll, 0)
                
@pytest.mark.asyncio
async def test_get_vote_users_success(poll):
    base = f"https://discord.com/api/v10/channels/{poll.channel_id}/polls/{poll.message_id}"
    responses = [
        {"users": [{"id": "1"}]},        # Red
        {"users": [{"id": "2"}, {"id": "3"}]},  # Blue
        {"users": []},                   # Green
    ]

    with aioresponses() as m:
        for i, resp in enumerate(responses):
            m.get(f"{base}/answers/{i+1}", status=200, payload=resp)

        async with PollClient(token="fake_token") as client:
            users_per_option = await client.get_vote_users(poll)

    assert users_per_option == [
        ["1"],
        ["2", "3"],
        []
    ]

@pytest.mark.asyncio
async def test_get_vote_counts_success(poll):
    base = f"https://discord.com/api/v10/channels/{poll.channel_id}/polls/{poll.message_id}"
    responses = [
        {"users": [{"id": "1"}]},             # 1 vote
        {"users": [{"id": "2"}, {"id": "3"}]},  # 2 votes
        {"users": []},                        # 0 votes
    ]

    with aioresponses() as m:
        for i, resp in enumerate(responses):
            m.get(f"{base}/answers/{i+1}", status=200, payload=resp)

        async with PollClient(token="fake_token") as client:
            counts = await client.get_vote_counts(poll)

    assert counts == [1, 2, 0]


@pytest.mark.asyncio
async def test_get_vote_users_handles_error(poll, caplog):
    base = f"https://discord.com/api/v10/channels/{poll.channel_id}/polls/{poll.message_id}"

    with aioresponses() as m:
        # First call succeeds, second fails
        m.get(f"{base}/answers/1", status=200, payload={"users": [{"id": "1"}]})
        m.get(f"{base}/answers/2", status=500, body="Server error")
        m.get(f"{base}/answers/3", status=200, payload={"users": []})

        async with PollClient(token="fake_token") as client:
            with pytest.raises(PollcordError):
                users_per_option = await client.get_vote_users(poll)

    assert "Error while fetching poll" in caplog.text
