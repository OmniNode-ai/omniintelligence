# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Test grouping real codebase nodes into families.

Scans the actual omniintelligence nodes directory, groups role occurrences
into node families, and verifies structural expectations against the live
codebase.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_group_node_families import (
    group_into_node_families,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_scan_role_occurrences import (
    scan_directory_for_role_occurrences,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_definition import (
    ModelPatternDefinition,
    ModelPatternRole,
)


def _omni_home() -> Path:
    """Resolve omni_home root via OMNI_HOME env or walk-up."""
    env = os.environ.get("OMNI_HOME")
    if env:
        return Path(env)
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "omnibase_core").is_dir() and (p / "omniintelligence").is_dir():
            return p
        p = p.parent
    msg = (
        "Cannot resolve omni_home root. Set OMNI_HOME or run from within the workspace."
    )
    raise RuntimeError(msg)


OMNI_HOME = _omni_home()

FOUR_NODE_PATTERN = ModelPatternDefinition(
    pattern_name="onex-four-node",
    pattern_type="architectural",
    description="ONEX four-node pattern",
    roles=[
        ModelPatternRole(
            role_name="compute",
            base_class="NodeCompute",
            distinguishing_mixin="MixinHandlerRouting",
            required=True,
            description="Pure computation",
        ),
        ModelPatternRole(
            role_name="effect",
            base_class="NodeEffect",
            distinguishing_mixin="MixinEffectExecution",
            required=True,
            description="External I/O",
        ),
        ModelPatternRole(
            role_name="orchestrator",
            base_class="NodeOrchestrator",
            distinguishing_mixin="MixinWorkflowExecution",
            required=False,
            description="Workflow",
        ),
        ModelPatternRole(
            role_name="reducer",
            base_class="NodeReducer",
            distinguishing_mixin="MixinFSMExecution",
            required=False,
            description="FSM state",
        ),
    ],
    when_to_use="When building a new Kafka-connected processing node",
    canonical_instance="omniintelligence/src/omniintelligence/nodes/node_pattern_storage_effect/",
)


@pytest.mark.unit
class TestGroupRealCodebase:
    """Group real omniintelligence nodes into families."""

    def test_finds_at_least_5_families(self) -> None:
        """Scanning real nodes directory produces 5+ node families."""
        nodes_dir = (
            OMNI_HOME / "omniintelligence" / "src" / "omniintelligence" / "nodes"
        )
        occurrences = scan_directory_for_role_occurrences(
            nodes_dir,
            FOUR_NODE_PATTERN,
            source_repo="omniintelligence",
            repo_root=OMNI_HOME / "omniintelligence",
        )

        families = group_into_node_families(occurrences)
        assert len(families) >= 5, (
            f"Expected at least 5 families, found {len(families)}: "
            f"{[f.directory_name for f in families]}"
        )

    def test_node_pattern_storage_effect_is_effect_family(self) -> None:
        """node_pattern_storage_effect should be grouped as an effect family."""
        nodes_dir = (
            OMNI_HOME / "omniintelligence" / "src" / "omniintelligence" / "nodes"
        )
        occurrences = scan_directory_for_role_occurrences(
            nodes_dir,
            FOUR_NODE_PATTERN,
            source_repo="omniintelligence",
            repo_root=OMNI_HOME / "omniintelligence",
        )

        families = group_into_node_families(occurrences)
        storage_families = [
            f for f in families if f.directory_name == "node_pattern_storage_effect"
        ]
        assert len(storage_families) == 1, (
            f"Expected exactly 1 node_pattern_storage_effect family, "
            f"found {len(storage_families)}"
        )
        family = storage_families[0]
        assert "effect" in family.roles, (
            f"node_pattern_storage_effect should have 'effect' role, "
            f"has roles: {family.roles}"
        )

    def test_each_family_has_at_least_one_role(self) -> None:
        """Every grouped family has at least one detected role."""
        nodes_dir = (
            OMNI_HOME / "omniintelligence" / "src" / "omniintelligence" / "nodes"
        )
        occurrences = scan_directory_for_role_occurrences(
            nodes_dir,
            FOUR_NODE_PATTERN,
            source_repo="omniintelligence",
            repo_root=OMNI_HOME / "omniintelligence",
        )

        families = group_into_node_families(occurrences)
        for family in families:
            assert len(family.roles) >= 1, (
                f"Family {family.directory_name} has no roles"
            )
            assert len(family.occurrences) >= 1, (
                f"Family {family.directory_name} has no occurrences"
            )
