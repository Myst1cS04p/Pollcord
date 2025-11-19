from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from Pollcord import Poll


class PollcordError(Exception):
    """Base exception for Pollcord errors."""

    def __init__(self, message: str, poll: Optional[Poll] = None):
        """
        Initialize a PollcordError.

        Parameters:
            message (str): The error message.
            poll (Optional[Poll]): The poll associated with the error, if any.
        """
        self.poll = poll
        super().__init__(message)

    def __str__(self):
        base = f"{self.__class__.__name__}: {self.args[0] if self.args else ''}"
        if self.poll:
            base += f"\nPoll: {self.poll}"
        return base


class PollCreationError(PollcordError):
    """Raised when a poll cannot be created."""


class PollNotFoundError(PollcordError):
    """Raised when a poll cannot be found."""


class PollExpiredError(PollcordError):
    """Raised when trying to interact with an expired poll."""
