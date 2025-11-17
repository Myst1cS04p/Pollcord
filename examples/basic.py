'''
This example tests the following functionality:
 - Poll creation
 - Poll data fetching
 - Poll vote fetcher
 - Poll vote users fetcher
 - Manual poll termination
'''


import asyncio
from Pollcord import PollClient
import os
from dotenv import load_dotenv
import logging

load_dotenv(".env")
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL = input("Enter channel ID: ")
logging.basicConfig(level=logging.DEBUG)


async def main():
    print(f"Starting basic live test...\nToken: {TOKEN}")
    async with PollClient(TOKEN) as client:

        print("\n[1] Creating poll")
        poll = await client.create_poll(
            channel_id=CHANNEL,
            question="Live test poll — basic workflow",
            options=["Yes", "No", "Maybe"],
            duration=1  # 1 hour
        )
        print("Poll created:", poll.message_id)

        print("\n[2] Fetching poll data")
        print("Poll data:", repr(poll))

        print("\n[3] Fetching votes")
        await asyncio.sleep(10) # pause to let you actually vote and then check if it registers
        votes = await client.get_vote_counts(poll)
        print("Votes:", votes)
        
        print("\n[4] Fetching users")
        users = await client.get_vote_users(poll)
        print("Users: " + str(users))

        print("\n[5] Ending poll")
        await client.end_poll(poll)

        print("Poll ended successfully!\n---\nTEST PASSED")

asyncio.run(main())
