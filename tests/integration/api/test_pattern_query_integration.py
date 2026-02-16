"""Integration tests for the pattern query API with real pattern store.

Tests the full request path from HTTP endpoint through handler to
the AdapterPatternStore using a real database connection pool.
Skips gracefully when PostgreSQL is not available.

Ticket: OMN-2253
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import requires_postgres


@pytest.mark.integration
@requires_postgres
class TestPatternQueryIntegration:
    """Integration tests for GET /api/v1/patterns with real database."""

    @pytest_asyncio.fixture
    async def app_with_db(self, db_pool: Any) -> FastAPI:
        """Create a FastAPI app wired to a real database pool."""
        from omniintelligence.api.router_patterns import create_pattern_router
        from omniintelligence.repositories.adapter_pattern_store import (
            create_pattern_store_adapter,
        )

        adapter = await create_pattern_store_adapter(db_pool)

        async def get_adapter():
            return adapter

        test_app = FastAPI()
        router = create_pattern_router(get_adapter=get_adapter)
        test_app.include_router(router)
        return test_app

    @pytest_asyncio.fixture
    async def client(self, app_with_db: FastAPI) -> AsyncClient:
        """Create an async HTTP client for the test app."""
        transport = ASGITransport(app=app_with_db)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    async def test_endpoint_returns_200(self, client: AsyncClient) -> None:
        """Endpoint connects to database and returns 200."""
        response = await client.get("/api/v1/patterns")
        assert response.status_code == 200

        body = response.json()
        assert "patterns" in body
        assert "total_returned" in body
        assert "limit" in body
        assert "offset" in body

    async def test_domain_filter_returns_valid_response(
        self, client: AsyncClient
    ) -> None:
        """Endpoint returns valid response when filtering by domain."""
        response = await client.get("/api/v1/patterns?domain=code_generation")
        assert response.status_code == 200

        body = response.json()
        # All returned patterns should have the requested domain
        for pattern in body["patterns"]:
            assert pattern["domain_id"] == "code_generation"

    async def test_confidence_filter_enforced(self, client: AsyncClient) -> None:
        """Endpoint only returns patterns above confidence threshold."""
        response = await client.get("/api/v1/patterns?min_confidence=0.9")
        assert response.status_code == 200

        body = response.json()
        for pattern in body["patterns"]:
            assert pattern["confidence"] >= 0.9

    async def test_only_validated_provisional_returned(
        self, client: AsyncClient
    ) -> None:
        """Endpoint only returns validated or provisional patterns."""
        response = await client.get("/api/v1/patterns?min_confidence=0.0")
        assert response.status_code == 200

        body = response.json()
        for pattern in body["patterns"]:
            assert pattern["status"] in ("validated", "provisional")

    async def test_pagination_works(self, client: AsyncClient) -> None:
        """Endpoint respects limit and offset pagination."""
        response = await client.get("/api/v1/patterns?limit=1&offset=0")
        assert response.status_code == 200

        body = response.json()
        assert body["limit"] == 1
        assert body["offset"] == 0
        assert body["total_returned"] <= 1
