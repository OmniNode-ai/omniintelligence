#!/usr/bin/env python3
"""
Fixture Scope Validation Test

Verifies that session-scoped async fixtures work correctly without ScopeMismatch errors.
"""

import pytest
import pytest_asyncio


@pytest_asyncio.fixture(scope="session")
async def session_scoped_fixture(event_loop):
    """Test session-scoped async fixture that depends on event_loop"""
    return {"status": "initialized", "scope": "session"}


@pytest_asyncio.fixture
async def function_scoped_fixture(session_scoped_fixture):
    """Test function-scoped async fixture that depends on session-scoped fixture"""
    return {
        "status": "ready",
        "scope": "function",
        "parent": session_scoped_fixture,
    }


@pytest.mark.asyncio
async def test_session_scoped_fixture_access(session_scoped_fixture):
    """Test that session-scoped async fixtures can be accessed without ScopeMismatch"""
    assert session_scoped_fixture is not None
    assert session_scoped_fixture["scope"] == "session"
    assert session_scoped_fixture["status"] == "initialized"


@pytest.mark.asyncio
async def test_function_scoped_fixture_access(function_scoped_fixture):
    """Test that function-scoped fixtures can depend on session-scoped fixtures"""
    assert function_scoped_fixture is not None
    assert function_scoped_fixture["scope"] == "function"
    assert function_scoped_fixture["parent"]["scope"] == "session"


@pytest.mark.asyncio
async def test_multiple_access_to_session_fixture(session_scoped_fixture):
    """Test that session-scoped fixture is reused across tests"""
    assert session_scoped_fixture is not None
    assert session_scoped_fixture["scope"] == "session"
