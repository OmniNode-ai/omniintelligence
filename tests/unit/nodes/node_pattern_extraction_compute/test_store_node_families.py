# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Test converting node families to learned_patterns row dicts."""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_group_node_families import (
    NodeFamily,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_scan_role_occurrences import (
    RoleOccurrence,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_store_node_families import (
    node_family_to_pattern_row,
)


@pytest.mark.unit
class TestNodeFamilyToPatternRow:
    def test_produces_valid_row_dict(self) -> None:
        """A single-role family produces a row dict with all required fields."""
        occ = RoleOccurrence(
            pattern_name="onex-four-node",
            matched_role="effect",
            entity_name="NodePatternStorageEffect",
            qualified_name="omniintelligence.nodes.node_pattern_storage_effect.node.NodePatternStorageEffect",
            file_path="src/omniintelligence/nodes/node_pattern_storage_effect/node.py",
            source_repo="omniintelligence",
            bases=["NodeEffect"],
        )
        family = NodeFamily(
            directory_name="node_pattern_storage_effect",
            directory_path="src/omniintelligence/nodes/node_pattern_storage_effect",
            source_repo="omniintelligence",
            roles=frozenset({"effect"}),
            occurrences=(occ,),
        )

        row = node_family_to_pattern_row(family)

        assert row["domain_id"] == "architecture"
        assert row["status"] == "validated"
        assert row["confidence"] >= 0.5
        assert "node_pattern_storage_effect" in row["pattern_signature"]
        assert row["compiled_snippet"] is not None
        assert "effect" in row["compiled_snippet"]

    def test_multi_role_family_has_higher_confidence(self) -> None:
        """Families with more roles get higher confidence."""
        occ1 = RoleOccurrence(
            pattern_name="onex-four-node",
            matched_role="effect",
            entity_name="A",
            qualified_name="a.A",
            file_path="src/nodes/node_x/a.py",
            source_repo="r",
            bases=["NodeEffect"],
        )
        occ2 = RoleOccurrence(
            pattern_name="onex-four-node",
            matched_role="compute",
            entity_name="B",
            qualified_name="a.B",
            file_path="src/nodes/node_x/b.py",
            source_repo="r",
            bases=["NodeCompute"],
        )
        family = NodeFamily(
            directory_name="node_x",
            directory_path="src/nodes/node_x",
            source_repo="r",
            roles=frozenset({"effect", "compute"}),
            occurrences=(occ1, occ2),
        )
        row = node_family_to_pattern_row(family)
        assert row["confidence"] > 0.7  # multi-role should score higher
