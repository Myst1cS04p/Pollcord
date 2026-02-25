import pytest
from Pollcord import Poll, PollClient, PollNotFoundError, PollcordError
from Pollcord.voter import Voter
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
        on_end=None,
    )


@pytest.mark.asyncio
async def test_fetch_option_users_success(poll):
    url = f"https://discord.com/api/v10/channels/{poll.channel_id}/polls/{poll.message_id}/answers/1"
    mock_users = {
        "users": [
            {"id": "1", "username": "alice", "discriminator": "0"},
            {"id": "2", "username": "bob", "discriminator": "0"},
        ]
    }

    with aioresponses() as m:
        m.get(url, status=200, payload=mock_users)

        async with PollClient(token="fake_token") as client:
            voters = await client.fetch_option_users(poll, 0)

    assert len(voters) == 2
    assert all(isinstance(v, Voter) for v in voters)
    assert voters[0].id == 1
    assert voters[0].username == "alice"
    assert voters[1].id == 2
    assert voters[1].username == "bob"


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
        {"users": [{"id": "1", "username": "alice", "discriminator": "0"}]},
        {
            "users": [
                {"id": "2", "username": "bob", "discriminator": "0"},
                {"id": "3", "username": "carol", "discriminator": "0"},
            ]
        },
        {"users": []},
    ]

    with aioresponses() as m:
        for i, resp in enumerate(responses):
            m.get(f"{base}/answers/{i + 1}", status=200, payload=resp)

        async with PollClient(token="fake_token") as client:
            results = await client.get_vote_users(poll)

    assert len(results) == 3
    assert all(isinstance(v, Voter) for v in results[0])
    assert results[0][0].username == "alice"
    assert len(results[1]) == 2
    assert len(results[2]) == 0


@pytest.mark.asyncio
async def test_get_vote_counts_success(poll):
    base = f"https://discord.com/api/v10/channels/{poll.channel_id}/polls/{poll.message_id}"
    responses = [
        {"users": [{"id": "1", "username": "alice", "discriminator": "0"}]},
        {
            "users": [
                {"id": "2", "username": "bob", "discriminator": "0"},
                {"id": "3", "username": "carol", "discriminator": "0"},
            ]
        },
        {"users": []},
    ]

    with aioresponses() as m:
        for i, resp in enumerate(responses):
            m.get(f"{base}/answers/{i + 1}", status=200, payload=resp)

        async with PollClient(token="fake_token") as client:
            counts = await client.get_vote_counts(poll)

    assert counts == [1, 2, 0]


@pytest.mark.asyncio
async def test_get_vote_users_handles_error(poll, caplog):
    base = f"https://discord.com/api/v10/channels/{poll.channel_id}/polls/{poll.message_id}"

    with aioresponses() as m:
        m.get(
            f"{base}/answers/1",
            status=200,
            payload={"users": [{"id": "1", "username": "alice", "discriminator": "0"}]},
        )
        m.get(f"{base}/answers/2", status=500, body="Server error")
        m.get(f"{base}/answers/3", status=200, payload={"users": []})

        async with PollClient(token="fake_token") as client:
            with pytest.raises(PollcordError):
                await client.get_vote_users(poll)


@pytest.mark.asyncio
async def test_voter_display_name_fallback():
    """Voter.display_name falls back to username when global_name is absent."""
    v = Voter(id=1, username="testuser")
    assert v.display_name == "testuser"


@pytest.mark.asyncio
async def test_voter_display_name_global():
    """Voter.display_name prefers global_name when present."""
    v = Voter(id=1, username="testuser", global_name="Test User")
    assert v.display_name == "Test User"


@pytest.mark.asyncio
async def test_voter_from_dict_minimal():
    """Voter.from_dict handles a minimal API response."""
    v = Voter.from_dict({"id": "42", "username": "minimal"})
    assert v.id == 42
    assert v.username == "minimal"
    assert v.discriminator == "0"
    assert v.avatar is None
    assert v.bot is False
