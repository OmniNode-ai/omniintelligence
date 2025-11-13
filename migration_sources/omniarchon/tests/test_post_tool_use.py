"""Test file for PostToolUse auto-fix functionality."""


def get_user_account():  # Should be auto-fixed to get_user_account
    """Get user account information."""
    return {"account": "data"}


def process_payment_data():  # Should be auto-fixed to process_payment_data
    """Process payment data."""
    return True
