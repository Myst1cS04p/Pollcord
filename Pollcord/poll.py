from __future__ import annotations  # allows forward references in type hints
import asyncio
from typing import List, Dict, Optional, Callable, TYPE_CHECKING
from datetime import datetime, timedelta, timezone
import logging

if TYPE_CHECKING:
    from Pollcord.client import PollClient  # only imported for type checking

class Poll:   
    logger = logging.getLogger("pollcord") 

    def __init__(
        self,
        channel_id: int,
        message_id: int,
        prompt: str,
        options: List[str],
        duration: int = 1,
        isMultiselect: bool = False,
        on_end: Optional[Callable[['Poll'], None]] = None
    ):
        """
        Represents a local poll instance, with logic for auto-expiration and callbacks.
        
        :param channel_id (int): The channel in which the poll exists
        :param message_id (int): The message ID of the poll
        :param prompt (str): The question asked in the poll
        :param options (List(str)): A list of options provided to the user in the poll. Length of the list should be between 2-10.
        :param duration (int): The duration in hours of the poll (Discord API specifies hours)
        :param isMultiSelect (bool): If True a poll will be generated where users can vote on more than 1 option at a time
        :param on_end (Callable): A callback for when the poll ends
        """
        self.channel_id = channel_id
        self.message_id = message_id
        self.prompt = prompt
        self.options = options
        self.start_time = datetime.now(timezone.utc)
        self.end_time = self.start_time + timedelta(hours=duration)
        self.on_end = on_end
        self.duration = duration
        self.isMultiselect = isMultiselect
        self.ended = False

    def __repr__(self):
        return (
            f"<Poll channel_id={self.channel_id} message_id={self.message_id} "
            f"prompt={self.prompt!r} options={self.options} duration={self.duration} "
            f"isMultiselect={self.isMultiselect} ended={self.ended}>"
        )

    def start(self):
        """
        Starts the background task to end the poll after the specified duration.
        """
        if not self.ended:
            self.logger.debug(f"Poll started: {self}")
            self.end_task = asyncio.create_task(self._schedule_end())

    async def _schedule_end(self):
        """
        Sleeps for the poll duration then marks it ended and calls the on_end callback.
        """
        self.logger.debug(
            f"Starting poll end scheduler (ending in {self.duration * 3600}s): {self}"
        )
        await asyncio.sleep(self.duration * 3600)
        self.logger.debug(f"Poll duration elapsed, ending poll: {self}")

        if not self.ended:
            self.ended = True
            if self.on_end:
                await self._safe_callback()

    async def _safe_callback(self):
        """
        Safely executes the on_end callback with error handling.
        """
        try:
            if asyncio.iscoroutinefunction(self.on_end):
                await self.on_end(self)
            else:
                self.on_end(self)
        except Exception as e:
            self.logger.exception(f"Error in on_end callback: {e}")

    async def end(self, client: Optional["PollClient"] = None):
        """
        Manually calls the on_end callback.
        Poll.end() does NOT end the poll. Use Poll.end(PollClient) to end the poll, or PollClient.end_poll(Poll)
        """
        if not self.ended:
            if client:
                await client.end_poll(self)  # note: await added if end_poll is async
            self.ended = True
            if self.on_end:
                await self._safe_callback()
            if hasattr(self, "end_task"):
                self.end_task.cancel()
