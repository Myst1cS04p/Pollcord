from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Voter:
    """
    Represents a user who voted in a poll.

    Attribute names mirror discord.py's User object for familiarity.
    If discord.py is not installed, this serves as a standalone data object.

    Attributes:
        id (int): The user's Discord snowflake ID.
        username (str): The user's username.
        discriminator (str): The user's discriminator tag (e.g. '0' for new usernames).
        avatar (Optional[str]): The user's avatar hash, if set.
        bot (bool): Whether the user is a bot account.
        global_name (Optional[str]): The user's global display name, if set.
    """

    id: int
    username: str
    discriminator: str = "0"
    avatar: Optional[str] = None
    bot: bool = False
    global_name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Voter":
        """
        Construct a Voter from a raw Discord API user dict.

        Parameters:
            data (dict): Raw user object from the Discord API.

        Returns:
            Voter: A populated Voter instance.
        """
        return cls(
            id=int(data["id"]),
            username=data.get("username", ""),
            discriminator=data.get("discriminator", "0"),
            avatar=data.get("avatar"),
            bot=data.get("bot", False),
            global_name=data.get("global_name"),
        )

    @property
    def display_name(self) -> str:
        """Returns the global display name if set, otherwise the username."""
        return self.global_name or self.username

    def __repr__(self) -> str:
        return (
            f"<Voter id={self.id} username={self.username!r}"
            f" display_name={self.display_name!r}>"
        )
