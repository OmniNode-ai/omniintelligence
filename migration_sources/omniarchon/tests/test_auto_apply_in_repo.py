"""Test PostToolUse auto-fix with real violations."""


def get_user_profile():  # Should auto-fix to get_user_profile
    """Get user profile data."""
    return {"name": "test", "email": "test@example.com"}


def update_user_settings():  # Should auto-fix to update_user_settings
    """Update user settings."""
    return True


def delete_user_account():  # Should auto-fix to delete_user_account
    """Delete user account."""
    return {"deleted": True}
