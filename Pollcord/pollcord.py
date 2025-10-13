import discord

class Pollcord:
    def __init__(self, bot_token):
        self.client = discord.Client()
        self.bot_token = bot_token
    
    def create_poll(self, channel_id, question, options):
        """
        Creates a poll in the given channel

        Args:
            channel_id (int): The channel id to create the poll in
            question (str): The prompt message of the poll
            options (str[]): The options provided in the poll

        Returns:
            Poll: The object of the created poll
        """
        return None
