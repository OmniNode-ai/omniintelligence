"""A node with environment variable access violations.

This fixture demonstrates forbidden patterns:
- os.environ access
- os.getenv() calls
- os.putenv() calls
"""

import os
from typing import Any


def get_config_from_env() -> dict[str, Any]:
    """BAD: Reads configuration directly from environment."""
    # VIOLATION: os.environ subscript access
    api_key = os.environ["API_KEY"]

    # VIOLATION: os.environ.get()
    timeout = os.environ.get("TIMEOUT", "30")

    # VIOLATION: os.getenv()
    host = os.getenv("SERVICE_HOST", "localhost")

    return {
        "api_key": api_key,
        "timeout": int(timeout),
        "host": host,
    }


def set_env_value(key: str, value: str) -> None:
    """BAD: Sets environment variables directly."""
    # VIOLATION: os.putenv()
    os.putenv(key, value)


def check_env_flag() -> bool:
    """BAD: Checks environment for feature flags."""
    # VIOLATION: 'in' operator with os.environ
    return "DEBUG_MODE" in os.environ
