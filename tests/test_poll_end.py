import asyncio
import pytest
from Pollcord import Poll


@pytest.mark.asyncio
async def test_poll_auto_expires():
    """Poll should mark itself ended and fire the callback after its duration."""
    ended = False

    async def on_end(poll):
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
async def test_poll_manual_end():
    """Manually ending a poll should mark it ended and fire the callback."""
    ended = False

    async def on_end(poll):
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


@pytest.mark.asyncio
async def test_callback_receives_correct_poll():
    """The on_end callback should receive the exact Poll instance."""
    received_poll = None

    async def on_end(poll):
        nonlocal received_poll
        received_poll = poll

    original_poll = Poll(
        channel_id=42,
        message_id=99,
        prompt="Callback test",
        options=["Yes", "No"],
        duration=0.00003,
        on_end=on_end,
    )
    original_poll.start()

    await asyncio.sleep(1)

    assert received_poll is original_poll
    assert received_poll.channel_id == 42
    assert received_poll.message_id == 99
    assert received_poll.prompt == "Callback test"


@pytest.mark.asyncio
async def test_end_twice_fires_callback_once():
    """Calling end() a second time should be a no-op — callback fires exactly once."""
    call_count = 0

    async def on_end(poll):
        nonlocal call_count
        call_count += 1

    poll = Poll(
        channel_id=1,
        message_id=1,
        prompt="Double end test",
        options=["A", "B"],
        duration=1,
        on_end=on_end,
    )
    poll.start()

    await poll.end()
    await poll.end()

    assert call_count == 1
    assert poll.ended


@pytest.mark.asyncio
async def test_callback_exception_does_not_crash_poll():
    """An exception raised inside on_end should not propagate or leave poll in a bad state."""

    async def bad_callback(poll):
        raise ValueError("Intentional error in callback")

    poll = Poll(
        channel_id=1,
        message_id=1,
        prompt="Exception test",
        options=["A", "B"],
        duration=1,
        on_end=bad_callback,
    )
    poll.start()

    # Should not raise
    await poll.end()

    assert poll.ended


@pytest.mark.asyncio
async def test_sync_callback_is_supported():
    """A synchronous (non-async) on_end callback should also be called correctly."""
    called_with = []

    def sync_callback(poll):
        called_with.append(poll)

    poll = Poll(
        channel_id=1,
        message_id=1,
        prompt="Sync callback test",
        options=["A", "B"],
        duration=1,
        on_end=sync_callback,
    )
    poll.start()
    await poll.end()

    assert len(called_with) == 1
    assert called_with[0] is poll


@pytest.mark.asyncio
async def test_no_callback_end_is_safe():
    """Ending a poll with no callback set should not raise."""
    poll = Poll(
        channel_id=1,
        message_id=1,
        prompt="No callback",
        options=["A", "B"],
        duration=1,
        on_end=None,
    )
    poll.start()
    await poll.end()

    assert poll.ended
