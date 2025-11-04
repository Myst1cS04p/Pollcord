import asyncio
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta, timezone
from pollcord.client import PollClient

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


    def __repr__(self):
        return f"<Poll channel_id={self.channel_id} message_id={self.message_id} prompt={self.prompt!r} options={self.options} duration={self.duration} isMultiselect={self.isMultiselect} ended={self.ended}>"

    def start(self):
        """
        Starts the background task to end the poll after the specified duration.
        """
        if not self.ended:
            self.end_task = asyncio.create_task(self._schedule_end())

    async def _schedule_end(self):
        """
        Sleeps for the poll duration then marks it ended and calls the on_end callback.
        """
        print("[Pollcord] Starting poll end scheduler \n" + "Ending in " + str(self.duration*3600) + "s" "\n" + self.__repr__())
        await asyncio.sleep(self.duration * 3600)  # Convert hours to seconds
        print("[Pollcord] Poll duration elapsed, ending poll\n" + self.__repr__())
        if not self.ended:
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
            
    async def end(self, client: PollClient = None):
        """
        Manually ends the poll immediately and calls the on_end callback.
        """
        if not self.ended:
            if client:
                client.end_poll(self)
            self.ended = True
            if self.on_end:
                await self._safe_callback()
            self.end_task.cancel()
    
    
