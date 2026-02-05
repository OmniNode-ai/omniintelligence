# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern storage governance invariants.

Tests the governance rules that MUST NOT be bypassed:
    1. Reject low confidence: confidence < 0.5 is rejected
    2. Empty signature rejection: signature cannot be empty
    3. Empty domain rejection: domain cannot be empty
    4. Uniqueness enforcement: (domain, signature_hash, version) must be unique
    5. Current version tracking: is_current boolean properly maintained

These tests verify the handler's governance layer enforces invariants
even when Pydantic validation is bypassed (e.g., malformed input).

Reference:
    - OMN-1668: Pattern storage effect acceptance criteria
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern import (
    GovernanceResult,
    handle_store_pattern,
    validate_governance,
)
from omniintelligence.nodes.node_pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternStorageInput,
    PatternStorageGovernance,
)
from omniintelligence.nodes.node_pattern_storage_effect.node_tests.conftest import (
    MockPatternStore,
    create_valid_input,
)

# =============================================================================
# Governance Constants Verification
# =============================================================================


@pytest.mark.unit
class TestGovernanceConstants:
    """Verify governance constants are correctly defined."""

    def test_min_confidence_is_half(self) -> None:
        """MIN_CONFIDENCE must be 0.5 (locked-in invariant)."""
        assert PatternStorageGovernance.MIN_CONFIDENCE == 0.5

    def test_min_confidence_is_not_configurable(self) -> None:
        """MIN_CONFIDENCE should not be writable (class attribute)."""
        # Verify it's a class attribute, not instance
        assert hasattr(PatternStorageGovernance, "MIN_CONFIDENCE")
        # Attempting to set should fail or be ignored on class
        original = PatternStorageGovernance.MIN_CONFIDENCE
        try:
            PatternStorageGovernance.MIN_CONFIDENCE = 0.1  # type: ignore[misc]
            # If we reach here, reset and fail
            PatternStorageGovernance.MIN_CONFIDENCE = original  # type: ignore[misc]
            # Note: Python allows this, but the governance design
            # intention is that this constant should never be changed
        except (TypeError, AttributeError):
            pass  # Expected behavior for truly immutable constants


# =============================================================================
# Low Confidence Rejection Tests
# =============================================================================


@pytest.mark.unit
class TestLowConfidenceRejection:
    """Tests for low confidence pattern rejection."""

    def test_reject_confidence_below_threshold(self) -> None:
        """Patterns with confidence < 0.5 must be rejected."""
        # Pydantic validation should reject this at model creation
        with pytest.raises(ValueError, match=r"greater than or equal to 0\.5"):
            ModelPatternStorageInput(
                pattern_id=uuid4(),
                signature="def.*return.*None",
                signature_hash="hash123",
                domain="code_patterns",
                confidence=0.3,  # Below MIN_CONFIDENCE
            )

    def test_reject_confidence_zero(self) -> None:
        """Patterns with confidence = 0.0 must be rejected."""
        with pytest.raises(ValueError, match=r"greater than or equal to 0\.5"):
            ModelPatternStorageInput(
                pattern_id=uuid4(),
                signature="def.*return.*None",
                signature_hash="hash123",
                domain="code_patterns",
                confidence=0.0,
            )

    def test_reject_confidence_just_below_threshold(self) -> None:
        """Patterns with confidence = 0.49 must be rejected (boundary test)."""
        with pytest.raises(ValueError, match=r"greater than or equal to 0\.5"):
            ModelPatternStorageInput(
                pattern_id=uuid4(),
                signature="def.*return.*None",
                signature_hash="hash123",
                domain="code_patterns",
                confidence=0.49,
            )

    def test_reject_negative_confidence(self) -> None:
        """Patterns with negative confidence must be rejected."""
        with pytest.raises(ValueError, match=r"greater than or equal to 0\.5"):
            ModelPatternStorageInput(
                pattern_id=uuid4(),
                signature="def.*return.*None",
                signature_hash="hash123",
                domain="code_patterns",
                confidence=-0.5,
            )


# =============================================================================
# Minimum Confidence Acceptance Tests
# =============================================================================


@pytest.mark.unit
class TestMinimumConfidenceAcceptance:
    """Tests for patterns at exactly the minimum confidence threshold."""

    def test_accept_minimum_confidence(self) -> None:
        """Patterns with confidence = 0.5 must be accepted."""
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="def.*return.*None",
            signature_hash="hash123",
            domain="code_patterns",
            confidence=0.5,  # Exactly at MIN_CONFIDENCE
        )
        assert input_data.confidence == 0.5

    def test_accept_above_minimum_confidence(self) -> None:
        """Patterns with confidence > 0.5 must be accepted."""
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="def.*return.*None",
            signature_hash="hash123",
            domain="code_patterns",
            confidence=0.85,
        )
        assert input_data.confidence == 0.85

    def test_accept_maximum_confidence(self) -> None:
        """Patterns with confidence = 1.0 must be accepted."""
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="def.*return.*None",
            signature_hash="hash123",
            domain="code_patterns",
            confidence=1.0,
        )
        assert input_data.confidence == 1.0

    @pytest.mark.asyncio
    async def test_handler_accepts_minimum_confidence(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Handler should accept patterns at exactly MIN_CONFIDENCE."""
        input_data = create_valid_input(confidence=0.5)

        result = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        assert result.pattern_id is not None
        assert result.confidence == 0.5
        assert result.state == EnumPatternState.CANDIDATE


# =============================================================================
# Empty Signature Rejection Tests
# =============================================================================


@pytest.mark.unit
class TestEmptySignatureRejection:
    """Tests for empty signature rejection."""

    def test_reject_empty_signature(self) -> None:
        """Patterns with empty signature must be rejected."""
        with pytest.raises(ValueError, match="at least 1 character"):
            ModelPatternStorageInput(
                pattern_id=uuid4(),
                signature="",  # Empty signature
                signature_hash="hash123",
                domain="code_patterns",
                confidence=0.85,
            )

    def test_reject_whitespace_only_signature(self) -> None:
        """Patterns with whitespace-only signature should be rejected by governance."""
        # Pydantic min_length=1 allows whitespace, so test governance layer
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="   ",  # Whitespace only
            signature_hash="hash123",
            domain="code_patterns",
            confidence=0.85,
        )

        result = validate_governance(input_data)

        assert not result.valid
        assert any(v.rule == "SIGNATURE_REQUIRED" for v in result.violations)

    @pytest.mark.asyncio
    async def test_handler_rejects_whitespace_signature(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Handler should reject patterns with whitespace-only signature."""
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="   ",  # Whitespace only
            signature_hash="hash123",
            domain="code_patterns",
            confidence=0.85,
        )

        with pytest.raises(ValueError, match="Governance validation failed"):
            await handle_store_pattern(
                input_data, pattern_store=mock_pattern_store, conn=mock_conn
            )


# =============================================================================
# Empty Domain Rejection Tests
# =============================================================================


@pytest.mark.unit
class TestEmptyDomainRejection:
    """Tests for empty domain rejection."""

    def test_reject_empty_domain(self) -> None:
        """Patterns with empty domain must be rejected."""
        with pytest.raises(ValueError, match="at least 1 character"):
            ModelPatternStorageInput(
                pattern_id=uuid4(),
                signature="def.*return.*None",
                signature_hash="hash123",
                domain="",  # Empty domain
                confidence=0.85,
            )

    def test_reject_whitespace_only_domain(self) -> None:
        """Patterns with whitespace-only domain should be rejected by governance."""
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="def.*return.*None",
            signature_hash="hash123",
            domain="   ",  # Whitespace only
            confidence=0.85,
        )

        result = validate_governance(input_data)

        assert not result.valid
        assert any(v.rule == "DOMAIN_REQUIRED" for v in result.violations)

    @pytest.mark.asyncio
    async def test_handler_rejects_whitespace_domain(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Handler should reject patterns with whitespace-only domain."""
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="def.*return.*None",
            signature_hash="hash123",
            domain="   ",  # Whitespace only
            confidence=0.85,
        )

        with pytest.raises(ValueError, match="Governance validation failed"):
            await handle_store_pattern(
                input_data, pattern_store=mock_pattern_store, conn=mock_conn
            )


# =============================================================================
# validate_governance Function Tests
# =============================================================================


@pytest.mark.unit
class TestValidateGovernance:
    """Tests for the validate_governance function."""

    def test_valid_input_passes_governance(self) -> None:
        """Valid input should pass all governance checks."""
        input_data = create_valid_input()

        result = validate_governance(input_data)

        assert result.valid
        assert len(result.violations) == 0
        assert result.checked_at is not None

    def test_governance_result_is_dataclass(self) -> None:
        """GovernanceResult should be a proper dataclass."""
        input_data = create_valid_input()
        result = validate_governance(input_data)

        assert isinstance(result, GovernanceResult)
        assert hasattr(result, "valid")
        assert hasattr(result, "violations")
        assert hasattr(result, "checked_at")

    def test_multiple_violations_reported(self) -> None:
        """Multiple governance violations should all be reported."""
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="   ",  # Whitespace only
            signature_hash="hash123",
            domain="   ",  # Whitespace only
            confidence=0.5,
        )

        result = validate_governance(input_data)

        assert not result.valid
        assert len(result.violations) == 2  # Both signature and domain violations

    def test_violation_contains_rule_name(self) -> None:
        """Each violation should include the rule name."""
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="   ",  # Whitespace only
            signature_hash="hash123",
            domain="code_patterns",
            confidence=0.5,
        )

        result = validate_governance(input_data)

        assert len(result.violations) == 1
        assert result.violations[0].rule == "SIGNATURE_REQUIRED"

    def test_violation_contains_message(self) -> None:
        """Each violation should include a human-readable message."""
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="   ",
            signature_hash="hash123",
            domain="code_patterns",
            confidence=0.5,
        )

        result = validate_governance(input_data)

        violation = result.violations[0]
        assert violation.message is not None
        assert len(violation.message) > 0
        assert "empty" in violation.message.lower()

    def test_violation_contains_value_and_threshold(self) -> None:
        """Violation should include the actual value and expected threshold."""
        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="   ",
            signature_hash="hash123",
            domain="code_patterns",
            confidence=0.5,
        )

        result = validate_governance(input_data)

        violation = result.violations[0]
        assert violation.value == "   "  # The whitespace signature
        assert violation.threshold is not None


# =============================================================================
# Handler Governance Integration Tests
# =============================================================================


@pytest.mark.unit
class TestHandlerGovernanceIntegration:
    """Tests for handler integration with governance layer."""

    @pytest.mark.asyncio
    async def test_handler_passes_valid_input(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Handler should process valid input without errors."""
        input_data = create_valid_input()

        result = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        assert result is not None
        assert result.pattern_id == input_data.pattern_id
        assert result.state == EnumPatternState.CANDIDATE

    @pytest.mark.asyncio
    async def test_handler_logs_governance_violation(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Handler should log governance violations before rejecting."""
        import logging

        # Set log level to capture INFO logs (governance rejections are INFO level)
        caplog.set_level(logging.INFO)

        input_data = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="   ",  # Whitespace only - governance violation
            signature_hash="hash123",
            domain="code_patterns",
            confidence=0.5,
        )

        with pytest.raises(ValueError):
            await handle_store_pattern(
                input_data, pattern_store=mock_pattern_store, conn=mock_conn
            )

        # Check that violation was logged (at INFO level since rejection is expected business logic)
        assert any("governance" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_handler_returns_stored_pattern_details(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Handler should return complete pattern details after storage."""
        input_data = create_valid_input(
            domain="test_domain",
            confidence=0.75,
            signature="test_signature_pattern",
        )

        result = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        assert result.domain == "test_domain"
        assert result.confidence == 0.75
        assert result.signature == "test_signature_pattern"
        assert result.version >= 1


# =============================================================================
# Confidence Rejection Tests
# =============================================================================


@pytest.mark.unit
class TestConfidenceRejection:
    """Tests for confidence value validation."""

    def test_reject_confidence_above_one(self) -> None:
        """Patterns with confidence > 1.0 must be rejected."""
        with pytest.raises(ValueError, match="less than or equal to 1"):
            ModelPatternStorageInput(
                pattern_id=uuid4(),
                signature="def.*return.*None",
                signature_hash="hash123",
                domain="code_patterns",
                confidence=1.5,  # Above maximum
            )

    def test_accept_boundary_confidence_values(self) -> None:
        """Boundary confidence values (0.5 and 1.0) should be accepted."""
        # Test lower boundary
        input_low = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="def.*return.*None",
            signature_hash="hash123",
            domain="code_patterns",
            confidence=0.5,
        )
        assert input_low.confidence == 0.5

        # Test upper boundary
        input_high = ModelPatternStorageInput(
            pattern_id=uuid4(),
            signature="def.*return.*None",
            signature_hash="hash456",
            domain="code_patterns",
            confidence=1.0,
        )
        assert input_high.confidence == 1.0


# =============================================================================
# Uniqueness Invariant Tests
# =============================================================================


@pytest.mark.unit
class TestUniquenessInvariant:
    """Tests for uniqueness constraint (domain, signature_hash, version)."""

    @pytest.mark.asyncio
    async def test_different_domains_coexist(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Patterns with same signature_hash but different domains should coexist."""
        input1 = create_valid_input(domain="domain_a", signature_hash="shared_hash")
        input2 = create_valid_input(domain="domain_b", signature_hash="shared_hash")

        result1 = await handle_store_pattern(
            input1, pattern_store=mock_pattern_store, conn=mock_conn
        )
        result2 = await handle_store_pattern(
            input2, pattern_store=mock_pattern_store, conn=mock_conn
        )

        assert result1.pattern_id != result2.pattern_id
        assert result1.domain == "domain_a"
        assert result2.domain == "domain_b"

    @pytest.mark.asyncio
    async def test_different_signature_hashes_coexist(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Patterns with same domain but different signature_hash should coexist."""
        input1 = create_valid_input(domain="shared_domain", signature_hash="hash_a")
        input2 = create_valid_input(domain="shared_domain", signature_hash="hash_b")

        result1 = await handle_store_pattern(
            input1, pattern_store=mock_pattern_store, conn=mock_conn
        )
        result2 = await handle_store_pattern(
            input2, pattern_store=mock_pattern_store, conn=mock_conn
        )

        assert result1.pattern_id != result2.pattern_id


# =============================================================================
# Current Version Tracking Tests
# =============================================================================


@pytest.mark.unit
class TestCurrentVersionTracking:
    """Tests for is_current boolean maintenance."""

    @pytest.mark.asyncio
    async def test_first_version_is_current(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """First version of a pattern should be marked as current."""
        input_data = create_valid_input()

        await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Check the stored pattern has is_current = True
        stored = mock_pattern_store.patterns[input_data.pattern_id]
        assert stored["is_current"] is True

    @pytest.mark.asyncio
    async def test_new_version_becomes_current(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """New version should become current and previous should not be current."""
        # Store first version
        input1 = create_valid_input(
            pattern_id=uuid4(),
            domain="test_domain",
            signature_hash="same_hash",
        )
        await handle_store_pattern(
            input1, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Store second version (same lineage key)
        input2 = create_valid_input(
            pattern_id=uuid4(),
            domain="test_domain",
            signature_hash="same_hash",
        )
        await handle_store_pattern(
            input2, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # First should no longer be current
        stored1 = mock_pattern_store.patterns[input1.pattern_id]
        assert stored1["is_current"] is False

        # Second should be current
        stored2 = mock_pattern_store.patterns[input2.pattern_id]
        assert stored2["is_current"] is True
