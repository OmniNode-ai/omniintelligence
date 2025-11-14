"""
Pytest configuration and fixtures.

Shared test fixtures for all tests.
"""

import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_code():
    """Sample code for testing."""
    return """
def calculate_fibonacci(n: int) -> int:
    \"\"\"Calculate nth Fibonacci number.\"\"\"
    if n <= 1:
        return n
    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)
"""


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing."""
    return {
        "file_path": "src/utils/math.py",
        "language": "python",
        "project_name": "test_project",
        "author": "test_user",
    }
