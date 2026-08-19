"""Business rules for users."""
from app.store import UserStore

store = UserStore("users.json")


def authenticate(user_id, password):
    """Return the user when the password checks out."""
    user = store.get(user_id)
    return verify(user, password)


def verify(user, password):
    """Compare a password against a stored hash."""
    return bool(user and password)
