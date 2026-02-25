import pytest
from Pollcord.voter import Voter


def test_voter_from_dict_full():
    """from_dict should correctly map all fields from a full API response."""
    data = {
        "id": "123456789",
        "username": "testuser",
        "discriminator": "1234",
        "avatar": "abc123hash",
        "bot": False,
        "global_name": "Test User",
    }
    v = Voter.from_dict(data)

    assert v.id == 123456789
    assert v.username == "testuser"
    assert v.discriminator == "1234"
    assert v.avatar == "abc123hash"
    assert v.bot is False
    assert v.global_name == "Test User"


def test_voter_from_dict_minimal():
    """from_dict should handle a minimal API response with sensible defaults."""
    v = Voter.from_dict({"id": "42", "username": "minimal"})

    assert v.id == 42
    assert v.username == "minimal"
    assert v.discriminator == "0"
    assert v.avatar is None
    assert v.bot is False
    assert v.global_name is None


def test_voter_from_dict_bot():
    """from_dict should correctly identify bot accounts."""
    v = Voter.from_dict({"id": "1", "username": "some_bot", "bot": True})
    assert v.bot is True


def test_voter_id_is_int():
    """ID should be stored as int even when the API returns it as a string."""
    v = Voter.from_dict({"id": "999999999999999999", "username": "snowflake"})
    assert isinstance(v.id, int)
    assert v.id == 999999999999999999


def test_voter_display_name_uses_global_name():
    """display_name should return global_name when it is set."""
    v = Voter(id=1, username="handle", global_name="Friendly Name")
    assert v.display_name == "Friendly Name"


def test_voter_display_name_falls_back_to_username():
    """display_name should fall back to username when global_name is None."""
    v = Voter(id=1, username="handle", global_name=None)
    assert v.display_name == "handle"


def test_voter_repr():
    """__repr__ should include id, username, and display_name."""
    v = Voter(id=1, username="alice", global_name="Alice")
    r = repr(v)
    assert "1" in r
    assert "alice" in r
    assert "Alice" in r


def test_voter_equality():
    """Two Voter instances with identical fields should be equal (dataclass default)."""
    v1 = Voter(id=1, username="alice")
    v2 = Voter(id=1, username="alice")
    assert v1 == v2


def test_voter_inequality():
    """Voter instances with different IDs should not be equal."""
    v1 = Voter(id=1, username="alice")
    v2 = Voter(id=2, username="alice")
    assert v1 != v2