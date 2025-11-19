from __future__ import annotations  # allows forward references in type hints
import asyncio
from typing import List, Optional, Callable
from datetime import datetime, timedelta, timezone
import logging

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
            f"<(Poll Object) Channel ID = {self.channel_id}, Message ID = {self.message_id}\n "
            f"Prompt = {self.prompt!r}, Options = {self.options}, Duration = {self.duration}h\n "
            f"Start Time = {self.start_time}, Elapsed Time = {datetime.now(timezone.utc) - self.start_time}, End Time = {self.end_time}"
            f"Multiselect = {self.isMultiselect}, Ended = {self.ended}\n>"
            
        )

    def start(self):
        """
        Starts the background task to end the poll after the specified duration.
        """
        if not self.ended:
            self.logger.debug(f"Poll started: {self}")
            loop = asyncio.get_running_loop()
            self.end_task = loop.create_task(self._schedule_end())

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

    async def end(self):
        """
        Marks the poll as ended locally and triggers the callback.
        This does NOT interact with the Discord API. Call PollClient.close_poll(poll) to end the poll.
        """
        if self.ended:
            return

        self.ended = True

        # cancel scheduler if running
        if hasattr(self, "end_task"):
            self.end_task.cancel()

        if self.on_end:
            await self._safe_callback()