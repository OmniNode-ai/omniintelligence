# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern storage idempotency and versioning.

Tests the idempotency invariants:
    - Same (pattern_id, signature_hash) returns same result without side effects
    - Different pattern_id for same lineage creates new version
    - Immutable history: Never overwrite existing patterns

These tests verify the handler's idempotent behavior and version tracking.

Reference:
    - OMN-1668: Pattern storage effect acceptance criteria
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from omniintelligence.nodes.pattern_storage_effect.handlers.handler_store_pattern import (
    handle_store_pattern,
)
from omniintelligence.nodes.pattern_storage_effect.models import EnumPatternState
from omniintelligence.nodes.pattern_storage_effect.node_tests.conftest import (
    MockPatternStore,
    create_valid_input,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock


# =============================================================================
# Idempotent Storage Tests
# =============================================================================


@pytest.mark.unit
class TestIdempotentStorage:
    """Tests for idempotent pattern storage behavior."""

    @pytest.mark.asyncio
    async def test_same_event_id_returns_same_result(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Same (pattern_id, signature_hash) should return same result."""
        pattern_id = uuid4()
        signature_hash = f"hash_{uuid4().hex[:16]}"

        input_data = create_valid_input(
            pattern_id=pattern_id,
            signature_hash=signature_hash,
        )

        # First call
        result1 = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Second call with same input
        result2 = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Should return same pattern_id
        assert result1.pattern_id == result2.pattern_id
        assert result1.signature_hash == result2.signature_hash

    @pytest.mark.asyncio
    async def test_idempotent_call_no_duplicate_storage(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Idempotent call should not create duplicate pattern in store."""
        pattern_id = uuid4()
        signature_hash = f"hash_{uuid4().hex[:16]}"

        input_data = create_valid_input(
            pattern_id=pattern_id,
            signature_hash=signature_hash,
        )

        # Store pattern twice
        await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )
        await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Should only have one pattern stored
        assert len(mock_pattern_store.patterns) == 1

    @pytest.mark.asyncio
    async def test_idempotent_maintains_original_state(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Idempotent return should maintain original storage state."""
        pattern_id = uuid4()
        signature_hash = f"hash_{uuid4().hex[:16]}"

        input_data = create_valid_input(
            pattern_id=pattern_id,
            signature_hash=signature_hash,
        )

        # First storage
        result1 = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )
        original_stored_at = mock_pattern_store.patterns[pattern_id]["stored_at"]

        # Second call (idempotent)
        result2 = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Original stored_at should not change
        assert mock_pattern_store.patterns[pattern_id]["stored_at"] == original_stored_at

    @pytest.mark.asyncio
    async def test_idempotent_returns_candidate_state(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Idempotent return should show CANDIDATE state for newly stored patterns."""
        pattern_id = uuid4()
        input_data = create_valid_input(pattern_id=pattern_id)

        result1 = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )
        result2 = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Both should show CANDIDATE state
        assert result1.state == EnumPatternState.CANDIDATE
        assert result2.state == EnumPatternState.CANDIDATE


# =============================================================================
# New Version Creation Tests
# =============================================================================


@pytest.mark.unit
class TestNewVersionCreation:
    """Tests for new version creation behavior."""

    @pytest.mark.asyncio
    async def test_different_pattern_id_creates_new_version(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Different pattern_id for same lineage should create new version."""
        signature_hash = f"hash_{uuid4().hex[:16]}"
        domain = "code_patterns"

        # First pattern in lineage
        input1 = create_valid_input(
            pattern_id=uuid4(),
            signature_hash=signature_hash,
            domain=domain,
        )
        result1 = await handle_store_pattern(
            input1, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Second pattern in same lineage (same domain + signature_hash)
        input2 = create_valid_input(
            pattern_id=uuid4(),  # Different pattern_id
            signature_hash=signature_hash,
            domain=domain,
        )
        result2 = await handle_store_pattern(
            input2, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Should have incremented version
        assert result1.version == 1
        assert result2.version == 2

    @pytest.mark.asyncio
    async def test_version_auto_increment(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Versions should auto-increment for same lineage."""
        signature_hash = f"hash_{uuid4().hex[:16]}"
        domain = "test_domain"

        versions_created = []
        for _ in range(5):
            input_data = create_valid_input(
                pattern_id=uuid4(),
                signature_hash=signature_hash,
                domain=domain,
            )
            result = await handle_store_pattern(
                input_data, pattern_store=mock_pattern_store, conn=mock_conn
            )
            versions_created.append(result.version)

        # Versions should be 1, 2, 3, 4, 5
        assert versions_created == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_different_lineages_independent_versions(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Different lineages should have independent version tracking."""
        # First lineage
        input1a = create_valid_input(
            pattern_id=uuid4(),
            signature_hash="lineage_a_hash",
            domain="domain_a",
        )
        result1a = await handle_store_pattern(
            input1a, pattern_store=mock_pattern_store, conn=mock_conn
        )

        input1b = create_valid_input(
            pattern_id=uuid4(),
            signature_hash="lineage_a_hash",
            domain="domain_a",
        )
        result1b = await handle_store_pattern(
            input1b, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Second lineage
        input2a = create_valid_input(
            pattern_id=uuid4(),
            signature_hash="lineage_b_hash",
            domain="domain_b",
        )
        result2a = await handle_store_pattern(
            input2a, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Each lineage should have independent versioning
        assert result1a.version == 1
        assert result1b.version == 2  # Incremented within lineage_a
        assert result2a.version == 1  # Independent lineage_b starts at 1


# =============================================================================
# Immutable History Tests
# =============================================================================


@pytest.mark.unit
class TestImmutableHistory:
    """Tests for immutable history invariant."""

    @pytest.mark.asyncio
    async def test_never_overwrite_existing(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """New version should not overwrite existing pattern data."""
        signature_hash = f"hash_{uuid4().hex[:16]}"
        domain = "code_patterns"

        # First version
        input1 = create_valid_input(
            pattern_id=uuid4(),
            signature_hash=signature_hash,
            domain=domain,
            confidence=0.7,
            signature="original_signature",
        )
        result1 = await handle_store_pattern(
            input1, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Second version with different data
        input2 = create_valid_input(
            pattern_id=uuid4(),
            signature_hash=signature_hash,
            domain=domain,
            confidence=0.9,
            signature="updated_signature",
        )
        result2 = await handle_store_pattern(
            input2, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Both patterns should exist with original data
        stored1 = mock_pattern_store.patterns[result1.pattern_id]
        stored2 = mock_pattern_store.patterns[result2.pattern_id]

        assert stored1["confidence"] == 0.7
        assert stored1["signature"] == "original_signature"
        assert stored2["confidence"] == 0.9
        assert stored2["signature"] == "updated_signature"

    @pytest.mark.asyncio
    async def test_all_versions_preserved(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """All versions should be preserved (not deleted)."""
        signature_hash = f"hash_{uuid4().hex[:16]}"
        domain = "code_patterns"

        pattern_ids = []
        for i in range(3):
            input_data = create_valid_input(
                pattern_id=uuid4(),
                signature_hash=signature_hash,
                domain=domain,
                confidence=0.5 + (i * 0.1),  # 0.5, 0.6, 0.7
            )
            result = await handle_store_pattern(
                input_data, pattern_store=mock_pattern_store, conn=mock_conn
            )
            pattern_ids.append(result.pattern_id)

        # All three patterns should exist
        assert len(mock_pattern_store.patterns) == 3
        for pid in pattern_ids:
            assert pid in mock_pattern_store.patterns


# =============================================================================
# is_current Flag Tests
# =============================================================================


@pytest.mark.unit
class TestIsCurrentFlag:
    """Tests for is_current flag behavior."""

    @pytest.mark.asyncio
    async def test_first_version_is_current(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """First version should have is_current = True."""
        input_data = create_valid_input()

        result = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        stored = mock_pattern_store.patterns[result.pattern_id]
        assert stored["is_current"] is True

    @pytest.mark.asyncio
    async def test_only_latest_is_current(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Only the latest version should be current."""
        signature_hash = f"hash_{uuid4().hex[:16]}"
        domain = "code_patterns"

        # Create three versions
        pattern_ids = []
        for _ in range(3):
            input_data = create_valid_input(
                pattern_id=uuid4(),
                signature_hash=signature_hash,
                domain=domain,
            )
            result = await handle_store_pattern(
                input_data, pattern_store=mock_pattern_store, conn=mock_conn
            )
            pattern_ids.append(result.pattern_id)

        # Check is_current flags
        for i, pid in enumerate(pattern_ids):
            stored = mock_pattern_store.patterns[pid]
            if i == len(pattern_ids) - 1:
                # Last one should be current
                assert stored["is_current"] is True, f"Pattern {i} should be current"
            else:
                # Others should not be current
                assert stored["is_current"] is False, f"Pattern {i} should not be current"

    @pytest.mark.asyncio
    async def test_previous_version_marked_not_current(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """When new version is stored, previous is marked not current."""
        signature_hash = f"hash_{uuid4().hex[:16]}"
        domain = "code_patterns"

        # First version
        input1 = create_valid_input(
            pattern_id=uuid4(),
            signature_hash=signature_hash,
            domain=domain,
        )
        result1 = await handle_store_pattern(
            input1, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Verify first is current
        assert mock_pattern_store.patterns[result1.pattern_id]["is_current"] is True

        # Second version
        input2 = create_valid_input(
            pattern_id=uuid4(),
            signature_hash=signature_hash,
            domain=domain,
        )
        result2 = await handle_store_pattern(
            input2, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # First should no longer be current
        assert mock_pattern_store.patterns[result1.pattern_id]["is_current"] is False
        # Second should be current
        assert mock_pattern_store.patterns[result2.pattern_id]["is_current"] is True


# =============================================================================
# Lineage Key Tests
# =============================================================================


@pytest.mark.unit
class TestLineageKey:
    """Tests for lineage key (domain, signature_hash) behavior."""

    @pytest.mark.asyncio
    async def test_lineage_key_uniquely_identifies_lineage(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Same lineage key should increment version, different key starts fresh.

        Note: The lineage key is (domain, signature). Different signature_hash
        values with the same signature belong to the same lineage.
        """
        # Same lineage (same domain + same signature)
        input1 = create_valid_input(
            pattern_id=uuid4(),
            domain="domain_a",
            signature="pattern_x",
        )
        result1 = await handle_store_pattern(
            input1, pattern_store=mock_pattern_store, conn=mock_conn
        )

        input2 = create_valid_input(
            pattern_id=uuid4(),
            domain="domain_a",
            signature="pattern_x",
        )
        result2 = await handle_store_pattern(
            input2, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Different domain, same signature
        input3 = create_valid_input(
            pattern_id=uuid4(),
            domain="domain_b",
            signature="pattern_x",
        )
        result3 = await handle_store_pattern(
            input3, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Different signature, same domain
        input4 = create_valid_input(
            pattern_id=uuid4(),
            domain="domain_a",
            signature="pattern_y",
        )
        result4 = await handle_store_pattern(
            input4, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Same lineage increments
        assert result1.version == 1
        assert result2.version == 2

        # Different lineages start at 1
        assert result3.version == 1
        assert result4.version == 1

    @pytest.mark.asyncio
    async def test_input_lineage_key_property(self) -> None:
        """ModelPatternStorageInput should expose lineage_key property.

        The lineage_key is (domain, signature), not (domain, signature_hash).
        This allows readable pattern identification and debugging.
        """
        input_data = create_valid_input(
            domain="test_domain",
            signature="test_signature",
        )

        lineage_key = input_data.lineage_key

        assert lineage_key == ("test_domain", "test_signature")


# =============================================================================
# Metadata Preservation Tests
# =============================================================================


@pytest.mark.unit
class TestMetadataPreservation:
    """Tests for metadata preservation in storage."""

    @pytest.mark.asyncio
    async def test_metadata_stored_correctly(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Pattern metadata should be stored correctly."""
        input_data = create_valid_input(
            actor="test_actor",
            source_run_id="run_123",
            tags=["tag1", "tag2"],
            learning_context="unit_test_context",
        )

        result = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        stored = mock_pattern_store.patterns[result.pattern_id]
        assert stored["actor"] == "test_actor"
        assert stored["source_run_id"] == "run_123"
        assert stored["metadata"]["tags"] == ["tag1", "tag2"]
        assert stored["metadata"]["learning_context"] == "unit_test_context"

    @pytest.mark.asyncio
    async def test_correlation_id_stored(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Correlation ID should be stored for tracing."""
        correlation_id = uuid4()
        input_data = create_valid_input(correlation_id=correlation_id)

        result = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        stored = mock_pattern_store.patterns[result.pattern_id]
        assert stored["correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_correlation_id_in_result(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Correlation ID should be included in result event."""
        correlation_id = uuid4()
        input_data = create_valid_input(correlation_id=correlation_id)

        result = await handle_store_pattern(
            input_data, pattern_store=mock_pattern_store, conn=mock_conn
        )

        assert result.correlation_id == correlation_id


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.unit
class TestIdempotencyEdgeCases:
    """Edge case tests for idempotency behavior."""

    @pytest.mark.asyncio
    async def test_rapid_sequential_calls(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Rapid sequential calls with same input should be idempotent."""
        input_data = create_valid_input()

        results = []
        for _ in range(10):
            result = await handle_store_pattern(
                input_data, pattern_store=mock_pattern_store, conn=mock_conn
            )
            results.append(result.pattern_id)

        # All should return same pattern_id
        assert all(pid == results[0] for pid in results)
        # Only one pattern should be stored
        assert len(mock_pattern_store.patterns) == 1

    @pytest.mark.asyncio
    async def test_same_signature_different_confidence(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Same pattern_id but different confidence should still be idempotent."""
        pattern_id = uuid4()
        signature_hash = f"hash_{uuid4().hex[:16]}"

        input1 = create_valid_input(
            pattern_id=pattern_id,
            signature_hash=signature_hash,
            confidence=0.7,
        )
        input2 = create_valid_input(
            pattern_id=pattern_id,
            signature_hash=signature_hash,
            confidence=0.9,  # Different confidence
        )

        result1 = await handle_store_pattern(
            input1, pattern_store=mock_pattern_store, conn=mock_conn
        )
        result2 = await handle_store_pattern(
            input2, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Should be idempotent based on (pattern_id, signature_hash)
        assert result1.pattern_id == result2.pattern_id
        # Original confidence should be preserved
        stored = mock_pattern_store.patterns[pattern_id]
        assert stored["confidence"] == 0.7
