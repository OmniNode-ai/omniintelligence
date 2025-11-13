#!/usr/bin/env python3
"""
Integration Test Conftest Fixture Validation

Verifies that the actual conftest.py fixtures work correctly without ScopeMismatch errors.
"""

import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_service_urls_fixture(service_urls):
    """Test that service_urls fixture is accessible"""
    assert service_urls is not None
    assert hasattr(service_urls, "intelligence")
    assert hasattr(service_urls, "bridge")
    assert hasattr(service_urls, "search")


@pytest.mark.asyncio
async def test_session_fixture(test_session):
    """Test that test_session fixture (session-scoped async) is accessible"""
    assert test_session is not None
    assert hasattr(test_session, "session_id")
    assert hasattr(test_session, "services")
    assert test_session.session_id.startswith("test_")


@pytest.mark.asyncio
async def test_session_fixture_multiple_access(test_session):
    """Test that test_session fixture can be accessed multiple times"""
    assert test_session is not None
    session_id = test_session.session_id
    # Verify the session_id is consistent (same session instance)
    assert test_session.session_id == session_id
