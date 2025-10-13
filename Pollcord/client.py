import requests
from typing import List
from poll import Poll

class PollClient:
    """
    PollClient provides an interface for interacting with Discord's poll API, allowing creation and management of polls within Discord channels.
    Attributes:
        BASE_URL (str): The base URL for Discord's API.
    Methods:
        __init__(token: str):
            Initializes the PollClient with the provided Discord bot token.
        create_poll(channel_id: int, question: str, options: list[str], duration: int = 1, isMultiselect: bool = False, callback = None):
            Creates a poll in the specified Discord channel with the given question, options, duration, and multiselect setting. Optionally accepts a callback to be executed when the poll ends.
        get_vote_users(poll: Poll):
            Retrieves the list of user IDs who voted for each option in the specified poll.
        get_vote_counts(poll: Poll):
            Returns the number of votes for each option in the specified poll.
        fetch_option_users(poll: Poll, answer_id: int):
            Fetches the list of users who voted for a specific answer option in a poll.
        format_options(options: List[str]):
            Helper method to format poll options for the API request.
    """

    
    BASE_URL = "https://discord.com/api/v10"

    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json"
        }
        
    async def create_poll(self, channel_id: int, question: str, options: list[str], duration: int = 1, isMultiselect: bool = False, callback = None):
        """
        Sends a request to discord, and prays that a poll gets created.

        Args:
            channel_id (int): The Discord channel ID where the poll should be posted.
            question (str): The poll question.
            options (list[str]): List of answers.
            duration (int, optional): The time in hours of the poll. Defaults to 1.
            isMultiselect (bool, optional): Defines whether the poll allows the selection of multiple options. Defaults to False.

        Returns:
            Poll: The created Poll object
        """
        payload = {
        "poll": {
            "question": {
                "text": question  # The poll's question
            },
            "answers": self.format_options(options),  # Poll options
            "duration": duration,  # Poll duration (in hours)
            "allow_multiselect": isMultiselect,  # Whether multiple selections are allowed
        }}
        
        r = requests.post(
            f"{self.BASE_URL}/channels/{channel_id}/polls",
            headers=self.headers,
            json=payload
        )
        
        r.raise_for_status()        
        data = r.json()
        
        poll = Poll(
            channel_id=channel_id, message_id=data["message_id"], prompt=question, options=options, duration=duration, on_end=callback
        )
        poll.start()
        
        return poll
    
    
    async def get_vote_users(self, poll: Poll):
        """
        Retrieves information about what users votes for what options

        Args:
            poll (Poll): The poll to retrieve votes from
            
        Returns:
            int[]: The list of user_ids
        """
        data = []
        
        # Fetch the results for each option
        for index in range(len(poll.options)):
            users = await self.fetch_option_users(channel_id=poll.channel_id, message_id=poll.message_id, answer_id=index)
            
        ids = []
        
        for user in users:
            ids.append(user["id"])
        
        data.append(ids)
        return data
            
    async def get_vote_counts(self, poll: Poll):
        votes = []
        
        users = []
        for index in range(len(poll.options)):
            users.append(await self.fetch_option_users(channel_id=poll.channel_id, message_id=poll.message_id, answer_id=index))
            votes.append(len(users[index]))
            
        return votes
    
    # Fetch poll options (answers) for a specific poll message
    async def fetch_option_users(self, poll: Poll, answer_id: int):
        """
        Retrieve the list of users who voted for a specific answer option in a given poll.
        Args:
            poll (Poll): The poll object containing channel and message identifiers.
            answer_id (int): The identifier of the answer option to fetch voters for.
        Returns:
            list: A list of user identifiers who voted for the specified answer option.
        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
            KeyError: If the expected 'users' key is not present in the response data.
        """
        
        channel_id = poll.channel_id
        message_id = poll.message_id
        
        url = f"{self.BASE_URL}/channels/{channel_id}/polls/{message_id}/answers/{answer_id}"
        response = requests.get(url=url, headers=self.headers)
        data = response.json()  # Poll data
        
        return data["users"]
    
    async def end_poll(self, poll: Poll):
        """
        Ends an active poll in a specified Discord channel.

        Args:
            poll (Poll): The Poll object representing the poll to be ended.
        """
        url = f"{self.BASE_URL}/channels/{poll.channel_id}/polls/{poll.message_id}/expire"
        response = requests.post(url=url, headers=self.headers)
        response.raise_for_status()  # Raise an error for bad responses
        poll.ended = True  # Mark the poll as ended
        poll.on_end and await poll._safe_callback()  # Call the on_end callback if provided
    
    # Helper function to format the poll options
    async def format_options(self, options: List[str]):
        """
        Formats the poll options for the API request.

        Args:
            options (List[str]): The list of poll options.

        Returns:
            List[Dict[str, Any]]: The formatted poll options.
        """
        formatted_options = []
        for index, opt in enumerate(options):
            formatted_options.append({
                "answer_id": str(index + 1), 
                "poll_media": {"text": str(opt)}
            })
        return formatted_options
