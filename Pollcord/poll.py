import asyncio
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta, timezone

class Poll:    
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

        Parameters:
            - channel_id (int): The Discord channel ID.
            - message_id (int): The Discord message ID (of the poll).
            - prompt (str): The poll question text.
            - options (List[str]): Answer choices.
            - duration (int): Duration in hours before poll expires.
            - isMultiselect (bool): Whether multiple options can be selected.
            - on_end (Callable): Optional callback when the poll ends.
        """

        self.channel_id = channel_id
        self.message_id = message_id
        self.prompt = prompt
        self.options = options

        # Track start and end times
        self.start_time = datetime.now(timezone.utc)
        self.end_time = self.start_time + timedelta(hours=duration)

        self.on_end = on_end
        self.duration = duration
        self.isMultiselect = isMultiselect
        self.ended = False

    def start(self):
        """
        Starts the background task to end the poll after the specified duration.
        """
        if not self.ended:
            asyncio.create_task(self._schedule_end())

    async def _schedule_end(self):
        """
        Sleeps for the poll duration then marks it ended and calls the on_end callback.
        """
        await asyncio.sleep(self.duration * 3600)  # Convert hours to seconds
        self.ended = True
        if self.on_end:
            await self._safe_callback()

    async def _safe_callback(self):
        """
        Safely executes the on_end callback with error handling.

        Supports both sync and async functions.
        """
        try:
            if asyncio.iscoroutinefunction(self.on_end):
                await self.on_end(self)
            else:
                self.on_end(self)
        except Exception as e:
            print(f"[Pollcord] Error in on_end callback: {e}")
