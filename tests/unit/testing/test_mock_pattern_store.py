# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for MockPatternStore signature_hash behavior.

Tests verify that MockPatternStore correctly uses signature_hash for:
1. Pattern identity and idempotency
2. Lineage tracking (version management)
3. Atomic version transitions

Reference:
    - OMN-1780: Pattern storage repository contract
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_pattern_storage_effect.models import EnumPatternState
from omniintelligence.testing import MockPatternStore


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_store() -> MockPatternStore:
    """Create a fresh MockPatternStore for each test."""
    return MockPatternStore()


@pytest.fixture
def sample_pattern_id() -> str:
    """Provide a fixed pattern ID for consistent test assertions."""
    return uuid4()


@pytest.fixture
def sample_signature_hash() -> str:
    """Provide a sample signature hash."""
    return "abc123def456"


@pytest.fixture
def sample_domain() -> str:
    """Provide a sample domain."""
    return "code_patterns"


# =============================================================================
# Test: store_pattern stores signature_hash correctly
# =============================================================================


class TestStorePatternSignatureHash:
    """Tests for store_pattern signature_hash storage behavior."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_store_pattern_stores_signature_hash(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify signature_hash is stored in the patterns dict.

        When storing a pattern:
        1. signature_hash should be persisted in the patterns dict
        2. idempotency_map should use (pattern_id, signature_hash) as key
        """
        # Arrange
        pattern_id = uuid4()
        signature_hash = "test_hash_abc123"
        domain = "code_patterns"

        # Act
        await mock_store.store_pattern(
            pattern_id=pattern_id,
            signature="def.*return.*None",
            signature_hash=signature_hash,
            domain=domain,
            version=1,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Assert - signature_hash stored in patterns dict
        stored_pattern = mock_store.patterns[pattern_id]
        assert stored_pattern["signature_hash"] == signature_hash

        # Assert - idempotency_map uses (pattern_id, signature_hash) tuple
        idempotency_key = (pattern_id, signature_hash)
        assert idempotency_key in mock_store.idempotency_map
        assert mock_store.idempotency_map[idempotency_key] == pattern_id

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_store_pattern_different_hashes_different_keys(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify different signature_hashes create different idempotency keys.

        Two patterns with the same pattern_id but different signature_hashes
        should have separate entries in idempotency_map.
        """
        # Arrange
        pattern_id_1 = uuid4()
        pattern_id_2 = uuid4()
        hash_1 = "hash_version_1"
        hash_2 = "hash_version_2"

        # Act
        await mock_store.store_pattern(
            pattern_id=pattern_id_1,
            signature="def foo():",
            signature_hash=hash_1,
            domain="code_patterns",
            version=1,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
        )
        await mock_store.store_pattern(
            pattern_id=pattern_id_2,
            signature="def bar():",
            signature_hash=hash_2,
            domain="code_patterns",
            version=1,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Assert - both entries exist with distinct keys
        assert (pattern_id_1, hash_1) in mock_store.idempotency_map
        assert (pattern_id_2, hash_2) in mock_store.idempotency_map
        assert len(mock_store.idempotency_map) == 2


# =============================================================================
# Test: check_exists_by_id uses signature_hash
# =============================================================================


class TestCheckExistsByIdSignatureHash:
    """Tests for check_exists_by_id signature_hash lookup behavior."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_exists_by_id_uses_signature_hash(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify check_exists_by_id finds patterns using (pattern_id, signature_hash) tuple.

        The method should return the pattern UUID only when both
        pattern_id and signature_hash match.
        """
        # Arrange
        pattern_id = uuid4()
        signature_hash = "unique_hash_for_test"

        await mock_store.store_pattern(
            pattern_id=pattern_id,
            signature="class.*Pattern:",
            signature_hash=signature_hash,
            domain="architecture",
            version=1,
            confidence=0.90,
            state=EnumPatternState.PROVISIONAL,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Act - check with correct key
        result = await mock_store.check_exists_by_id(
            pattern_id=pattern_id,
            signature_hash=signature_hash,
        )

        # Assert
        assert result == pattern_id

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_exists_by_id_returns_none_for_wrong_hash(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify check_exists_by_id returns None when signature_hash doesn't match.

        Even if pattern_id exists, a mismatched signature_hash should
        return None (no match).
        """
        # Arrange
        pattern_id = uuid4()
        stored_hash = "stored_hash"
        wrong_hash = "different_hash"

        await mock_store.store_pattern(
            pattern_id=pattern_id,
            signature="import.*from",
            signature_hash=stored_hash,
            domain="imports",
            version=1,
            confidence=0.75,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Act - check with wrong hash
        result = await mock_store.check_exists_by_id(
            pattern_id=pattern_id,
            signature_hash=wrong_hash,
        )

        # Assert
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_exists_by_id_returns_none_for_unknown_pattern(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify check_exists_by_id returns None for non-existent patterns."""
        # Arrange - empty store
        unknown_id = uuid4()
        unknown_hash = "nonexistent"

        # Act
        result = await mock_store.check_exists_by_id(
            pattern_id=unknown_id,
            signature_hash=unknown_hash,
        )

        # Assert
        assert result is None


# =============================================================================
# Test: Lineage tracking uses signature_hash
# =============================================================================


class TestLineageTrackingSignatureHash:
    """Tests for version tracking keyed by (domain, signature_hash)."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_latest_version_works_with_signature_hash(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify get_latest_version returns correct version for lineage.

        Lineage is keyed by (domain, signature_hash), so versions
        should be tracked per signature_hash within a domain.
        """
        # Arrange
        signature_hash = "lineage_test_hash"
        domain = "error_handling"

        await mock_store.store_pattern(
            pattern_id=uuid4(),
            signature="try:.*except.*:",
            signature_hash=signature_hash,
            domain=domain,
            version=1,
            confidence=0.80,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Act
        latest_version = await mock_store.get_latest_version(
            domain=domain,
            signature_hash=signature_hash,
        )

        # Assert
        assert latest_version == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lineage_tracks_multiple_versions(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify version tracker updates with each new version.

        Storing patterns with increasing versions should update
        the version tracker for that lineage.
        """
        # Arrange
        signature_hash = "evolving_pattern"
        domain = "logging"

        # Store version 1
        await mock_store.store_pattern(
            pattern_id=uuid4(),
            signature="logger\\.info\\(.*\\)",
            signature_hash=signature_hash,
            domain=domain,
            version=1,
            confidence=0.70,
            state=EnumPatternState.CANDIDATE,
            is_current=False,
            stored_at=datetime.now(UTC),
        )

        # Store version 2
        await mock_store.store_pattern(
            pattern_id=uuid4(),
            signature="logger\\.info\\(.*\\)",
            signature_hash=signature_hash,
            domain=domain,
            version=2,
            confidence=0.80,
            state=EnumPatternState.PROVISIONAL,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Act
        latest_version = await mock_store.get_latest_version(
            domain=domain,
            signature_hash=signature_hash,
        )

        # Assert
        assert latest_version == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_different_hashes_have_independent_lineages(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify different signature_hashes have independent version tracking.

        Two different signature_hashes in the same domain should
        maintain separate version counters.
        """
        # Arrange
        domain = "validation"
        hash_a = "pattern_a_hash"
        hash_b = "pattern_b_hash"

        # Store pattern A at version 3
        await mock_store.store_pattern(
            pattern_id=uuid4(),
            signature="assert.*is not None",
            signature_hash=hash_a,
            domain=domain,
            version=3,
            confidence=0.85,
            state=EnumPatternState.VALIDATED,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Store pattern B at version 1
        await mock_store.store_pattern(
            pattern_id=uuid4(),
            signature="if.*is None:.*raise",
            signature_hash=hash_b,
            domain=domain,
            version=1,
            confidence=0.75,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Act
        version_a = await mock_store.get_latest_version(
            domain=domain, signature_hash=hash_a
        )
        version_b = await mock_store.get_latest_version(
            domain=domain, signature_hash=hash_b
        )

        # Assert - independent version tracking
        assert version_a == 3
        assert version_b == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_latest_version_returns_none_for_unknown_lineage(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify get_latest_version returns None for non-existent lineage."""
        # Arrange - empty store

        # Act
        result = await mock_store.get_latest_version(
            domain="unknown_domain",
            signature_hash="unknown_hash",
        )

        # Assert
        assert result is None


# =============================================================================
# Test: store_with_version_transition atomic updates
# =============================================================================


class TestStoreWithVersionTransition:
    """Tests for atomic version transition behavior."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_store_with_version_transition_updates_correctly(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify atomic transition sets old version is_current=False and new version is_current=True.

        The atomic transition should:
        1. Set previous version's is_current to False
        2. Store new version with is_current=True
        3. Increment atomic_transitions_count
        """
        # Arrange
        signature_hash = "transition_test_hash"
        domain = "async_patterns"

        old_pattern_id = uuid4()
        new_pattern_id = uuid4()

        # Store initial version
        await mock_store.store_pattern(
            pattern_id=old_pattern_id,
            signature="async def.*await",
            signature_hash=signature_hash,
            domain=domain,
            version=1,
            confidence=0.80,
            state=EnumPatternState.PROVISIONAL,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Verify initial state
        assert mock_store.patterns[old_pattern_id]["is_current"] is True
        assert mock_store._atomic_transitions_count == 0

        # Act - atomic transition
        await mock_store.store_with_version_transition(
            pattern_id=new_pattern_id,
            signature="async def.*await",
            signature_hash=signature_hash,
            domain=domain,
            version=2,
            confidence=0.90,
            state=EnumPatternState.VALIDATED,
            is_current=True,  # This is ignored - always True for atomic transition
            stored_at=datetime.now(UTC),
        )

        # Assert - old version is_current = False
        assert mock_store.patterns[old_pattern_id]["is_current"] is False

        # Assert - new version is_current = True
        assert mock_store.patterns[new_pattern_id]["is_current"] is True

        # Assert - atomic_transitions_count incremented
        assert mock_store._atomic_transitions_count == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_store_with_version_transition_only_affects_matching_lineage(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify atomic transition only affects patterns with matching domain and signature_hash.

        Patterns with different signature_hashes should not be affected
        by the transition.
        """
        # Arrange
        domain = "concurrency"
        hash_target = "target_pattern"
        hash_unrelated = "unrelated_pattern"

        target_old_id = uuid4()
        unrelated_id = uuid4()
        target_new_id = uuid4()

        # Store target pattern (will be transitioned)
        await mock_store.store_pattern(
            pattern_id=target_old_id,
            signature="with.*Lock\\(\\):",
            signature_hash=hash_target,
            domain=domain,
            version=1,
            confidence=0.85,
            state=EnumPatternState.PROVISIONAL,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Store unrelated pattern (should not be affected)
        await mock_store.store_pattern(
            pattern_id=unrelated_id,
            signature="threading\\.Thread\\(",
            signature_hash=hash_unrelated,
            domain=domain,
            version=1,
            confidence=0.75,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Act - transition only target pattern
        await mock_store.store_with_version_transition(
            pattern_id=target_new_id,
            signature="with.*Lock\\(\\):",
            signature_hash=hash_target,
            domain=domain,
            version=2,
            confidence=0.92,
            state=EnumPatternState.VALIDATED,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Assert - unrelated pattern unchanged
        assert mock_store.patterns[unrelated_id]["is_current"] is True

        # Assert - target pattern transitioned
        assert mock_store.patterns[target_old_id]["is_current"] is False
        assert mock_store.patterns[target_new_id]["is_current"] is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_multiple_atomic_transitions_increment_counter(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify atomic_transitions_count increments for each transition."""
        # Arrange
        signature_hash = "counter_test"
        domain = "testing"

        # Act - perform 3 atomic transitions
        for version in range(1, 4):
            await mock_store.store_with_version_transition(
                pattern_id=uuid4(),
                signature="test pattern",
                signature_hash=signature_hash,
                domain=domain,
                version=version,
                confidence=0.80,
                state=EnumPatternState.PROVISIONAL,
                is_current=True,
                stored_at=datetime.now(UTC),
            )

        # Assert
        assert mock_store._atomic_transitions_count == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_store_with_version_transition_updates_version_tracker(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify atomic transition updates the version tracker correctly."""
        # Arrange
        signature_hash = "version_tracking_test"
        domain = "performance"

        # Store initial version
        await mock_store.store_pattern(
            pattern_id=uuid4(),
            signature="@cache",
            signature_hash=signature_hash,
            domain=domain,
            version=1,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Act - atomic transition to version 2
        await mock_store.store_with_version_transition(
            pattern_id=uuid4(),
            signature="@cache",
            signature_hash=signature_hash,
            domain=domain,
            version=2,
            confidence=0.90,
            state=EnumPatternState.PROVISIONAL,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        # Assert - version tracker updated
        latest = await mock_store.get_latest_version(
            domain=domain,
            signature_hash=signature_hash,
        )
        assert latest == 2


# =============================================================================
# Test: reset() clears all state
# =============================================================================


class TestMockPatternStoreReset:
    """Tests for MockPatternStore.reset() method."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reset_clears_all_state(
        self,
        mock_store: MockPatternStore,
    ) -> None:
        """Verify reset() clears patterns, idempotency_map, version_tracker, and counter."""
        # Arrange - populate the store
        await mock_store.store_with_version_transition(
            pattern_id=uuid4(),
            signature="test",
            signature_hash="test_hash",
            domain="test_domain",
            version=1,
            confidence=0.85,
            state=EnumPatternState.CANDIDATE,
            is_current=True,
            stored_at=datetime.now(UTC),
        )

        assert len(mock_store.patterns) > 0
        assert len(mock_store.idempotency_map) > 0
        assert len(mock_store._version_tracker) > 0
        assert mock_store._atomic_transitions_count > 0

        # Act
        mock_store.reset()

        # Assert
        assert len(mock_store.patterns) == 0
        assert len(mock_store.idempotency_map) == 0
        assert len(mock_store._version_tracker) == 0
        assert mock_store._atomic_transitions_count == 0
