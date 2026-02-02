# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern storage idempotency and versioning.

Tests the idempotency invariants:
    - Same (pattern_id, signature_hash) returns same result without side effects
    - Different pattern_id for same lineage creates new version
    - Immutable history: Never overwrite existing patterns

Lineage is defined by (domain, signature_hash).
Idempotency key is (pattern_id, signature_hash).

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

        Note: The lineage key is (domain, signature_hash). Different signature
        values with the same signature_hash belong to the same lineage.
        """
        # Same lineage (same domain + same signature_hash)
        input1 = create_valid_input(
            pattern_id=uuid4(),
            domain="domain_a",
            signature_hash="hash_x",
        )
        result1 = await handle_store_pattern(
            input1, pattern_store=mock_pattern_store, conn=mock_conn
        )

        input2 = create_valid_input(
            pattern_id=uuid4(),
            domain="domain_a",
            signature_hash="hash_x",
        )
        result2 = await handle_store_pattern(
            input2, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Different domain, same signature_hash
        input3 = create_valid_input(
            pattern_id=uuid4(),
            domain="domain_b",
            signature_hash="hash_x",
        )
        result3 = await handle_store_pattern(
            input3, pattern_store=mock_pattern_store, conn=mock_conn
        )

        # Different signature_hash, same domain
        input4 = create_valid_input(
            pattern_id=uuid4(),
            domain="domain_a",
            signature_hash="hash_y",
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

        The lineage_key is (domain, signature_hash) for stable identification.
        This allows consistent pattern identification across signature variations.
        """
        input_data = create_valid_input(
            domain="test_domain",
            signature_hash="test_hash",
        )

        lineage_key = input_data.lineage_key

        assert lineage_key == ("test_domain", "test_hash")


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


# =============================================================================
# Atomic Version Transition Tests
# =============================================================================


@pytest.mark.unit
class TestAtomicVersionTransition:
    """Tests for atomic version transition via store_with_version_transition.

    The store_with_version_transition method combines set_previous_not_current
    and store_pattern into a single atomic operation, preventing the invariant
    violation where a lineage has ZERO current versions.

    These tests verify the MockPatternStore implementation which serves as:
    1. A test double for unit testing
    2. A specification for production implementations
    """

    @pytest.mark.asyncio
    async def test_atomic_transition_sets_previous_not_current(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Atomic transition should set previous versions as not current."""
        from datetime import UTC, datetime

        domain = "code_patterns"
        signature = "def.*return.*None"
        signature_hash = f"hash_{uuid4().hex[:16]}"

        # Store first version using store_pattern (version 1)
        v1_id = uuid4()
        await mock_pattern_store.store_pattern(
            pattern_id=v1_id,
            signature=signature,
            signature_hash=signature_hash,
            domain=domain,
            version=1,
            confidence=0.7,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
            conn=mock_conn,
        )

        # Verify v1 is current
        assert mock_pattern_store.patterns[v1_id]["is_current"] is True

        # Store second version using atomic transition
        v2_id = uuid4()
        await mock_pattern_store.store_with_version_transition(
            pattern_id=v2_id,
            signature=signature,
            signature_hash=signature_hash,
            domain=domain,
            version=2,
            confidence=0.8,
            state=EnumPatternState.CANDIDATE,
            is_current=True,  # Ignored by atomic operation
            stored_at=datetime.now(UTC),
            conn=mock_conn,
        )

        # Verify v1 is NO LONGER current (atomic transition updated it)
        assert mock_pattern_store.patterns[v1_id]["is_current"] is False
        # Verify v2 IS current
        assert mock_pattern_store.patterns[v2_id]["is_current"] is True

    @pytest.mark.asyncio
    async def test_atomic_transition_returns_correct_pattern_id(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Atomic transition should return the correct pattern_id."""
        from datetime import UTC, datetime

        pattern_id = uuid4()

        result_id = await mock_pattern_store.store_with_version_transition(
            pattern_id=pattern_id,
            signature="test_signature",
            signature_hash="test_hash",
            domain="test_domain",
            version=2,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
            conn=mock_conn,
        )

        # Should return the same pattern_id that was passed in
        assert result_id == pattern_id
        # Pattern should be stored with that ID
        assert pattern_id in mock_pattern_store.patterns

    @pytest.mark.asyncio
    async def test_atomic_transition_tracks_operation_count(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Atomic transition should track that it was called (for test verification)."""
        from datetime import UTC, datetime

        # Initially zero atomic transitions
        assert mock_pattern_store._atomic_transitions_count == 0

        # Perform atomic transition
        await mock_pattern_store.store_with_version_transition(
            pattern_id=uuid4(),
            signature="test_signature",
            signature_hash="test_hash",
            domain="test_domain",
            version=2,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
            conn=mock_conn,
        )

        # Should have tracked one atomic transition
        assert mock_pattern_store._atomic_transitions_count == 1

        # Perform another atomic transition
        await mock_pattern_store.store_with_version_transition(
            pattern_id=uuid4(),
            signature="test_signature_2",
            signature_hash="test_hash_2",
            domain="test_domain",
            version=2,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
            conn=mock_conn,
        )

        # Should have tracked two atomic transitions
        assert mock_pattern_store._atomic_transitions_count == 2

    @pytest.mark.asyncio
    async def test_atomic_transition_updates_version_tracker(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Atomic transition should update the version tracker."""
        from datetime import UTC, datetime

        domain = "code_patterns"
        signature = "def.*return.*None"
        signature_hash = "test_hash"

        await mock_pattern_store.store_with_version_transition(
            pattern_id=uuid4(),
            signature=signature,
            signature_hash=signature_hash,
            domain=domain,
            version=5,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
            conn=mock_conn,
        )

        # Version tracker should be updated
        latest = await mock_pattern_store.get_latest_version(
            domain=domain,
            signature_hash=signature_hash,
            conn=mock_conn,
        )
        assert latest == 5

    @pytest.mark.asyncio
    async def test_atomic_transition_updates_idempotency_map(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Atomic transition should update idempotency map for future checks."""
        from datetime import UTC, datetime

        pattern_id = uuid4()
        signature = "test_signature"
        signature_hash = "test_hash"

        await mock_pattern_store.store_with_version_transition(
            pattern_id=pattern_id,
            signature=signature,
            signature_hash=signature_hash,
            domain="test_domain",
            version=2,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
            conn=mock_conn,
        )

        # Idempotency check should find it
        existing = await mock_pattern_store.check_exists_by_id(
            pattern_id=pattern_id,
            signature_hash=signature_hash,
            conn=mock_conn,
        )
        assert existing == pattern_id

    @pytest.mark.asyncio
    async def test_atomic_transition_handles_multiple_previous_versions(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Atomic transition should set ALL previous versions as not current."""
        from datetime import UTC, datetime

        domain = "code_patterns"
        signature = "def.*return.*None"
        signature_hash = "test_hash"

        # Store versions 1, 2, 3 using store_pattern
        # (simulating a scenario where is_current wasn't managed correctly)
        v_ids = []
        for v in range(1, 4):
            v_id = uuid4()
            await mock_pattern_store.store_pattern(
                pattern_id=v_id,
                signature=signature,
                signature_hash=signature_hash,
                domain=domain,
                version=v,
                confidence=0.7,
                state=EnumPatternState.CANDIDATE,
                is_current=True,  # Intentionally set all to current (incorrect state)
                stored_at=datetime.now(UTC),
                conn=mock_conn,
            )
            v_ids.append(v_id)

        # All three are marked current (bad state for testing)
        for v_id in v_ids:
            assert mock_pattern_store.patterns[v_id]["is_current"] is True

        # Now store version 4 using atomic transition
        v4_id = uuid4()
        await mock_pattern_store.store_with_version_transition(
            pattern_id=v4_id,
            signature=signature,
            signature_hash=signature_hash,
            domain=domain,
            version=4,
            confidence=0.9,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
            conn=mock_conn,
        )

        # ALL previous versions should now be not current
        for v_id in v_ids:
            assert (
                mock_pattern_store.patterns[v_id]["is_current"] is False
            ), f"Version {mock_pattern_store.patterns[v_id]['version']} should not be current"

        # Only v4 should be current
        assert mock_pattern_store.patterns[v4_id]["is_current"] is True

    @pytest.mark.asyncio
    async def test_atomic_transition_preserves_pattern_data(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Atomic transition should store all pattern data correctly."""
        from datetime import UTC, datetime

        pattern_id = uuid4()
        correlation_id = uuid4()
        stored_at = datetime.now(UTC)
        metadata = {
            "tags": ["test", "unit"],
            "learning_context": "unit_test",
            "additional_attributes": {"key": "value"},
        }

        await mock_pattern_store.store_with_version_transition(
            pattern_id=pattern_id,
            signature="test_signature",
            signature_hash="test_hash",
            domain="test_domain",
            version=2,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=stored_at,
            actor="test_actor",
            source_run_id="run_123",
            correlation_id=correlation_id,
            metadata=metadata,
            conn=mock_conn,
        )

        stored = mock_pattern_store.patterns[pattern_id]
        assert stored["signature"] == "test_signature"
        assert stored["signature_hash"] == "test_hash"
        assert stored["domain"] == "test_domain"
        assert stored["version"] == 2
        assert stored["confidence"] == 0.85
        assert stored["state"] == EnumPatternState.CANDIDATE
        assert stored["is_current"] is True
        assert stored["stored_at"] == stored_at
        assert stored["actor"] == "test_actor"
        assert stored["source_run_id"] == "run_123"
        assert stored["correlation_id"] == correlation_id
        assert stored["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_reset_clears_atomic_transition_count(
        self,
        mock_pattern_store: MockPatternStore,
        mock_conn: MagicMock,
    ) -> None:
        """Reset should clear the atomic transition count."""
        from datetime import UTC, datetime

        # Perform an atomic transition
        await mock_pattern_store.store_with_version_transition(
            pattern_id=uuid4(),
            signature="test_signature",
            signature_hash="test_hash",
            domain="test_domain",
            version=2,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
            conn=mock_conn,
        )

        assert mock_pattern_store._atomic_transitions_count == 1

        # Reset should clear it
        mock_pattern_store.reset()

        assert mock_pattern_store._atomic_transitions_count == 0
        assert len(mock_pattern_store.patterns) == 0
