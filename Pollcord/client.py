import aiohttp
from typing import List
from Pollcord.poll import Poll

class PollClient:
    BASE_URL = "https://discord.com/api/v10"

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json"
        }
        self.session = aiohttp.ClientSession(headers=self.headers)

    async def create_poll(self, channel_id: int, question: str, options: List[str],
                          duration: int = 1, isMultiselect: bool = False, callback=None) -> Poll:
        payload = {
            "poll": {
                "question": {"text": question},
                "answers": self.format_options(options),
                "duration": duration,
                "allow_multiselect": isMultiselect,
            }
        }

        async with self.session.post(f"{self.BASE_URL}/channels/{channel_id}/polls", json=payload) as r:
            if r.status != 200 and r.status != 201:
                text = await r.text()
                raise Exception(f"Failed to create poll: {r.status} {text}")
            data = await r.json()

        poll = Poll(
            channel_id=channel_id,
            message_id=data["message_id"],
            prompt=question,
            options=options,
            duration=duration,
            on_end=callback
        )
        poll.start()
        return poll

    async def get_vote_users(self, poll: Poll):
        results = []
        for index in range(len(poll.options)):
            users = await self.fetch_option_users(poll, index)
            results.append([u["id"] for u in users])
        return results

    async def get_vote_counts(self, poll: Poll):
        counts = []
        for index in range(len(poll.options)):
            users = await self.fetch_option_users(poll, index)
            counts.append(len(users))
        return counts

    async def fetch_option_users(self, poll: Poll, answer_id: int):
        url = f"{self.BASE_URL}/channels/{poll.channel_id}/polls/{poll.message_id}/answers/{answer_id + 1}"
        async with self.session.get(url) as r:
            if r.status != 200:
                text = await r.text()
                raise Exception(f"Failed to fetch poll users: {r.status} {text}")
            data = await r.json()
            return data.get("users", [])

    async def end_poll(self, poll: Poll):
        url = f"{self.BASE_URL}/channels/{poll.channel_id}/polls/{poll.message_id}/expire"
        async with self.session.post(url) as r:
            if r.status != 200 and r.status != 204:
                text = await r.text()
                raise Exception(f"Failed to end poll: {r.status} {text}")
        poll.ended = True
        if poll.on_end:
            await poll._safe_callback()

    @staticmethod
    def format_options(options: List[str]):
        return [
            {"answer_id": str(i + 1), "poll_media": {"text": str(opt)}}
            for i, opt in enumerate(options)
        ]

    async def close(self):
        await self.session.close()
