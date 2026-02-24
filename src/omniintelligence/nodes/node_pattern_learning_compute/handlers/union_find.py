# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Union-Find (Disjoint-Set) data structure for clustering operations.

This module provides a reusable Union-Find implementation optimized for
deterministic clustering operations. It supports path compression for
efficient `find()` operations and guarantees deterministic behavior by
always selecting the smaller index as the root during union operations.

Union-Find Overview:
    Union-Find is a data structure that tracks a partition of elements into
    disjoint sets. It supports two primary operations:
    - find(x): Determine which set element x belongs to (returns the "root")
    - union(x, y): Merge the sets containing x and y

    This implementation uses:
    - Path compression: Flatten tree structure during find() for O(alpha(n)) amortized
    - Deterministic union: Smaller index always becomes root (not rank-based)

Determinism Guarantees:
    Unlike traditional rank-based union, this implementation prioritizes
    determinism over theoretical optimality:
    - The smaller index ALWAYS becomes the root
    - Given the same inputs, the same partition will always result
    - This enables reproducible clustering results

Performance:
    - find(): O(alpha(n)) amortized with path compression
    - union(): O(alpha(n)) amortized (dominated by find())
    - connected(): O(alpha(n)) amortized (two find() calls)
    - components(): O(n) to collect all groups

    Where alpha(n) is the inverse Ackermann function, effectively O(1) for all
    practical values of n.

Usage:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers.union_find import (
        UnionFind,
    )

    # Create Union-Find for n=5 elements (indices 0-4)
    uf = UnionFind(5)

    # Merge sets containing indices 0 and 1
    uf.union(0, 1)

    # Check if 0 and 1 are in the same set
    assert uf.connected(0, 1) is True

    # Find the root of element 0
    root = uf.find(0)

    # Get all components (groups of connected indices)
    components = uf.components()  # {root: [indices...], ...}
"""

from __future__ import annotations


class UnionFind:
    """Disjoint-set data structure with deterministic ordering.

    This class implements Union-Find with path compression and deterministic
    union rules suitable for single-linkage clustering where reproducibility
    is critical.

    Attributes:
        n: The number of elements (indices 0 to n-1).

    Determinism:
        The smaller index always becomes the root during union operations.
        This ensures that given the same sequence of union() calls, the
        resulting partition is identical regardless of call order within
        pairs.

    Examples:
        >>> uf = UnionFind(5)
        >>> uf.union(0, 2)
        >>> uf.union(1, 2)
        >>> uf.find(0) == uf.find(1) == uf.find(2)
        True
        >>> uf.find(0)  # Smallest index (0) is root
        0
        >>> uf.connected(3, 4)
        False
    """

    __slots__ = ("_n", "_parent")

    def __init__(self, n: int) -> None:
        """Initialize Union-Find with n elements.

        Each element starts in its own singleton set, where it is its own root.

        Args:
            n: Number of elements (creates indices 0 to n-1).

        Raises:
            ValueError: If n is negative.

        Examples:
            >>> uf = UnionFind(10)
            >>> uf.find(5)
            5
        """
        if n < 0:
            raise ValueError(f"Number of elements must be non-negative, got {n}")
        self._n = n
        self._parent: list[int] = list(range(n))

    @property
    def n(self) -> int:
        """Return the number of elements."""
        return self._n

    def find(self, x: int) -> int:
        """Find the root of the set containing element x.

        Uses iterative path compression: all nodes on the path to root are
        updated to point directly to the root, amortizing future find() calls.

        Args:
            x: Element index (must be in range [0, n)).

        Returns:
            The root index of the set containing x.

        Raises:
            IndexError: If x is out of bounds.

        Examples:
            >>> uf = UnionFind(5)
            >>> uf.union(0, 1)
            >>> uf.union(1, 2)
            >>> uf.find(2)  # Path compressed to root
            0
        """
        if x < 0 or x >= self._n:
            raise IndexError(
                f"Index {x} out of bounds for UnionFind with {self._n} elements"
            )

        # Pass 1: Find root
        root = x
        while self._parent[root] != root:
            root = self._parent[root]

        # Pass 2: Path compression - update all nodes to point to root
        while self._parent[x] != root:
            next_x = self._parent[x]
            self._parent[x] = root
            x = next_x

        return root

    def union(self, x: int, y: int) -> None:
        """Merge the sets containing elements x and y.

        Uses deterministic union: the smaller root index always becomes
        the new root. This guarantees reproducible results regardless of
        the order of union operations.

        If x and y are already in the same set, this is a no-op.

        Args:
            x: First element index.
            y: Second element index.

        Raises:
            IndexError: If x or y is out of bounds.

        Examples:
            >>> uf = UnionFind(5)
            >>> uf.union(3, 1)
            >>> uf.find(3)  # Smaller index (1) becomes root
            1
        """
        root_x = self.find(x)
        root_y = self.find(y)

        if root_x != root_y:
            # Deterministic: smaller index becomes root
            if root_x < root_y:
                self._parent[root_y] = root_x
            else:
                self._parent[root_x] = root_y

    def connected(self, x: int, y: int) -> bool:
        """Check if elements x and y are in the same set.

        Args:
            x: First element index.
            y: Second element index.

        Returns:
            True if x and y are in the same set, False otherwise.

        Raises:
            IndexError: If x or y is out of bounds.

        Examples:
            >>> uf = UnionFind(5)
            >>> uf.connected(0, 1)
            False
            >>> uf.union(0, 1)
            >>> uf.connected(0, 1)
            True
        """
        return self.find(x) == self.find(y)

    def components(self) -> dict[int, list[int]]:
        """Get all connected components as a mapping from root to members.

        Returns:
            Dictionary mapping each root index to a list of all element
            indices in that component. Lists are sorted for determinism.

        Examples:
            >>> uf = UnionFind(5)
            >>> uf.union(0, 2)
            >>> uf.union(1, 3)
            >>> components = uf.components()
            >>> components[0]  # Component with root 0
            [0, 2]
            >>> components[1]  # Component with root 1
            [1, 3]
            >>> 4 in components  # Singleton component
            True
        """
        result: dict[int, list[int]] = {}
        for i in range(self._n):
            root = self.find(i)
            if root not in result:
                result[root] = []
            result[root].append(i)

        # Sort member lists for determinism
        for members in result.values():
            members.sort()

        return result


__all__ = ["UnionFind"]
