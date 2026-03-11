# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for PlanReviewFinding and PlanReviewFindingWithConfidence models.

All tests are pure in-memory; no I/O is performed.

Ticket: OMN-3291
"""

from __future__ import annotations

from uuid import UUID

import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_plan_review_category import (
    EnumPlanReviewCategory,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    PlanReviewFinding,
    PlanReviewFindingWithConfidence,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    *,
    category: EnumPlanReviewCategory = EnumPlanReviewCategory.R1_COUNTS,
    location: str = "Step 3",
    severity: str = SEVERITY_WARN,
    source_model: EnumReviewModel = EnumReviewModel.QWEN3_CODER,
    patch: str | None = None,
) -> PlanReviewFinding:
    return PlanReviewFinding.create(
        category=category,
        location=location,
        severity=severity,
        description="Test finding description.",
        suggested_fix="Apply the suggested fix.",
        source_model=source_model,
        patch=patch,
    )


# ---------------------------------------------------------------------------
# PlanReviewFinding
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPlanReviewFindingCreate:
    """Tests for PlanReviewFinding.create() factory method."""

    def test_location_normalized_is_lower_and_stripped(self) -> None:
        """location_normalized must be lower-cased and whitespace-stripped."""
        finding = _make_finding(location="  STEP 3  ")
        assert finding.location_normalized == "step 3"

    def test_location_preserved_raw(self) -> None:
        """location preserves the raw input (not normalized)."""
        finding = _make_finding(location="  STEP 3  ")
        assert finding.location == "  STEP 3  "

    def test_finding_id_is_uuid(self) -> None:
        """finding_id must be a UUID."""
        finding = _make_finding()
        assert isinstance(finding.finding_id, UUID)

    def test_two_findings_have_distinct_ids(self) -> None:
        """Each call to create() produces a unique finding_id."""
        f1 = _make_finding()
        f2 = _make_finding()
        assert f1.finding_id != f2.finding_id

    def test_severity_warn_stored(self) -> None:
        """SEVERITY_WARN value is stored correctly."""
        finding = _make_finding(severity=SEVERITY_WARN)
        assert finding.severity == SEVERITY_WARN

    def test_severity_block_stored(self) -> None:
        """SEVERITY_BLOCK value is stored correctly."""
        finding = _make_finding(severity=SEVERITY_BLOCK)
        assert finding.severity == SEVERITY_BLOCK

    def test_patch_default_is_none(self) -> None:
        """patch defaults to None when not provided."""
        finding = _make_finding()
        assert finding.patch is None

    def test_patch_stored_when_provided(self) -> None:
        """patch is stored when provided."""
        finding = _make_finding(patch="--- a/file.py\n+++ b/file.py")
        assert finding.patch == "--- a/file.py\n+++ b/file.py"

    def test_source_model_stored(self) -> None:
        """source_model is stored correctly."""
        finding = _make_finding(source_model=EnumReviewModel.DEEPSEEK_R1)
        assert finding.source_model == EnumReviewModel.DEEPSEEK_R1

    def test_category_stored(self) -> None:
        """category is stored correctly."""
        finding = _make_finding(category=EnumPlanReviewCategory.R4_INTEGRATION_TRAPS)
        assert finding.category == EnumPlanReviewCategory.R4_INTEGRATION_TRAPS


@pytest.mark.unit
class TestPlanReviewFindingImmutability:
    """PlanReviewFinding is frozen (immutable after creation)."""

    def test_model_is_frozen(self) -> None:
        """Attempting to mutate a field raises ValidationError."""
        from pydantic import ValidationError

        finding = _make_finding()
        with pytest.raises((ValidationError, TypeError)):
            finding.severity = SEVERITY_BLOCK  # type: ignore[misc]

    def test_model_config_frozen(self) -> None:
        """model_config['frozen'] is True."""
        assert PlanReviewFinding.model_config.get("frozen") is True


# ---------------------------------------------------------------------------
# PlanReviewFindingWithConfidence
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPlanReviewFindingWithConfidence:
    """Tests for PlanReviewFindingWithConfidence model."""

    def _make_merged(
        self,
        *,
        confidence: float = 0.75,
        severity: str = SEVERITY_WARN,
        sources: list[EnumReviewModel] | None = None,
    ) -> PlanReviewFindingWithConfidence:
        return PlanReviewFindingWithConfidence(
            category=EnumPlanReviewCategory.R1_COUNTS,
            location="Step 3",
            location_normalized="step 3",
            severity=severity,
            description="Merged finding description.",
            suggested_fix="Apply the fix.",
            confidence=confidence,
            sources=sources or [EnumReviewModel.QWEN3_CODER],
        )

    def test_confidence_stored(self) -> None:
        """confidence is stored as provided."""
        merged = self._make_merged(confidence=0.75)
        assert merged.confidence == pytest.approx(0.75)

    def test_confidence_zero_valid(self) -> None:
        """confidence=0.0 is a valid value."""
        merged = self._make_merged(confidence=0.0)
        assert merged.confidence == pytest.approx(0.0)

    def test_confidence_one_valid(self) -> None:
        """confidence=1.0 is a valid value."""
        merged = self._make_merged(confidence=1.0)
        assert merged.confidence == pytest.approx(1.0)

    def test_confidence_above_one_rejected(self) -> None:
        """confidence > 1.0 is rejected by the model validator."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._make_merged(confidence=1.1)

    def test_confidence_below_zero_rejected(self) -> None:
        """confidence < 0.0 is rejected by the model validator."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._make_merged(confidence=-0.1)

    def test_sources_list_stored(self) -> None:
        """sources list is stored correctly."""
        merged = self._make_merged(
            sources=[EnumReviewModel.QWEN3_CODER, EnumReviewModel.DEEPSEEK_R1]
        )
        assert EnumReviewModel.QWEN3_CODER in merged.sources
        assert EnumReviewModel.DEEPSEEK_R1 in merged.sources

    def test_patch_defaults_to_none(self) -> None:
        """patch is None by default."""
        merged = self._make_merged()
        assert merged.patch is None

    def test_model_is_frozen(self) -> None:
        """PlanReviewFindingWithConfidence is frozen."""
        from pydantic import ValidationError

        merged = self._make_merged()
        with pytest.raises((ValidationError, TypeError)):
            merged.confidence = 0.9  # type: ignore[misc]

    def test_finding_id_is_uuid(self) -> None:
        """finding_id is a UUID."""
        merged = self._make_merged()
        assert isinstance(merged.finding_id, UUID)
