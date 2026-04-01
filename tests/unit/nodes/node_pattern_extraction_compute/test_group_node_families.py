# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for NodeFamily grouping logic."""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_group_node_families import (
    NodeFamily,
    group_into_node_families,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_scan_role_occurrences import (
    RoleOccurrence,
)


def _make_occurrence(
    *,
    matched_role: str = "compute",
    file_path: str = "src/nodes/node_quality_scoring_compute/handlers/handler_compute.py",
    source_repo: str = "omniintelligence",
) -> RoleOccurrence:
    return RoleOccurrence(
        pattern_name="node_quad",
        matched_role=matched_role,
        entity_name="NodeQualityScoringCompute",
        qualified_name=f"omniintelligence.nodes.{matched_role}",
        file_path=file_path,
        source_repo=source_repo,
        bases=["NodeCompute"],
    )


@pytest.mark.unit
class TestGroupIntoNodeFamilies:
    """Tests for group_into_node_families."""

    def test_groups_by_parent_directory(self) -> None:
        """Two occurrences from different node_* dirs produce two families."""
        occ_a = _make_occurrence(
            file_path="src/nodes/node_quality_scoring_compute/handlers/handler.py",
            matched_role="compute",
        )
        occ_b = _make_occurrence(
            file_path="src/nodes/node_pattern_storage_effect/handlers/handler.py",
            matched_role="effect",
        )

        families = group_into_node_families([occ_a, occ_b])

        assert len(families) == 2
        dir_names = {f.directory_name for f in families}
        assert dir_names == {
            "node_quality_scoring_compute",
            "node_pattern_storage_effect",
        }

    def test_family_has_role_set(self) -> None:
        """A single effect occurrence produces a family with roles={'effect'}."""
        occ = _make_occurrence(
            file_path="src/nodes/node_pattern_storage_effect/node.py",
            matched_role="effect",
        )

        families = group_into_node_families([occ])

        assert len(families) == 1
        family = families[0]
        assert isinstance(family, NodeFamily)
        assert family.roles == frozenset({"effect"})
        assert family.directory_name == "node_pattern_storage_effect"
        assert len(family.occurrences) == 1

    def test_empty_input_returns_empty(self) -> None:
        """Empty input list returns empty output list."""
        assert group_into_node_families([]) == []
