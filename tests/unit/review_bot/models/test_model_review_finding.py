# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for ModelReviewFinding.

Tests cover OMN-2495 acceptance criteria R1:
- Fields: finding_id (UUID), rule_id, severity, confidence, rationale,
  suggested_fix, patch, file_path, line_number
- frozen=True, extra="ignore", from_attributes=True
- confidence validated to [0.0, 1.0]
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from omniintelligence.review_bot.models.model_review_finding import ModelReviewFinding
from omniintelligence.review_bot.models.model_review_severity import ReviewSeverity


def make_finding(**kwargs: object) -> ModelReviewFinding:
    """Helper to create a valid finding with defaults."""
    defaults: dict[str, object] = {
        "rule_id": "no-bare-except",
        "severity": ReviewSeverity.BLOCKER,
        "confidence": 0.95,
        "rationale": "Bare except catches all exceptions",
        "suggested_fix": "Use specific exception type",
        "file_path": "src/handler.py",
    }
    defaults.update(kwargs)
    return ModelReviewFinding(**defaults)  # type: ignore[arg-type]


class TestModelReviewFindingFields:
    def test_finding_id_is_uuid(self) -> None:
        finding = make_finding()
        assert isinstance(finding.finding_id, uuid.UUID)

    def test_finding_id_auto_generated(self) -> None:
        f1 = make_finding()
        f2 = make_finding()
        assert f1.finding_id != f2.finding_id

    def test_finding_id_can_be_specified(self) -> None:
        specific_id = uuid.uuid4()
        finding = make_finding(finding_id=specific_id)
        assert finding.finding_id == specific_id

    def test_rule_id_field(self) -> None:
        finding = make_finding(rule_id="no-eval")
        assert finding.rule_id == "no-eval"

    def test_severity_field_blocker(self) -> None:
        finding = make_finding(severity=ReviewSeverity.BLOCKER)
        assert finding.severity == ReviewSeverity.BLOCKER

    def test_severity_field_warning(self) -> None:
        finding = make_finding(severity=ReviewSeverity.WARNING)
        assert finding.severity == ReviewSeverity.WARNING

    def test_severity_field_info(self) -> None:
        finding = make_finding(severity=ReviewSeverity.INFO)
        assert finding.severity == ReviewSeverity.INFO

    def test_confidence_field(self) -> None:
        finding = make_finding(confidence=0.75)
        assert finding.confidence == 0.75

    def test_rationale_field(self) -> None:
        finding = make_finding(rationale="This is dangerous")
        assert finding.rationale == "This is dangerous"

    def test_suggested_fix_field(self) -> None:
        finding = make_finding(suggested_fix="Do this instead")
        assert finding.suggested_fix == "Do this instead"

    def test_patch_field_optional_none(self) -> None:
        finding = make_finding()
        assert finding.patch is None

    def test_patch_field_with_value(self) -> None:
        patch = "--- a/src/handler.py\n+++ b/src/handler.py\n@@ -1 +1 @@\n-except:\n+except Exception:"
        finding = make_finding(patch=patch)
        assert finding.patch == patch

    def test_file_path_field(self) -> None:
        finding = make_finding(file_path="src/module/handler.py")
        assert finding.file_path == "src/module/handler.py"

    def test_line_number_optional_none(self) -> None:
        finding = make_finding()
        assert finding.line_number is None

    def test_line_number_with_value(self) -> None:
        finding = make_finding(line_number=42)
        assert finding.line_number == 42

    def test_line_number_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(line_number=0)

    def test_line_number_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(line_number=-1)


class TestModelReviewFindingFrozen:
    def test_finding_is_frozen(self) -> None:
        finding = make_finding()
        with pytest.raises(ValidationError):
            finding.rule_id = "modified"  # type: ignore[misc]

    def test_finding_confidence_immutable(self) -> None:
        finding = make_finding()
        with pytest.raises(ValidationError):
            finding.confidence = 0.5  # type: ignore[misc]


class TestModelReviewFindingExtraFields:
    def test_extra_fields_ignored(self) -> None:
        finding = ModelReviewFinding(
            rule_id="test",
            severity=ReviewSeverity.INFO,
            confidence=0.5,
            rationale="test",
            suggested_fix="test",
            file_path="test.py",
            unknown_field="ignored",  # type: ignore[call-arg]
        )
        assert finding.rule_id == "test"
        assert not hasattr(finding, "unknown_field")


class TestModelReviewFindingConfidenceValidation:
    def test_confidence_zero(self) -> None:
        finding = make_finding(confidence=0.0)
        assert finding.confidence == 0.0

    def test_confidence_one(self) -> None:
        finding = make_finding(confidence=1.0)
        assert finding.confidence == 1.0

    def test_confidence_midpoint(self) -> None:
        finding = make_finding(confidence=0.5)
        assert finding.confidence == 0.5

    def test_confidence_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(confidence=1.01)

    def test_confidence_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(confidence=-0.01)

    def test_confidence_exactly_boundary_values(self) -> None:
        # Exactly at boundaries should pass
        for v in [0.0, 0.01, 0.99, 1.0]:
            finding = make_finding(confidence=v)
            assert finding.confidence == v


class TestModelReviewFindingRequired:
    def test_rule_id_required(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewFinding(
                severity=ReviewSeverity.INFO,
                confidence=0.5,
                rationale="test",
                suggested_fix="test",
                file_path="test.py",
            )

    def test_severity_required(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewFinding(
                rule_id="test",
                confidence=0.5,
                rationale="test",
                suggested_fix="test",
                file_path="test.py",
            )

    def test_confidence_required(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewFinding(
                rule_id="test",
                severity=ReviewSeverity.INFO,
                rationale="test",
                suggested_fix="test",
                file_path="test.py",
            )

    def test_file_path_required(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewFinding(
                rule_id="test",
                severity=ReviewSeverity.INFO,
                confidence=0.5,
                rationale="test",
                suggested_fix="test",
            )
