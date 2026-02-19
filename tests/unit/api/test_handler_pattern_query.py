"""Unit tests for the pattern query handler.

Tests the handler logic in isolation using a mock AdapterPatternStore.
Verifies correct delegation, model transformation, and pagination metadata.

Ticket: OMN-2253
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest
from fastapi import HTTPException

from omniintelligence.api.handler_pattern_query import handle_query_patterns
from omniintelligence.api.model_pattern_query_page import ModelPatternQueryPage
from omniintelligence.api.model_pattern_query_response import ModelPatternQueryResponse


@pytest.fixture
def mock_adapter() -> AsyncMock:
    """Create a mock AdapterPatternStore with query_patterns method."""
    adapter = AsyncMock()
    adapter.query_patterns = AsyncMock(return_value=[])
    return adapter


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
class TestHandleQueryPatterns:
    """Tests for handle_query_patterns handler function."""

    async def test_returns_empty_page_when_no_results(
        self, mock_adapter: AsyncMock
    ) -> None:
        """Handler returns empty page with correct metadata when no patterns match."""
        result = await handle_query_patterns(
            adapter=mock_adapter,
            domain="nonexistent",
            min_confidence=0.9,
            limit=10,
            offset=0,
        )

        assert isinstance(result, ModelPatternQueryPage)
        assert result.patterns == []
        assert result.total_returned == 0
        assert result.limit == 10
        assert result.offset == 0

    async def test_delegates_all_params_to_adapter(
        self, mock_adapter: AsyncMock
    ) -> None:
        """Handler passes all query parameters to the adapter."""
        await handle_query_patterns(
            adapter=mock_adapter,
            domain="error_handling",
            language="python",
            min_confidence=0.8,
            limit=25,
            offset=10,
        )

        mock_adapter.query_patterns.assert_awaited_once_with(
            domain="error_handling",
            language="python",
            min_confidence=0.8,
            limit=25,
            offset=10,
        )

    async def test_transforms_rows_to_response_models(
        self,
        mock_adapter: AsyncMock,
        sample_pattern_row: dict,
    ) -> None:
        """Handler converts raw dict rows into typed response models."""
        mock_adapter.query_patterns.return_value = [sample_pattern_row]

        result = await handle_query_patterns(
            adapter=mock_adapter,
            limit=50,
            offset=0,
        )

        assert result.total_returned == 1
        pattern = result.patterns[0]
        assert isinstance(pattern, ModelPatternQueryResponse)
        assert pattern.id == sample_pattern_row["id"]
        assert pattern.domain_id == "error_handling"
        assert pattern.confidence == 0.9
        assert pattern.status == "validated"
        assert pattern.version == 2

    async def test_handles_multiple_results(
        self,
        mock_adapter: AsyncMock,
        sample_pattern_row: dict,
    ) -> None:
        """Handler correctly processes multiple pattern rows."""
        row2 = {
            **sample_pattern_row,
            "id": uuid4(),
            "domain_id": "logging",
            "status": "provisional",
            "confidence": 0.75,
        }
        mock_adapter.query_patterns.return_value = [sample_pattern_row, row2]

        result = await handle_query_patterns(
            adapter=mock_adapter,
            limit=50,
            offset=0,
        )

        assert result.total_returned == 2
        assert result.patterns[0].domain_id == "error_handling"
        assert result.patterns[1].domain_id == "logging"

    async def test_preserves_pagination_metadata(self, mock_adapter: AsyncMock) -> None:
        """Handler echoes back the pagination parameters in the response."""
        result = await handle_query_patterns(
            adapter=mock_adapter,
            limit=25,
            offset=75,
        )

        assert result.limit == 25
        assert result.offset == 75

    async def test_default_parameters(self, mock_adapter: AsyncMock) -> None:
        """Handler uses correct defaults when optional params are omitted."""
        await handle_query_patterns(adapter=mock_adapter)

        mock_adapter.query_patterns.assert_awaited_once_with(
            domain=None,
            language=None,
            min_confidence=0.7,
            limit=50,
            offset=0,
        )

    async def test_database_error_returns_502(self, mock_adapter: AsyncMock) -> None:
        """Handler returns HTTPException 502 when database query fails."""
        mock_adapter.query_patterns.side_effect = asyncpg.PostgresError(
            "connection refused"
        )

        with pytest.raises(HTTPException) as exc_info:
            await handle_query_patterns(adapter=mock_adapter)

        assert exc_info.value.status_code == 502
        assert "database error" in exc_info.value.detail.lower()

    async def test_validation_error_returns_502(self, mock_adapter: AsyncMock) -> None:
        """Handler returns HTTPException 502 when rows have unexpected schema."""
        # Return a row missing required fields so model_validate raises
        # ValidationError.
        mock_adapter.query_patterns.return_value = [
            {"bad_field": "not_a_valid_pattern"}
        ]

        with pytest.raises(HTTPException) as exc_info:
            await handle_query_patterns(adapter=mock_adapter)

        assert exc_info.value.status_code == 502
        assert "unexpected schema" in exc_info.value.detail.lower()
