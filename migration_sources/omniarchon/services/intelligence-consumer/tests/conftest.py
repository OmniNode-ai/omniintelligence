"""
Pytest configuration for intelligence-consumer tests.

Provides shared fixtures and configuration.
"""

import sys
from pathlib import Path

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration between tests."""
    import logging

    # Clear all handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    yield

    # Cleanup after test
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)


@pytest.fixture
def event_loop_policy():
    """Use default event loop policy for async tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()
