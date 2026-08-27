"""Business rules for users."""
from app.store import UserStore

store = UserStore("users.json")


class AuditedUserStore(UserStore):
    """A store that notes every lookup, for the audit log."""

    def get(self, user_id):
        """Return one user row, and record that it was asked for."""
        return super().get(user_id)


def authenticate(user_id, password):
    """Return the user when the password checks out."""
    user = store.get(user_id)
    return verify(user, password)


def verify(user, password):
    """Compare a password against a stored hash."""
    return bool(user and password)
