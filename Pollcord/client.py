import aiohttp
from typing import List
from Pollcord.poll import Poll
from Pollcord.error import PollCreationError, PollNotFoundError, PollcordError
import logging
import asyncio


class PollClient:
    logger = logging.getLogger("pollcord") 
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
        self.logger.info("Initialized PollClient instance: \n" + str(self))
    
    def __repr__(self):
        return f"<PollClient connection {self.session is not None}>"
    
    async def __aenter__(self):
        """
        Initializes the aiohttp session with proper headers when entering async context.
        """
        self.session = aiohttp.ClientSession(headers=self.headers)
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
        
        self.logger.debug(f"Attempting to create poll\nchannel id: {channel_id}, question: {question}, options: {options}, duration: {duration}, {"MultiSelect" if isMultiselect else "Not multiselect"}, callback: {callback}")

        # Send POST request to Discord API to create the poll
        url = f"{self.BASE_URL}/channels/{channel_id}/messages"
        status, response = await self.__post_request(url, payload=payload)
        
        
        if status != 200 and status != 201:
            self.logger.error(f"Failed to create poll: {status} - {response}")
            raise PollCreationError(f"Failed to create poll: {status} - {response}")
        self.logger.debug(f"Successfully created poll. \nAPI response: {response}")


        # Create and start a local Poll object
        poll = Poll(
            channel_id=channel_id,
            message_id=response["id"],
            prompt=question,
            options=options,
            duration=duration,
            on_end=callback
        )
        self.logger.debug(f"Poll object created: {poll}")
        poll.start()  # Schedule auto-expiry
        return poll

    async def get_vote_users(self, poll: Poll):
        """
        Fetches user IDs for each option in the poll.

        Returns:
            - List of lists of user IDs per option.
        """
        self.logger.debug("Getting user votes")
        results = []
        for index in range(len(poll.options)):
            users = await self.fetch_option_users(poll, index)
            results.append([u for u in users])
        return results

    async def get_vote_counts(self, poll: Poll):
        """
        Fetches the number of votes per option in the poll.

        Returns:
            - List of integers, each representing vote count for that option.
        """
        self.logger.debug("Counting user votes")
        
        counts = []
        for index in range(len(poll.options)):
            users = await self.fetch_option_users(poll, index)
            counts.append(len(users))
        return counts

    async def fetch_option_users(self, poll: Poll, answer_id: int, max_retries: int = 5):
        """ Internal method to get users who voted for a specific answer option. 
        Parameters: 
            - poll (Poll): The poll to get the answer of
            - answer_id (int): Index of the answer option. 
            - max_retries(optional) (int): Maximum number of retries in case of rate limiting
        Returns: 
            - List of user objects (dicts) who voted for this option. """
        
        url = f"{self.BASE_URL}/channels/{poll.channel_id}/polls/{poll.message_id}/answers/{answer_id + 1}"
        status, response = await self.__get_request(url)
        
        if status == 404:
            raise PollNotFoundError(response, poll=poll)
        elif status != 200:
            text = await response
            raise PollcordError(text, poll=poll)

        data = response
        return data.get("users", [])


    async def end_poll(self, poll: Poll):
        """
        Ends a poll early by expiring it via the Discord API.

        Also sets the poll as ended locally and runs the callback.
        """
        
        url = f"{self.BASE_URL}/channels/{poll.channel_id}/polls/{poll.message_id}/expire"
        self.logger.debug(f"Attempting to terminate a poll({poll})\nurl: {url}")
        status, response = await self.__post_request(url)
        
        if status == 404:
            raise PollNotFoundError(f"Could not find poll: {status} - {response}")
        elif status != 200 and status != 204:
            text = await text()
            self.logger.error(f"Failed to end poll({poll})\nstatus code: {status} \nmessage: {text}")
            raise PollcordError(f"Failed to end poll: {status} - {text}", poll=poll)
        
        await poll.end()

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

    async def __get_request(self, url:str, max_retries:int=5):
        self.logger.info(f"Sending request to {url}\nmax retries: {max_retries}")
        retries = 0
        while retries < max_retries:
            async with self.session.get(url) as r:
                if r.status == 429: 
                    wait_time = r.json()["retry_after"] # exponential backoff
                    self.logger.warning(f"\nRate limited(Status Code 429).\n Waiting {wait_time}s before retry ({retries+1}/{max_retries})\nServer Response: {r.content}.")
                    await asyncio.sleep(wait_time)
                    retries += 1
                    continue
                else:
                    return r.status, await r.json()
                
        raise PollcordError("Exceeded maximum retries due to rate limiting.")
    
    async def __post_request(self, url:str, payload=None, max_retries:int=5):
        retries = 0
        while retries < max_retries:
            async with self.session.post(url, json=None if not payload else payload) as r:
                if r.status == 429: 
                    wait_time = r.json()["retry_after"] # exponential backoff
                    self.logger.warning(f"\nRate limited(Status Code 429).\n Waiting {wait_time}s before retry ({retries+1}/{max_retries})\nServer Response: {r.content}.")
                    await asyncio.sleep(wait_time)
                    retries += 1
                    continue
                else:
                    return r.status, await r.json()
                
        raise PollcordError("Exceeded maximum retries due to rate limiting.")

    async def close(self):
        """
        Manually close the aiohttp session, if needed.
        """
        self.logger.info("Closing PollClient HTTP session")
        if self.session and not self.session.closed:
            await self.session.close()
