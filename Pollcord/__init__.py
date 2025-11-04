from pollcord.client import PollClient
from pollcord.poll import Poll
from pollcord.error import PollCreationError, PollNotFoundError, PollcordError
import importlib.metadata
import logging

logger = logging.getLogger("pollcord")
logger.addHandler(logging.NullHandler())

__all__ = ['PollClient', 'Poll', 'PollCreationError', 'PollNotFoundError', 'PollcordError']
__version__ = importlib.metadata.version("Pollcord")