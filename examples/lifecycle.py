"""
This example creates a poll and periodically fetches it's votes
"""


import asyncio
from Pollcord import PollClient
import os
from dotenv import load_dotenv

load_dotenv(".env")
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL = input("Channel ID: ")

async def main():
    print("Starting lifecycle test...")
    async with PollClient(TOKEN) as client:

        poll = await client.create_poll(
            channel_id=CHANNEL,
            question="Lifecycle test poll",
            options=["Alpha", "Beta", "Gamma"],
            duration=1
        )

        print("Poll created:", poll.message_id)

        # Periodic fetch
        for i in range(6):
            print(f"\nTick #{i+1}: Fetching data...")
            print("Data:", poll)

            votes = await client.get_vote_counts(poll)
            print("Votes:", votes)

            await asyncio.sleep(30)

        print("\nEnding poll...")
        await poll.end(client=client)
        print("Poll ended. Lifecycle test complete!")

asyncio.run(main())
