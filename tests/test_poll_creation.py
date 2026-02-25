import pytest
from unittest.mock import patch
from aioresponses import aioresponses
from Pollcord import PollClient, Poll
from Pollcord.error import PollCreationError


@pytest.mark.asyncio
async def test_create_poll_success():
    channel_id = 1234567890
    question = "What's your favorite color?"
    options = ["Red", "Blue", "Green"]
    duration = 2
    isMultiselect = False

    mock_response = {
        "id": 9876543210,
        "channel_id": str(channel_id),
        "poll": {
            "question": {"text": question},
            "answers": [{"text": opt} for opt in options],
            "duration": duration,
            "allow_multiselect": isMultiselect,
        },
    }

    with aioresponses() as m:
        m.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            payload=mock_response,
            status=201,
        )

        async with PollClient(token="fake_token") as client:
            poll = await client.create_poll(
                channel_id=channel_id,
                question=question,
                options=options,
                duration=duration,
                isMultiselect=isMultiselect,
            )

            assert isinstance(poll, Poll)
            assert poll.channel_id == channel_id
            assert poll.prompt == question
            assert poll.options == options
            assert poll.duration == duration
            assert poll.isMultiselect == isMultiselect


@pytest.mark.asyncio
async def test_create_poll_schedules_expiry():
    """Poll.start() should be called after successful creation."""
    channel_id = 1234567890
    mock_response = {
        "id": 9876543210,
        "channel_id": str(channel_id),
        "poll": {
            "question": {"text": "Test?"},
            "answers": [],
            "duration": 1,
            "allow_multiselect": False,
        },
    }

    with aioresponses() as m:
        m.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            payload=mock_response,
            status=201,
        )

        async with PollClient(token="fake_token") as client:
            with patch.object(Poll, "start") as mock_start:
                poll = await client.create_poll(
                    channel_id=channel_id,
                    question="Test?",
                    options=["Yes", "No"],
                )
                mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_create_poll_too_few_options():
    """Fewer than 2 options should raise PollCreationError before any API call."""
    async with PollClient(token="fake_token") as client:
        with pytest.raises(PollCreationError, match="At least 2 options"):
            await client.create_poll(
                channel_id=123,
                question="Solo option?",
                options=["Only one"],
            )


@pytest.mark.asyncio
async def test_create_poll_too_many_options():
    """More than 10 options should raise PollCreationError before any API call."""
    async with PollClient(token="fake_token") as client:
        with pytest.raises(PollCreationError, match="Maximum 10 options"):
            await client.create_poll(
                channel_id=123,
                question="Too many?",
                options=[str(i) for i in range(11)],
            )


@pytest.mark.asyncio
async def test_create_poll_exactly_two_options():
    """2 options should be accepted (lower boundary)."""
    channel_id = 123
    mock_response = {
        "id": 1,
        "channel_id": str(channel_id),
        "poll": {
            "question": {"text": "Binary?"},
            "answers": [],
            "duration": 1,
            "allow_multiselect": False,
        },
    }

    with aioresponses() as m:
        m.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            payload=mock_response,
            status=201,
        )

        async with PollClient(token="fake_token") as client:
            poll = await client.create_poll(
                channel_id=channel_id,
                question="Binary?",
                options=["Yes", "No"],
            )
            assert len(poll.options) == 2


@pytest.mark.asyncio
async def test_create_poll_exactly_ten_options():
    """10 options should be accepted (upper boundary)."""
    channel_id = 123
    options = [str(i) for i in range(10)]
    mock_response = {
        "id": 1,
        "channel_id": str(channel_id),
        "poll": {
            "question": {"text": "Ten?"},
            "answers": [],
            "duration": 1,
            "allow_multiselect": False,
        },
    }

    with aioresponses() as m:
        m.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            payload=mock_response,
            status=201,
        )

        async with PollClient(token="fake_token") as client:
            poll = await client.create_poll(
                channel_id=channel_id,
                question="Ten?",
                options=options,
            )
            assert len(poll.options) == 10


@pytest.mark.asyncio
async def test_create_poll_api_failure():
    """A non-2xx API response should raise PollCreationError."""
    channel_id = 1234567890

    with aioresponses() as m:
        m.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            status=400,
            body="Bad request",
        )

        async with PollClient(token="fake_token") as client:
            with pytest.raises(PollCreationError, match="Failed to create poll"):
                await client.create_poll(channel_id, "Bad poll?", ["A", "B"])
