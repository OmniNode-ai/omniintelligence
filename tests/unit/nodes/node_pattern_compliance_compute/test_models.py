"""Unit tests for pattern compliance models.

Tests validation, immutability, and serialization of input/output models.

Ticket: OMN-2256
"""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.unit

_TEST_CID = UUID("12345678-1234-5678-1234-567812345678")

from omniintelligence.nodes.node_pattern_compliance_compute.models import (
    ModelApplicablePattern,
    ModelComplianceMetadata,
    ModelComplianceRequest,
    ModelComplianceResult,
    ModelComplianceViolation,
)


class TestModelApplicablePattern:
    """Tests for ModelApplicablePattern."""

    def test_valid_pattern(self) -> None:
        """Valid pattern should be created successfully."""
        p = ModelApplicablePattern(
            pattern_id="P001",
            pattern_signature="Use frozen models",
            domain_id="onex",
            confidence=0.9,
        )
        assert p.pattern_id == "P001"
        assert p.confidence == 0.9

    def test_frozen_model(self) -> None:
        """Pattern model should be frozen (immutable)."""
        p = ModelApplicablePattern(
            pattern_id="P001",
            pattern_signature="Use frozen models",
            domain_id="onex",
            confidence=0.9,
        )
        with pytest.raises(ValidationError):
            p.pattern_id = "P002"  # type: ignore[misc]

    def test_empty_pattern_id_rejected(self) -> None:
        """Empty pattern_id should be rejected."""
        with pytest.raises(ValidationError):
            ModelApplicablePattern(
                pattern_id="",
                pattern_signature="Use frozen models",
                domain_id="onex",
                confidence=0.9,
            )

    def test_confidence_out_of_range_rejected(self) -> None:
        """Confidence outside [0, 1] should be rejected."""
        with pytest.raises(ValidationError):
            ModelApplicablePattern(
                pattern_id="P001",
                pattern_signature="Use frozen models",
                domain_id="onex",
                confidence=1.5,
            )


class TestModelComplianceRequest:
    """Tests for ModelComplianceRequest."""

    def test_valid_request(self) -> None:
        """Valid request should be created successfully."""
        r = ModelComplianceRequest(
            correlation_id=_TEST_CID,
            source_path="test.py",
            content="class Foo: pass",
            language="python",
            applicable_patterns=[
                ModelApplicablePattern(
                    pattern_id="P001",
                    pattern_signature="Use frozen models",
                    domain_id="onex",
                    confidence=0.9,
                )
            ],
        )
        assert r.source_path == "test.py"
        assert len(r.applicable_patterns) == 1
        assert r.correlation_id == _TEST_CID

    def test_empty_patterns_rejected(self) -> None:
        """Empty applicable_patterns list should be rejected."""
        with pytest.raises(ValidationError):
            ModelComplianceRequest(
                correlation_id=_TEST_CID,
                source_path="test.py",
                content="class Foo: pass",
                language="python",
                applicable_patterns=[],
            )

    def test_empty_content_rejected(self) -> None:
        """Empty content should be rejected."""
        with pytest.raises(ValidationError):
            ModelComplianceRequest(
                correlation_id=_TEST_CID,
                source_path="test.py",
                content="",
                language="python",
                applicable_patterns=[
                    ModelApplicablePattern(
                        pattern_id="P001",
                        pattern_signature="Use frozen models",
                        domain_id="onex",
                        confidence=0.9,
                    )
                ],
            )

    def test_frozen_model(self) -> None:
        """Request model should be frozen (immutable)."""
        r = ModelComplianceRequest(
            correlation_id=_TEST_CID,
            source_path="test.py",
            content="class Foo: pass",
            language="python",
            applicable_patterns=[
                ModelApplicablePattern(
                    pattern_id="P001",
                    pattern_signature="Test",
                    domain_id="onex",
                    confidence=0.9,
                )
            ],
        )
        with pytest.raises(ValidationError):
            r.content = "new content"  # type: ignore[misc]

    def test_default_language_is_python(self) -> None:
        """Default language should be python."""
        r = ModelComplianceRequest(
            correlation_id=_TEST_CID,
            source_path="test.py",
            content="class Foo: pass",
            applicable_patterns=[
                ModelApplicablePattern(
                    pattern_id="P001",
                    pattern_signature="Test",
                    domain_id="onex",
                    confidence=0.9,
                )
            ],
        )
        assert r.language == "python"


class TestModelComplianceViolation:
    """Tests for ModelComplianceViolation."""

    def test_valid_violation(self) -> None:
        """Valid violation should be created successfully."""
        v = ModelComplianceViolation(
            pattern_id="P001",
            pattern_signature="Use frozen models",
            description="Model is not frozen",
            severity="major",
            line_reference="line 5",
        )
        assert v.pattern_id == "P001"
        assert v.description == "Model is not frozen"

    def test_default_severity_is_major(self) -> None:
        """Default severity should be 'major'."""
        v = ModelComplianceViolation(
            pattern_id="P001",
            pattern_signature="Test",
            description="Violation",
        )
        assert v.severity == "major"

    def test_null_line_reference(self) -> None:
        """Null line_reference should be allowed."""
        v = ModelComplianceViolation(
            pattern_id="P001",
            pattern_signature="Test",
            description="Violation",
            line_reference=None,
        )
        assert v.line_reference is None


class TestModelComplianceResult:
    """Tests for ModelComplianceResult."""

    def test_successful_compliant_result(self) -> None:
        """Successful compliant result should have no violations."""
        r = ModelComplianceResult(
            success=True,
            violations=[],
            compliant=True,
            confidence=0.95,
            metadata=ModelComplianceMetadata(
                compliance_prompt_version="1.0.0",
            ),
        )
        assert r.success is True
        assert r.compliant is True
        assert r.violations == []

    def test_error_result(self) -> None:
        """Error result should have success=False."""
        r = ModelComplianceResult(
            success=False,
            violations=[],
            compliant=False,
            confidence=0.0,
            metadata=ModelComplianceMetadata(
                status="llm_error",
                message="LLM unavailable",
                compliance_prompt_version="1.0.0",
            ),
        )
        assert r.success is False
        assert r.metadata is not None
        assert r.metadata.status == "llm_error"

    def test_frozen_model(self) -> None:
        """Result model should be frozen (immutable)."""
        r = ModelComplianceResult(
            success=True,
            violations=[],
            compliant=True,
            confidence=0.9,
            metadata=ModelComplianceMetadata(
                compliance_prompt_version="1.0.0",
            ),
        )
        with pytest.raises(ValidationError):
            r.success = False  # type: ignore[misc]


class TestModelComplianceMetadata:
    """Tests for ModelComplianceMetadata."""

    def test_prompt_version_required(self) -> None:
        """compliance_prompt_version is required."""
        with pytest.raises(ValidationError):
            ModelComplianceMetadata()  # type: ignore[call-arg]

    def test_valid_metadata(self) -> None:
        """Valid metadata should be created successfully."""
        m = ModelComplianceMetadata(
            status="completed",
            compliance_prompt_version="1.0.0",
            model_used="test-model",
            processing_time_ms=42.5,
            patterns_checked=3,
        )
        assert m.compliance_prompt_version == "1.0.0"
        assert m.model_used == "test-model"
        assert m.patterns_checked == 3
