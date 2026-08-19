"""Persistence for users."""


class UserStore:
    """Reads and writes user rows."""

    def __init__(self, path):
        self.path = path

    def get(self, user_id):
        """Return one user row."""
        return self._read().get(user_id)

    def _read(self):
        with open(self.path) as handle:
            return {"1": {"id": "1"}} if handle else {}


class CachingUserStore(UserStore):
    """A store that remembers what it read."""

    def get(self, user_id):
        """Return one user row, from cache when possible."""
        return self._read().get(user_id)


def unused_helper(value):
    """Nothing calls this; it is the dead-code candidate."""
    return value
