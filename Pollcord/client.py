from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Callable

import aiohttp

from Pollcord.poll import Poll
from Pollcord.voter import Voter
from Pollcord.error import PollCreationError, PollNotFoundError, PollcordError


class PollClient:
    logger = logging.getLogger("pollcord")
    BASE_URL = "https://discord.com/api/v10"

    def __init__(self, token: str):
        """
        Initializes the PollClient with a bot token for authorization.

        Parameters:
            token (str): Your Discord bot token.
        """
        self.token = token
        self.headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger.info(f"Initialized PollClient: {self!r}")

    def __repr__(self) -> str:
        return f"<PollClient connected={self.session is not None}>"

    async def __aenter__(self) -> "PollClient":
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_poll(
        self,
        channel_id: int,
        question: str,
        options: List[str],
        duration: int = 1,
        isMultiselect: bool = False,
        callback: Optional[Callable] = None,
        max_retries: int = 5,
    ) -> Poll:
        """
        Creates a poll in a Discord channel.

        Parameters:
            channel_id (int): The channel to post the poll in.
            question (str): The poll question.
            options (List[str]): Answer choices (2–10 items).
            duration (int): Poll duration in hours.
            isMultiselect (bool): Allow multiple votes per user.
            callback (Callable): Called when the poll ends.
            max_retries (int): Max retries on rate limit.

        Returns:
            Poll: The created poll object.

        Raises:
            PollCreationError: If validation fails or the API rejects the request.
        """
        if len(options) < 2:
            raise PollCreationError(
                f"At least 2 options are required; got {len(options)}: {options}"
            )
        if len(options) > 10:
            raise PollCreationError(
                f"Maximum 10 options allowed; got {len(options)}: {options}"
            )

        payload = {
            "poll": {
                "question": {"text": question},
                "answers": self._format_options(options),
                "duration": duration,
                "allow_multiselect": isMultiselect,
            }
        }

        url = f"{self.BASE_URL}/channels/{channel_id}/messages"
        self.logger.debug(
            f"Creating poll in channel {channel_id!r}: {question!r} "
            f"options={options} duration={duration}h multiselect={isMultiselect}"
        )

        status, response = await self._request("POST", url, payload=payload, max_retries=max_retries)

        if status not in (200, 201):
            self.logger.error(f"Failed to create poll: {status} - {response}")
            raise PollCreationError(f"Failed to create poll: {status} - {response}")

        self.logger.debug(f"Poll created successfully. Response: {response}")

        poll = Poll(
            channel_id=channel_id,
            message_id=int(response["id"]),
            prompt=question,
            options=options,
            duration=duration,
            isMultiselect=isMultiselect,
            on_end=callback,
        )
        poll.start()
        return poll

    async def get_vote_users(self, poll: Poll) -> List[List[Voter]]:
        """
        Fetches voters for each option in the poll concurrently.

        Returns:
            List[List[Voter]]: A list of voter lists, one per option, in order.
        """
        self.logger.debug(f"Fetching vote users for poll {poll.message_id}")
        tasks = [
            self.fetch_option_users(poll, index)
            for index in range(len(poll.options))
        ]
        return list(await asyncio.gather(*tasks))

    async def get_vote_counts(self, poll: Poll) -> List[int]:
        """
        Fetches the vote count per option concurrently.

        Returns:
            List[int]: Vote counts in option order.
        """
        self.logger.debug(f"Fetching vote counts for poll {poll.message_id}")
        results = await self.get_vote_users(poll)
        return [len(voters) for voters in results]

    async def fetch_option_users(
        self,
        poll: Poll,
        answer_index: int,
        max_retries: int = 5,
    ) -> List[Voter]:
        """
        Fetches voters for a single answer option.

        Parameters:
            poll (Poll): The poll to query.
            answer_index (int): Zero-based index of the answer option.
            max_retries (int): Max retries on rate limit.

        Returns:
            List[Voter]: Users who voted for this option.

        Raises:
            PollNotFoundError: If the poll/channel cannot be found (404).
            PollcordError: On any other API error.
        """
        url = (
            f"{self.BASE_URL}/channels/{poll.channel_id}"
            f"/polls/{poll.message_id}/answers/{answer_index + 1}"
        )
        status, response = await self._request("GET", url, max_retries=max_retries)

        if status == 404:
            self.logger.error(f"Poll not found ({poll.message_id}): {response}")
            raise PollNotFoundError(response, poll=poll)
        elif status != 200:
            self.logger.error(f"Error fetching poll voters ({poll.message_id}): {response}")
            raise PollcordError(response, poll=poll)

        raw_users = response.get("users", [])
        return [Voter.from_dict(u) for u in raw_users]

    async def end_poll(self, poll: Poll, max_retries: int = 5) -> None:
        """
        Ends a poll via the Discord API, then marks it ended locally.

        Parameters:
            poll (Poll): The poll to end.
            max_retries (int): Max retries on rate limit.

        Raises:
            PollNotFoundError: If the poll cannot be found.
            PollcordError: On any other API error.
        """
        url = (
            f"{self.BASE_URL}/channels/{poll.channel_id}"
            f"/polls/{poll.message_id}/expire"
        )
        self.logger.debug(f"Ending poll {poll.message_id} via API")

        status, response = await self._request("POST", url, max_retries=max_retries)

        if status == 404:
            raise PollNotFoundError(f"Poll not found: {status} - {response}", poll=poll)
        elif status not in (200, 204):
            raise PollcordError(f"Failed to end poll: {status} - {response}", poll=poll)

        await poll.end()

    async def close(self) -> None:
        """Manually close the aiohttp session."""
        if self.session and not self.session.closed:
            self.logger.info("Closing PollClient HTTP session")
            await self.session.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        url: str,
        payload: Optional[dict] = None,
        max_retries: int = 5,
    ) -> tuple[int, any]:
        """
        Performs an HTTP request with built-in rate limit handling.

        Parameters:
            method (str): HTTP verb — 'GET' or 'POST'.
            url (str): The endpoint URL.
            payload (dict, optional): JSON body for POST requests.
            max_retries (int): Maximum number of retries after a 429.

        Returns:
            Tuple[int, any]: (status_code, parsed_response)

        Raises:
            RuntimeError: If the session has not been initialised.
            PollcordError: If max retries are exceeded.
        """
        if not self.session:
            raise RuntimeError(
                "PollClient session is not initialised. "
                "Use it as an async context manager: `async with PollClient(...) as client:`"
            )

        self.logger.info(f"{method} {url}")

        for attempt in range(max_retries):
            async with self.session.request(
                method, url, json=payload
            ) as response:
                if response.status == 429:
                    data = await response.json()
                    wait_time = data.get("retry_after", 1.0)
                    self.logger.warning(
                        f"Rate limited (429). Waiting {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                try:
                    data = await response.json()
                except Exception:
                    data = await response.text()

                return response.status, data

        raise PollcordError(
            f"Exceeded maximum retries ({max_retries}) due to rate limiting on {url}"
        )

    @staticmethod
    def _format_options(options: List[str]) -> List[dict]:
        return [
            {"answer_id": i + 1, "poll_media": {"text": str(opt)}}
            for i, opt in enumerate(options)
        ]