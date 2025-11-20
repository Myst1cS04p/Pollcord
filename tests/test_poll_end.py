import asyncio
import pytest
from Pollcord import Poll


@pytest.mark.asyncio
async def test_poll_auto_expires():
    ended = False

    async def on_end(poll):
        print("Poll ended callback called")
        nonlocal ended
        ended = True

    poll = Poll(
        channel_id=1,
        message_id=1,
        prompt="Test",
        options=["A", "B"],
        duration=0.00003,
        on_end=on_end,
    )
    poll.start()

    await asyncio.sleep(1)
    assert poll.ended
    assert ended


@pytest.mark.asyncio
async def test_poll_manual_expire():
    ended = False

    async def on_end(poll):
        print("Poll ended callback called")
        nonlocal ended
        ended = True

    poll = Poll(
        channel_id=1,
        message_id=1,
        prompt="Test",
        options=["A", "B"],
        duration=0.1,
        on_end=on_end,
    )
    poll.start()
    await asyncio.sleep(0.01)
    await poll.end()

    assert poll.ended
    assert ended
