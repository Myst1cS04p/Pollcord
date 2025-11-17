"""
This example demonstrates pollcord's ability to handle polls concurrently 
"""

import asyncio
from Pollcord import PollClient
from dotenv import load_dotenv
import os

load_dotenv(".env")
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL = input("Channel ID: ")

async def make_poll(client, i):
    poll = await client.create_poll(
        channel_id=CHANNEL,
        question=f"Concurrency test #{i}",
        options=["One", "Two"],
        duration=2
    )
    print(f"Created poll #{i}: {poll.message_id}")
    return poll

async def main():
    print("Running concurrency test...")
    async with PollClient(TOKEN) as client:
        tasks = [asyncio.create_task(make_poll(client, i)) for i in range(5)]
        await asyncio.gather(*tasks)

    print("\nIf concurrency is correct:")
    print(" - No mixed responses")
    print(" - No overlapping request errors")
    print(" - No rate limit meltdown")
    print(" - Likely unordered polls")

asyncio.run(main())
