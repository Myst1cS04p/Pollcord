from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

try:
    from discord import User as DiscordUser
    HAS_DISCORD_PY = True
except ImportError:
    HAS_DISCORD_PY = False


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

    def to_discord_user(self) -> "DiscordUser":
        """
        Attempt to return a discord.py User-compatible object.

        Raises:
            RuntimeError: If discord.py is not installed.
            NotImplementedError: Always — discord.py User objects require
                internal client state and cannot be constructed from raw data.
                Use this Voter object directly instead; its attributes mirror
                those of discord.py's User.
        """
        if not HAS_DISCORD_PY:
            raise RuntimeError(
                "discord.py is not installed. Install it with: pip install discord.py"
            )
        raise NotImplementedError(
            "discord.py User objects require internal client state and cannot be "
            "constructed from raw API data. Use the Voter object directly — its "
            "attributes (id, username, discriminator, avatar, bot, global_name) "
            "mirror those of discord.py's User."
        )