"""
User model definition.

Defines the User entity with basic validation.
"""


class User:
    """User entity representing a system user."""

    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email
        self.active = True

    def deactivate(self):
        """Deactivate the user."""
        self.active = False

    def __repr__(self):
        return f"User(name={self.name}, email={self.email}, active={self.active})"
