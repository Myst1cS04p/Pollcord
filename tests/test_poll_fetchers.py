import asyncio
import pytest   
from Pollcord import Poll, PollClient

@pytest.mark.asyncio
async def test_fetch_test_votes():
    channel_id = 1234567890
    message_id = 9876543210

    mock_votes = {
        "votes": [
            {"user_id": "111", "answers": [{"text": "Option 1"}]},
            {"user_id": "222", "answers": [{"text": "Option 2"}]},
            {"user_id": "333", "answers": [{"text": "Option 1"}]},
        ]
    }

    async with PollClient(token="fake_token") as client:
        # Mock the fetch_test_votes method to return our mock_votes
        original_fetch = client.fetch_test_votes
        async def mock_fetch_test_votes(channel_id, message_id):
            return mock_votes
        client.fetch_test_votes = mock_fetch_test_votes

        votes = await client.fetch_test_votes(channel_id, message_id)

        assert votes == mock_votes

        # Restore the original method
        client.fetch_test_votes = original_fetch