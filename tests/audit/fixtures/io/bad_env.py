# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

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


def remove_env_value(key: str) -> str | None:
    """BAD: Removes environment variables directly."""
    # VIOLATION: os.environ.pop()
    return os.environ.pop(key, None)


def set_default_env_value(key: str, default: str) -> str:
    """BAD: Sets default environment variables directly."""
    # VIOLATION: os.environ.setdefault()
    return os.environ.setdefault(key, default)


def clear_all_env() -> None:
    """BAD: Clears all environment variables."""
    # VIOLATION: os.environ.clear()
    os.environ.clear()


def bulk_update_env(values: dict[str, str]) -> None:
    """BAD: Bulk updates environment variables."""
    # VIOLATION: os.environ.update()
    os.environ.update(values)
