"""Unit tests for pattern query API models.

Tests Pydantic model validation, serialization, and frozen behavior.

Ticket: OMN-2253
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from omniintelligence.api.models_pattern_query import (
    ModelPatternQueryPage,
    ModelPatternQueryResponse,
)


@pytest.mark.unit
class TestModelPatternQueryResponse:
    """Tests for ModelPatternQueryResponse model."""

    def test_valid_construction(self) -> None:
        """Model accepts valid pattern data."""
        response = ModelPatternQueryResponse(
            id=uuid4(),
            pattern_signature="def foo(): pass",
            signature_hash="abc123",
            domain_id="testing",
            quality_score=0.85,
            confidence=0.9,
            status="validated",
            is_current=True,
            version=1,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert response.status == "validated"
        assert response.confidence == 0.9

    def test_frozen_model(self) -> None:
        """Model instances are immutable."""
        response = ModelPatternQueryResponse(
            id=uuid4(),
            pattern_signature="def foo(): pass",
            signature_hash="abc123",
            domain_id="testing",
            confidence=0.9,
            status="validated",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        with pytest.raises(ValidationError):
            response.status = "provisional"

    def test_rejects_extra_fields(self) -> None:
        """Model rejects unexpected fields."""
        with pytest.raises(ValidationError):
            ModelPatternQueryResponse(
                id=uuid4(),
                pattern_signature="def foo(): pass",
                signature_hash="abc123",
                domain_id="testing",
                confidence=0.9,
                status="validated",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                unexpected_field="value",
            )

    def test_confidence_validation(self) -> None:
        """Model rejects confidence outside 0.0-1.0 range."""
        with pytest.raises(ValidationError):
            ModelPatternQueryResponse(
                id=uuid4(),
                pattern_signature="def foo(): pass",
                signature_hash="abc123",
                domain_id="testing",
                confidence=1.5,
                status="validated",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_from_attributes_mode(self) -> None:
        """Model can be constructed from object attributes."""

        class MockRow:
            id = uuid4()
            pattern_signature = "def foo(): pass"
            signature_hash = "abc123"
            domain_id = "testing"
            quality_score = 0.8
            confidence = 0.9
            status = "validated"
            is_current = True
            version = 1
            created_at = datetime(2026, 1, 1, tzinfo=UTC)

        response = ModelPatternQueryResponse.model_validate(
            MockRow(), from_attributes=True
        )
        assert response.domain_id == "testing"


@pytest.mark.unit
class TestModelPatternQueryPage:
    """Tests for ModelPatternQueryPage model."""

    def test_valid_construction(self) -> None:
        """Page model accepts valid data."""
        page = ModelPatternQueryPage(
            patterns=[],
            total_returned=0,
            limit=50,
            offset=0,
        )
        assert page.total_returned == 0
        assert page.limit == 50

    def test_with_patterns(self) -> None:
        """Page model includes pattern list."""
        pattern = ModelPatternQueryResponse(
            id=uuid4(),
            pattern_signature="def foo(): pass",
            signature_hash="abc123",
            domain_id="testing",
            confidence=0.9,
            status="validated",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        page = ModelPatternQueryPage(
            patterns=[pattern],
            total_returned=1,
            limit=50,
            offset=0,
        )
        assert len(page.patterns) == 1
        assert page.patterns[0].domain_id == "testing"

    def test_limit_validation(self) -> None:
        """Page model rejects invalid limit values."""
        with pytest.raises(ValidationError):
            ModelPatternQueryPage(
                patterns=[],
                total_returned=0,
                limit=0,
                offset=0,
            )
        with pytest.raises(ValidationError):
            ModelPatternQueryPage(
                patterns=[],
                total_returned=0,
                limit=201,
                offset=0,
            )

    def test_offset_validation(self) -> None:
        """Page model rejects negative offset."""
        with pytest.raises(ValidationError):
            ModelPatternQueryPage(
                patterns=[],
                total_returned=0,
                limit=50,
                offset=-1,
            )
