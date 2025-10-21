import aiohttp
from typing import List
from pollcord.poll import Poll
from pollcord.error import PollCreationError, PollNotFoundError, PollcordError

class PollClient:
    BASE_URL = "https://discord.com/api/v10"

    def __init__(self, token: str):
        """
        Initializes the PollClient with a bot token for authorization.
        """
        self.token = token
        self.headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json"
        }
        self.session = None  # HTTP session will be created on entry

    async def __aenter__(self):
        """
        Initializes the aiohttp session with proper headers when entering async context.
        """
        self.session = await aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """
        Closes the aiohttp session when exiting async context.
        """
        if self.session and not self.session.closed:
            await self.session.close()

    async def create_poll(self, channel_id: int, question: str, options: List[str],
                          duration: int = 1, isMultiselect: bool = False, callback=None) -> Poll:
        """
        Creates a poll in a specified Discord channel.

        Parameters:
            - channel_id (int): The channel to post the poll in.
            - question (str): The poll prompt/question.
            - options (List[str]): List of answer choices.
            - duration (int): How long the poll should last (in hours).
            - isMultiselect (bool): Whether users can vote for more than one option.
            - callback (Callable): Function to be called when poll ends.

        Returns:
            - A Poll object representing the created poll.
        """
        payload = {
            "poll": {
                "question": {"text": question},
                "answers": self.format_options(options),
                "duration": duration,
                "allow_multiselect": isMultiselect,
            }
        }

        # Send POST request to Discord API to create the poll
        async with self.session.post(f"{self.BASE_URL}/channels/{channel_id}/polls", json=payload) as r:
            if r.status != 200 and r.status != 201:
                text = await r.text()
                raise PollCreationError(f"Failed to create poll: {r.status} - {text}")
            data = await r.json()

        # Create and start a local Poll object
        poll = Poll(
            channel_id=channel_id,
            message_id=data["message_id"],
            prompt=question,
            options=options,
            duration=duration,
            on_end=callback
        )
        poll.start()  # Schedule auto-expiry
        return poll

    async def get_vote_users(self, poll: Poll):
        """
        Fetches user IDs for each option in the poll.

        Returns:
            - List of lists of user IDs per option.
        """
        results = []
        for index in range(len(poll.options)):
            users = await self.fetch_option_users(poll, index)
            results.append([u["id"] for u in users])
        return results

    async def get_vote_counts(self, poll: Poll):
        """
        Fetches the number of votes per option in the poll.

        Returns:
            - List of integers, each representing vote count for that option.
        """
        counts = []
        for index in range(len(poll.options)):
            users = await self.fetch_option_users(poll, index)
            counts.append(len(users))
        return counts

    async def fetch_option_users(self, poll: Poll, answer_id: int):
        """
        Internal method to get users who voted for a specific answer option.

        Parameters:
            - answer_id (int): Index of the answer option.

        Returns:
            - List of user objects (dicts) who voted for this option.
        """
        url = f"{self.BASE_URL}/channels/{poll.channel_id}/polls/{poll.message_id}/answers/{answer_id + 1}"
        async with self.session.get(url) as r:
            if r.status != 200:
                text = await r.text()
                raise PollNotFoundError(text, poll=poll)
            data = await r.json()
            return data.get("users", [])

    async def end_poll(self, poll: Poll):
        """
        Ends a poll early by expiring it via the Discord API.

        Also sets the poll as ended locally and runs the callback.
        """
        url = f"{self.BASE_URL}/channels/{poll.channel_id}/polls/{poll.message_id}/expire"
        async with self.session.post(url) as r:
            if r.status != 200 and r.status != 204:
                text = await r.text()
                raise PollcordError(f"Failed to end poll: {r.status} - {text}", poll=poll)
        poll.ended = True
        if poll.on_end:
            await poll._safe_callback()

    @staticmethod
    def format_options(options: List[str]):
        """
        Formats a list of option strings into Discord's poll answer format.

        Returns:
            - List of formatted option dictionaries.
        """
        return [
            {"answer_id": str(i + 1), "poll_media": {"text": str(opt)}}
            for i, opt in enumerate(options)
        ]

    async def close(self):
        """
        Manually close the aiohttp session, if needed.
        """
        await self.session.close()
