# Pollcord

**Pollcord** is a lightweight asynchronous Python wrapper for Discord’s poll API.  
It handles poll creation, fetching, and expiration — while giving you a clean, extensible framework for running polls in bots or automation scripts.

---

## Features

- **Async-first design** – fully `async`/`await` compatible
- **Modular structure** – clean separation of client, models, and errors
- **Context-managed sessions** – automatic setup/teardown
- **Built-in rate limiting**
- **Meaningful error hierarchy**
- **Retries on transient failures** (planned)
- **Extensible** – easy to plug into your existing bot framework

---

## Installation

```bash
pip install pollcord
```

Or if you’re testing locally / from source (should work right now):

```bash
git clone https://github.com/<yourname>/pollcord.git
cd pollcord
pip install -e .
```

---

## Quickstart
Here’s a minimal example showing how to create and end a poll.
```python
import asyncio
from pollcord import PollClient

TOKEN = "your_bot_token_here"

async def main():
    async with PollClient(TOKEN) as client:
        # Create a poll
        poll = await client.create_poll(
            channel_id=123456789012345678,
            question="What should we build next?",
            options=["Mega base", "PvP arena", "Mob farm"]
        )
        print(f"Created poll: {poll.message_id}")

        # Fetch results
        votes = await client.get_vote_counts(poll)
        print("Current votes:", votes)

        # End the poll manually
        await poll.end(client)
        print("Poll ended!")

asyncio.run(main())
```

---

## Architecture Overview

Pollcord is built around three core layers:

| Layer | Description |
| :------- | :------: |
| PollClient | The main entry point — handles auth, rate limiting, and session context | 
| Poll | A high-level model representing a poll, with helper methods for interacting with it | 
| errors | Custom exceptions with Discord response context for debugging |

---

## Testing

Tests are written with pytest and use async mocks for API responses.
Run them with:

```bash
pytest -v
```

**Covered**:
- Poll creation
- Fetching poll data
- Ending polls
- Error handling

---

## Example Scripts

See the `examples/` directory for working demos:

- `basic.py` — Basic poll creation, termination, and vote fetching
- `concurrency.py` — Demonstration of concurrent poll handling
- `rate_limit.py` — Demonstrates rate limit handling
- `lifecycle.py` — Poll creation and periodic fetching of data

---

## Logging
Pollcord uses Python’s built-in `logging` module.
You can enable debug output to trace requests:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Roadmap

- Documentation that doesn’t completely suck :sweat_smile:
- Request queuing 

---

## Contributing

Contributions are welcome!
If you’d like to help with tests, documentation, or feature ideas:
1) Fork the repo
2) Create a feature branch (`git checkout -b feature/my-improvement`)
3) Submit a PR with clear commit messages

---

## Support

- Discord Server: https://discord.gg/gkc7dSS8Ef
- Myst1cS04p's discord: `@myst1cso4p`
- ChatGPT or smth idk

---

## License
MIT License © 2025 [Myst1cS04p]  
This project is unaffiliated with Discord Inc.  

---

## Credits

Inspired by real bot-development pain.  
Developed by Myst1cS04p  
Development assistance by Github Copilot  
README, examples, and tests written by ChatGPT cuz I'm lazy

