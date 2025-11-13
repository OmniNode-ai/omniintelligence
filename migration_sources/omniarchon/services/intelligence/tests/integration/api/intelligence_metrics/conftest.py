"""
Integration test fixtures for Intelligence Metrics API.

Provides database pool initialization for intelligence metrics endpoint tests.
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="function", autouse=True)
async def mock_intelligence_db_pool():
    """
    Mock database pool for intelligence metrics tests.

    Since integration tests run without a live database connection,
    this fixture mocks the database pool to prevent 503 errors.

    Auto-used for all tests in this directory.
    """
    from src.api.intelligence_metrics.routes import initialize_db_pool

    # Create mock connection
    mock_connection = AsyncMock()
    mock_connection.fetch = AsyncMock(return_value=[])  # Empty results by default
    mock_connection.fetchrow = AsyncMock(return_value=None)
    mock_connection.execute = AsyncMock()

    # Create async context manager for connection
    class MockAcquireContext:
        async def __aenter__(self):
            return mock_connection

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Create mock pool
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=MockAcquireContext())

    # Initialize the routes module with mock pool
    initialize_db_pool(mock_pool)

    yield mock_pool

    # Cleanup - reset to None after test
    initialize_db_pool(None)
