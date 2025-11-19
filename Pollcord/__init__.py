from Pollcord.client import PollClient
from Pollcord.poll import Poll
from Pollcord.error import PollCreationError, PollNotFoundError, PollcordError
import importlib.metadata
import logging

logger = logging.getLogger("pollcord")
logger.addHandler(logging.NullHandler())

__all__ = [
    "PollClient",
    "Poll",
    "PollCreationError",
    "PollNotFoundError",
    "PollcordError",
]
__version__ = importlib.metadata.version("Pollcord")
