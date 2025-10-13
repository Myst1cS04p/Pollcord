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
        Initializes a new Poll object.

        Parameters:
            channel_id (int): The Discord channel ID where the poll was posted.
            message_id (int): The Discord message ID of the poll message.
            prompt (str): The poll question.
            options (List[str]): List of possible options.
            duration (Optional[int]): Poll duration in seconds. Defaults to 1.
            isMultiselect (bool, optional): Defines whether the poll allows the selection of multiple options. Defaults to False.
            on_end (Optional[Callable[[Poll], None]]): Callback function to run when the poll ends.
        """
        
        self.channel_id = channel_id
        self.message_id = message_id
        self.prompt = prompt
        self.options = options
        
        self.start_time = datetime.now(timezone.utc)
        self.end_time = self.start_time + timedelta(hours=duration)
        
        self.votes: Dict[int, List[int]] = {} # answer(option) id -> list of user_ids
        
        self.on_end = on_end
        
        self.duration = duration
        self.isMultiselect = isMultiselect
        self.ended = False
        
    def start(self):
        if not self.ended:
            asyncio.create_task(self._schedule_end())
            
    async def _schedule_end(self):
        await asyncio.sleep(self.duration * 3600)  # assuming duration is in hours
        self.ended = True
        if self.on_end:
            await self._safe_callback()
            
    async def _safe_callback(self):
        try:
            if asyncio.iscoroutinefunction(self.on_end):
                await self.on_end(self)
            else:
                self.on_end(self)
        except Exception as e:
            print(f"[Pollcord] Error in on_end callback: {e}")
            