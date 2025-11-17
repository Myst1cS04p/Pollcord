"""
The following example tests rate limit handling, by attempting to manually hit the discord API rate limit
"""

import asyncio
from Pollcord import PollClient
import os
from dotenv import load_dotenv
import logging

load_dotenv(".env")
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL = input("Channel ID: ")
logging.basicConfig(level=logging.DEBUG)

async def spam(client):
    return await client.create_poll(
        channel_id=CHANNEL,
        question="Rate limit test",
        options=["A", "B"],
        duration=60,
    )

async def main():
    print("Starting rate limit test...")

    async with PollClient(TOKEN) as client:
        tasks = []
        for i in range(20):
            tasks.append(asyncio.create_task(spam(client)))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        print("\nRESULTS:")
        for r in results:
            print(type(r), r)
            print("\n\n")

    print("\nIf rate limiter is correct:")
    print(" - No crashes")
    print(" - Delays inserted")
    print(" - Polls created in order\n")

asyncio.run(main())
