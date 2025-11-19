import pytest
from aioresponses import aioresponses
from Pollcord import PollClient, Poll

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
        }
    }

    with aioresponses() as m:
        print(mock_response)
        m.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", payload=mock_response, status=201)

        async with PollClient(token="fake_token") as client:
            poll = await client.create_poll(channel_id=channel_id, question=question, options=options, duration=duration, isMultiselect=isMultiselect)

            assert isinstance(poll, Poll)
            assert poll.channel_id == channel_id
            assert poll.prompt == question
            for i, opt in enumerate(poll.options):
                assert opt == options[i]
            assert poll.duration == duration
            assert poll.isMultiselect == isMultiselect

@pytest.mark.asyncio
async def test_create_poll_failure():
    channel_id = 1234567890
    question = "What's your favorite color?"
    options = ["Red", "Blue", "Green"]

    with aioresponses() as m:
        m.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", status=400, body="Bad request")

        async with PollClient(token="fake_token") as client:
            with pytest.raises(Exception) as excinfo:
                await client.create_poll(channel_id, question, options)
                assert "Failed to create poll" in str(excinfo.value)

@pytest.mark.asyncio
async def test_create_poll_error():
    async with PollClient("fake_token") as client:
        with aioresponses() as mock:
            mock.post(
                "https://discord.com/api/v10/channels/123/polls",
                status=400,
                body="Bad request"
            )

            with pytest.raises(Exception):  # ideally PollCreationError
                await client.create_poll(123, "Bad poll", ["X", "Y"])
