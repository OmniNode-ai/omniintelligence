"""Test permissive mode - should allow write then auto-fix."""


def create_user_session():  # Violation: should be create_user_session
    """Create a new user session."""
    return {"session_id": "12345"}


def validate_api_token():  # Violation: should be validate_api_token
    """Validate API token."""
    return True


def process_webhook_event():  # Violation: should be process_webhook_event
    """Process incoming webhook event."""
    return {"status": "processed"}
