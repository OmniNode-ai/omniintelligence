"""Unit tests for the pattern query router.

Tests the FastAPI endpoint using httpx.AsyncClient with a mock adapter.
Validates HTTP-level behavior: status codes, query parameter validation,
response schema, and error handling.

Ticket: OMN-2253
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from omniintelligence.api.router_patterns import create_pattern_router


@pytest.fixture
def mock_adapter() -> AsyncMock:
    """Create a mock AdapterPatternStore."""
    adapter = AsyncMock()
    adapter.query_patterns = AsyncMock(return_value=[])
    return adapter


@pytest.fixture
def app(mock_adapter: AsyncMock) -> FastAPI:
    """Create a test FastAPI app with the pattern router."""
    test_app = FastAPI()

    async def get_adapter():
        return mock_adapter

    router = create_pattern_router(get_adapter=get_adapter)
    test_app.include_router(router)
    return test_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    """Create an async HTTP client for the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_pattern_row() -> dict:
    """Create a sample pattern row as returned by the database."""
    return {
        "id": uuid4(),
        "pattern_signature": "def handle_error(exc): log(exc); raise",
        "signature_hash": "testhash_error_handling_v2",
        "domain_id": "error_handling",
        "quality_score": 0.85,
        "confidence": 0.9,
        "status": "validated",
        "is_current": True,
        "version": 2,
        "created_at": datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC),
    }


@pytest.mark.unit
class TestGetPatternsEndpoint:
    """Tests for GET /api/v1/patterns endpoint."""

    async def test_returns_200_with_empty_results(self, client: AsyncClient) -> None:
        """Endpoint returns 200 with empty patterns list when no matches."""
        response = await client.get("/api/v1/patterns")

        assert response.status_code == 200
        body = response.json()
        assert body["patterns"] == []
        assert body["total_returned"] == 0
        assert body["limit"] == 50
        assert body["offset"] == 0

    async def test_returns_patterns_with_correct_schema(
        self,
        client: AsyncClient,
        mock_adapter: AsyncMock,
        sample_pattern_row: dict,
    ) -> None:
        """Endpoint returns properly serialized pattern data."""
        mock_adapter.query_patterns.return_value = [sample_pattern_row]

        response = await client.get("/api/v1/patterns")

        assert response.status_code == 200
        body = response.json()
        assert body["total_returned"] == 1

        pattern = body["patterns"][0]
        assert pattern["domain_id"] == "error_handling"
        assert pattern["confidence"] == 0.9
        assert pattern["status"] == "validated"
        assert pattern["version"] == 2
        assert "id" in pattern
        assert "created_at" in pattern

    async def test_passes_domain_filter(
        self,
        client: AsyncClient,
        mock_adapter: AsyncMock,
    ) -> None:
        """Endpoint passes domain query parameter to adapter."""
        await client.get("/api/v1/patterns?domain=error_handling")

        mock_adapter.query_patterns.assert_awaited_once()
        call_kwargs = mock_adapter.query_patterns.call_args.kwargs
        assert call_kwargs["domain"] == "error_handling"

    async def test_passes_language_filter(
        self,
        client: AsyncClient,
        mock_adapter: AsyncMock,
    ) -> None:
        """Endpoint passes language query parameter to adapter."""
        await client.get("/api/v1/patterns?language=python")

        mock_adapter.query_patterns.assert_awaited_once()
        call_kwargs = mock_adapter.query_patterns.call_args.kwargs
        assert call_kwargs["language"] == "python"

    async def test_passes_min_confidence_filter(
        self,
        client: AsyncClient,
        mock_adapter: AsyncMock,
    ) -> None:
        """Endpoint passes min_confidence query parameter to adapter."""
        await client.get("/api/v1/patterns?min_confidence=0.85")

        mock_adapter.query_patterns.assert_awaited_once()
        call_kwargs = mock_adapter.query_patterns.call_args.kwargs
        assert call_kwargs["min_confidence"] == 0.85

    async def test_passes_pagination_params(
        self,
        client: AsyncClient,
        mock_adapter: AsyncMock,
    ) -> None:
        """Endpoint passes limit and offset to adapter."""
        await client.get("/api/v1/patterns?limit=25&offset=50")

        mock_adapter.query_patterns.assert_awaited_once()
        call_kwargs = mock_adapter.query_patterns.call_args.kwargs
        assert call_kwargs["limit"] == 25
        assert call_kwargs["offset"] == 50

    async def test_validates_min_confidence_range(self, client: AsyncClient) -> None:
        """Endpoint rejects min_confidence outside 0.0-1.0 range."""
        response = await client.get("/api/v1/patterns?min_confidence=1.5")
        assert response.status_code == 422

        response = await client.get("/api/v1/patterns?min_confidence=-0.1")
        assert response.status_code == 422

    async def test_validates_limit_range(self, client: AsyncClient) -> None:
        """Endpoint rejects limit outside 1-200 range."""
        response = await client.get("/api/v1/patterns?limit=0")
        assert response.status_code == 422

        response = await client.get("/api/v1/patterns?limit=201")
        assert response.status_code == 422

    async def test_validates_offset_non_negative(self, client: AsyncClient) -> None:
        """Endpoint rejects negative offset."""
        response = await client.get("/api/v1/patterns?offset=-1")
        assert response.status_code == 422

    async def test_all_params_combined(
        self,
        client: AsyncClient,
        mock_adapter: AsyncMock,
    ) -> None:
        """Endpoint correctly handles all parameters together."""
        await client.get(
            "/api/v1/patterns"
            "?domain=error_handling"
            "&language=python"
            "&min_confidence=0.8"
            "&limit=10"
            "&offset=20"
        )

        mock_adapter.query_patterns.assert_awaited_once()
        call_kwargs = mock_adapter.query_patterns.call_args.kwargs
        assert call_kwargs["domain"] == "error_handling"
        assert call_kwargs["language"] == "python"
        assert call_kwargs["min_confidence"] == 0.8
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 20
