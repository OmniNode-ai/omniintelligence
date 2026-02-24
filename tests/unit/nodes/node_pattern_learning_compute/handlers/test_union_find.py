# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for Union-Find (Disjoint-Set) data structure.

This module tests the UnionFind class used for deterministic clustering:
    - Initialization with various sizes
    - find(): Root discovery with path compression
    - union(): Deterministic set merging (smaller index becomes root)
    - connected(): Connectivity checking
    - components(): Component grouping
    - Error handling for invalid inputs
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_pattern_learning_compute.handlers.union_find import (
    UnionFind,
)

# =============================================================================
# Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestUnionFindInit:
    """Tests for UnionFind initialization."""

    # -------------------------------------------------------------------------
    # Valid Initialization
    # -------------------------------------------------------------------------

    def test_init_creates_singletons(self) -> None:
        """Each element starts as its own root (singleton set)."""
        uf = UnionFind(5)

        # Each element should be its own root initially
        for i in range(5):
            assert uf.find(i) == i

    def test_init_zero_elements(self) -> None:
        """Zero elements should create empty UnionFind."""
        uf = UnionFind(0)
        assert uf.n == 0

    def test_init_single_element(self) -> None:
        """Single element UnionFind should work correctly."""
        uf = UnionFind(1)
        assert uf.n == 1
        assert uf.find(0) == 0

    def test_init_large_size(self) -> None:
        """Large UnionFind should initialize correctly."""
        uf = UnionFind(10000)
        assert uf.n == 10000

        # Spot check some elements
        assert uf.find(0) == 0
        assert uf.find(5000) == 5000
        assert uf.find(9999) == 9999

    def test_n_property_returns_size(self) -> None:
        """The n property should return the number of elements."""
        assert UnionFind(0).n == 0
        assert UnionFind(1).n == 1
        assert UnionFind(100).n == 100

    # -------------------------------------------------------------------------
    # Invalid Initialization
    # -------------------------------------------------------------------------

    def test_init_negative_raises_error(self) -> None:
        """Negative n should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            UnionFind(-1)

        assert "non-negative" in str(exc_info.value)
        assert "-1" in str(exc_info.value)

    def test_init_large_negative_raises_error(self) -> None:
        """Large negative n should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            UnionFind(-1000)

        assert "non-negative" in str(exc_info.value)


# =============================================================================
# find() Tests
# =============================================================================


@pytest.mark.unit
class TestUnionFindFind:
    """Tests for the find() method."""

    # -------------------------------------------------------------------------
    # Basic find() Behavior
    # -------------------------------------------------------------------------

    def test_find_returns_self_initially(self) -> None:
        """find(x) should return x before any union operations."""
        uf = UnionFind(10)

        for i in range(10):
            assert uf.find(i) == i

    def test_find_returns_root_after_union(self) -> None:
        """find() should return the root after union operations."""
        uf = UnionFind(5)
        uf.union(0, 2)

        # Both should have root 0 (smaller index)
        assert uf.find(0) == 0
        assert uf.find(2) == 0

    def test_find_unchanged_elements(self) -> None:
        """find() on elements not in any union should still return self."""
        uf = UnionFind(5)
        uf.union(0, 1)

        # Elements 2, 3, 4 should still be their own roots
        assert uf.find(2) == 2
        assert uf.find(3) == 3
        assert uf.find(4) == 4

    # -------------------------------------------------------------------------
    # Path Compression Tests
    # -------------------------------------------------------------------------

    def test_path_compression_works(self) -> None:
        """Path compression should flatten the tree structure.

        After find(), nodes on the path should point directly to root.
        """
        uf = UnionFind(4)

        # Build a chain: 3 -> 2 -> 1 -> 0
        uf.union(0, 1)  # 1's root becomes 0
        uf.union(1, 2)  # 2's root becomes 0 (via 1)
        uf.union(2, 3)  # 3's root becomes 0 (via 2, 1)

        # Find on 3 should trigger path compression
        root = uf.find(3)
        assert root == 0

        # After path compression, 3 should point directly to 0
        # We can verify by checking that subsequent finds are direct
        # (The internal _parent[3] should now be 0)
        # Since we can't directly access _parent, we verify behavior is consistent
        assert uf.find(3) == 0

    def test_path_compression_multiple_chains(self) -> None:
        """Path compression should work across multiple chains."""
        uf = UnionFind(6)

        # Create two chains
        uf.union(0, 1)
        uf.union(1, 2)  # Chain: 2 -> 1 -> 0

        uf.union(3, 4)
        uf.union(4, 5)  # Chain: 5 -> 4 -> 3

        # Verify both chains work correctly
        assert uf.find(2) == 0
        assert uf.find(5) == 3

    # -------------------------------------------------------------------------
    # Error Handling
    # -------------------------------------------------------------------------

    def test_find_negative_index_raises_error(self) -> None:
        """Negative index should raise IndexError."""
        uf = UnionFind(5)

        with pytest.raises(IndexError) as exc_info:
            uf.find(-1)

        assert "out of bounds" in str(exc_info.value)
        assert "-1" in str(exc_info.value)

    def test_find_out_of_bounds_raises_error(self) -> None:
        """Index >= n should raise IndexError."""
        uf = UnionFind(5)

        with pytest.raises(IndexError) as exc_info:
            uf.find(5)

        assert "out of bounds" in str(exc_info.value)
        assert "5" in str(exc_info.value)

    def test_find_far_out_of_bounds_raises_error(self) -> None:
        """Index far beyond n should raise IndexError."""
        uf = UnionFind(5)

        with pytest.raises(IndexError) as exc_info:
            uf.find(1000)

        assert "out of bounds" in str(exc_info.value)

    def test_find_on_empty_raises_error(self) -> None:
        """Any find() on empty UnionFind should raise IndexError."""
        uf = UnionFind(0)

        with pytest.raises(IndexError):
            uf.find(0)


# =============================================================================
# union() Tests
# =============================================================================


@pytest.mark.unit
class TestUnionFindUnion:
    """Tests for the union() method."""

    # -------------------------------------------------------------------------
    # Basic union() Behavior
    # -------------------------------------------------------------------------

    def test_union_merges_sets(self) -> None:
        """union() should merge two elements into the same set."""
        uf = UnionFind(5)
        uf.union(1, 3)

        assert uf.find(1) == uf.find(3)

    def test_union_multiple_elements(self) -> None:
        """Multiple union() calls should merge all elements."""
        uf = UnionFind(5)
        uf.union(0, 1)
        uf.union(1, 2)
        uf.union(2, 3)
        uf.union(3, 4)

        # All should have the same root
        root = uf.find(0)
        for i in range(5):
            assert uf.find(i) == root

    def test_union_same_element_is_noop(self) -> None:
        """union(x, x) should be a no-op."""
        uf = UnionFind(5)
        uf.union(2, 2)

        # Element 2 should still be its own root
        assert uf.find(2) == 2

    def test_union_already_connected_is_noop(self) -> None:
        """union() on already-connected elements should be a no-op."""
        uf = UnionFind(5)
        uf.union(0, 1)
        uf.union(1, 2)

        # 0 and 2 are already connected via 1
        root_before = uf.find(0)
        uf.union(0, 2)
        root_after = uf.find(0)

        assert root_before == root_after

    # -------------------------------------------------------------------------
    # Determinism Tests (Smaller Index Becomes Root)
    # -------------------------------------------------------------------------

    def test_union_determinism_smaller_root(self) -> None:
        """The smaller index should always become the root."""
        uf = UnionFind(5)
        uf.union(3, 1)  # 1 < 3, so 1 becomes root

        assert uf.find(3) == 1
        assert uf.find(1) == 1

    def test_union_determinism_order_independent(self) -> None:
        """union(a, b) should produce same result as union(b, a)."""
        uf1 = UnionFind(5)
        uf1.union(3, 1)

        uf2 = UnionFind(5)
        uf2.union(1, 3)

        # Both should have 1 as root
        assert uf1.find(3) == 1
        assert uf2.find(3) == 1

    def test_union_determinism_chain(self) -> None:
        """Chain of unions should always produce smallest index as root."""
        uf = UnionFind(5)
        uf.union(4, 3)  # root = 3
        uf.union(3, 2)  # root = 2
        uf.union(2, 1)  # root = 1
        uf.union(1, 0)  # root = 0

        # All should have root 0
        for i in range(5):
            assert uf.find(i) == 0

    def test_union_determinism_reverse_order(self) -> None:
        """Same unions in reverse order should produce same result."""
        uf = UnionFind(5)
        uf.union(0, 1)
        uf.union(1, 2)
        uf.union(2, 3)
        uf.union(3, 4)

        # All should have root 0
        for i in range(5):
            assert uf.find(i) == 0

    def test_union_determinism_random_order(self) -> None:
        """Random union order should still produce deterministic result."""
        uf = UnionFind(5)
        uf.union(2, 4)  # root = 2
        uf.union(1, 3)  # root = 1
        uf.union(2, 1)  # merge groups, root = 1

        # Elements 1, 2, 3, 4 should all have root 1
        assert uf.find(1) == 1
        assert uf.find(2) == 1
        assert uf.find(3) == 1
        assert uf.find(4) == 1

        # Element 0 should still be its own root
        assert uf.find(0) == 0

    # -------------------------------------------------------------------------
    # Error Handling
    # -------------------------------------------------------------------------

    def test_union_first_out_of_bounds_raises_error(self) -> None:
        """union() with first index out of bounds should raise IndexError."""
        uf = UnionFind(5)

        with pytest.raises(IndexError):
            uf.union(10, 2)

    def test_union_second_out_of_bounds_raises_error(self) -> None:
        """union() with second index out of bounds should raise IndexError."""
        uf = UnionFind(5)

        with pytest.raises(IndexError):
            uf.union(2, 10)

    def test_union_negative_index_raises_error(self) -> None:
        """union() with negative index should raise IndexError."""
        uf = UnionFind(5)

        with pytest.raises(IndexError):
            uf.union(-1, 2)


# =============================================================================
# connected() Tests
# =============================================================================


@pytest.mark.unit
class TestUnionFindConnected:
    """Tests for the connected() method."""

    # -------------------------------------------------------------------------
    # Basic connected() Behavior
    # -------------------------------------------------------------------------

    def test_connected_same_element(self) -> None:
        """An element is always connected to itself."""
        uf = UnionFind(5)
        assert uf.connected(2, 2) is True

    def test_connected_after_union(self) -> None:
        """connected() should return True after union()."""
        uf = UnionFind(5)
        uf.union(0, 4)

        assert uf.connected(0, 4) is True

    def test_connected_different_sets(self) -> None:
        """connected() should return False for elements in different sets."""
        uf = UnionFind(5)

        assert uf.connected(0, 1) is False
        assert uf.connected(2, 4) is False

    def test_connected_transitive(self) -> None:
        """Connectivity should be transitive through union chains."""
        uf = UnionFind(5)
        uf.union(0, 1)
        uf.union(1, 2)

        # 0 and 2 should be connected through 1
        assert uf.connected(0, 2) is True

    def test_connected_symmetry(self) -> None:
        """connected(a, b) should equal connected(b, a)."""
        uf = UnionFind(5)
        uf.union(0, 3)

        assert uf.connected(0, 3) == uf.connected(3, 0)

    def test_connected_separate_groups(self) -> None:
        """Elements in separate groups should not be connected."""
        uf = UnionFind(6)
        uf.union(0, 1)
        uf.union(1, 2)  # Group 1: {0, 1, 2}

        uf.union(3, 4)
        uf.union(4, 5)  # Group 2: {3, 4, 5}

        # Within group connections
        assert uf.connected(0, 2) is True
        assert uf.connected(3, 5) is True

        # Cross-group should not be connected
        assert uf.connected(0, 3) is False
        assert uf.connected(2, 4) is False

    # -------------------------------------------------------------------------
    # Error Handling
    # -------------------------------------------------------------------------

    def test_connected_out_of_bounds_raises_error(self) -> None:
        """connected() with out of bounds index should raise IndexError."""
        uf = UnionFind(5)

        with pytest.raises(IndexError):
            uf.connected(0, 10)

        with pytest.raises(IndexError):
            uf.connected(10, 0)


# =============================================================================
# components() Tests
# =============================================================================


@pytest.mark.unit
class TestUnionFindComponents:
    """Tests for the components() method."""

    # -------------------------------------------------------------------------
    # Basic components() Behavior
    # -------------------------------------------------------------------------

    def test_components_all_singletons(self) -> None:
        """Without any unions, each element should be its own component."""
        uf = UnionFind(5)
        components = uf.components()

        assert len(components) == 5
        for i in range(5):
            assert i in components
            assert components[i] == [i]

    def test_components_single_group(self) -> None:
        """All elements in one group should produce one component."""
        uf = UnionFind(5)
        uf.union(0, 1)
        uf.union(1, 2)
        uf.union(2, 3)
        uf.union(3, 4)

        components = uf.components()

        assert len(components) == 1
        assert 0 in components  # Root is 0
        assert components[0] == [0, 1, 2, 3, 4]

    def test_components_multiple_groups(self) -> None:
        """Multiple groups should produce multiple components."""
        uf = UnionFind(6)
        uf.union(0, 1)  # Group 1: {0, 1}
        uf.union(2, 3)  # Group 2: {2, 3}
        # 4 and 5 are singletons

        components = uf.components()

        assert len(components) == 4
        assert components[0] == [0, 1]
        assert components[2] == [2, 3]
        assert components[4] == [4]
        assert components[5] == [5]

    def test_components_returns_all_groups(self) -> None:
        """components() should return all groups including singletons."""
        uf = UnionFind(4)
        uf.union(1, 3)

        components = uf.components()

        # Should have 3 components: {0}, {1, 3}, {2}
        assert len(components) == 3
        assert 0 in components
        assert 1 in components
        assert 2 in components

    def test_components_empty_union_find(self) -> None:
        """Empty UnionFind should return empty dict."""
        uf = UnionFind(0)
        components = uf.components()

        assert components == {}

    # -------------------------------------------------------------------------
    # Determinism Tests
    # -------------------------------------------------------------------------

    def test_components_sorted_members(self) -> None:
        """Member lists should be sorted for determinism."""
        uf = UnionFind(5)
        uf.union(4, 2)
        uf.union(2, 0)

        components = uf.components()

        # Members should be sorted: [0, 2, 4]
        assert components[0] == [0, 2, 4]

    def test_components_deterministic_output(self) -> None:
        """Same unions should produce same components regardless of order."""
        uf1 = UnionFind(5)
        uf1.union(0, 2)
        uf1.union(2, 4)

        uf2 = UnionFind(5)
        uf2.union(4, 2)
        uf2.union(2, 0)

        assert uf1.components() == uf2.components()

    def test_components_root_is_key(self) -> None:
        """Component keys should be the root indices."""
        uf = UnionFind(5)
        uf.union(3, 1)  # root = 1
        uf.union(4, 2)  # root = 2

        components = uf.components()

        # Keys should be roots: 0, 1, 2
        assert set(components.keys()) == {0, 1, 2}
        assert components[1] == [1, 3]
        assert components[2] == [2, 4]


# =============================================================================
# Transitive Union Tests
# =============================================================================


@pytest.mark.unit
class TestUnionFindTransitivity:
    """Tests for transitive connectivity through union operations."""

    def test_transitive_union_ab_bc_means_ac_connected(self) -> None:
        """If A-B and B-C are unioned, then A-C should be connected."""
        uf = UnionFind(5)
        uf.union(0, 1)  # A-B
        uf.union(1, 2)  # B-C

        assert uf.connected(0, 2) is True  # A-C

    def test_transitive_long_chain(self) -> None:
        """Long transitive chain should connect endpoints."""
        uf = UnionFind(10)

        # Chain: 0-1-2-3-4-5-6-7-8-9
        for i in range(9):
            uf.union(i, i + 1)

        # First and last should be connected
        assert uf.connected(0, 9) is True

    def test_transitive_merge_two_chains(self) -> None:
        """Merging two separate chains should connect all elements."""
        uf = UnionFind(6)

        # Chain 1: 0-1-2
        uf.union(0, 1)
        uf.union(1, 2)

        # Chain 2: 3-4-5
        uf.union(3, 4)
        uf.union(4, 5)

        # Chains not connected yet
        assert uf.connected(0, 3) is False

        # Connect chains
        uf.union(2, 3)

        # Now all should be connected
        assert uf.connected(0, 5) is True
        assert uf.connected(1, 4) is True

    def test_transitive_merge_preserves_smallest_root(self) -> None:
        """When merging chains, smallest index should be root."""
        uf = UnionFind(6)

        # Chain 1: root = 0
        uf.union(0, 1)
        uf.union(1, 2)

        # Chain 2: root = 3
        uf.union(3, 4)
        uf.union(4, 5)

        # Merge chains
        uf.union(2, 3)

        # Root should be 0 (smallest)
        for i in range(6):
            assert uf.find(i) == 0


# =============================================================================
# Edge Cases and Stress Tests
# =============================================================================


@pytest.mark.unit
class TestUnionFindEdgeCases:
    """Edge cases and stress tests for UnionFind."""

    def test_single_element_operations(self) -> None:
        """All operations should work with single element."""
        uf = UnionFind(1)

        assert uf.find(0) == 0
        assert uf.connected(0, 0) is True

        uf.union(0, 0)  # Self-union should be no-op
        assert uf.find(0) == 0

        components = uf.components()
        assert components == {0: [0]}

    def test_alternating_unions(self) -> None:
        """Alternating union pattern should work correctly."""
        uf = UnionFind(6)

        # Union even indices
        uf.union(0, 2)
        uf.union(2, 4)

        # Union odd indices
        uf.union(1, 3)
        uf.union(3, 5)

        components = uf.components()

        assert len(components) == 2
        assert components[0] == [0, 2, 4]
        assert components[1] == [1, 3, 5]

    def test_star_pattern_union(self) -> None:
        """Star pattern: all elements connected to one center."""
        uf = UnionFind(5)

        # Connect all to element 2
        uf.union(2, 0)
        uf.union(2, 1)
        uf.union(2, 3)
        uf.union(2, 4)

        # Root should be 0 (smallest in any union)
        assert uf.find(2) == 0

        components = uf.components()
        assert len(components) == 1
        assert components[0] == [0, 1, 2, 3, 4]

    def test_many_redundant_unions(self) -> None:
        """Redundant unions should not break anything."""
        uf = UnionFind(3)

        # Many redundant unions
        for _ in range(100):
            uf.union(0, 1)
            uf.union(1, 2)
            uf.union(0, 2)

        assert uf.find(0) == 0
        assert uf.find(1) == 0
        assert uf.find(2) == 0

    def test_boundary_indices(self) -> None:
        """Operations on boundary indices should work correctly."""
        uf = UnionFind(100)

        # Union first and last
        uf.union(0, 99)

        assert uf.connected(0, 99) is True
        assert uf.find(99) == 0  # Smaller becomes root
