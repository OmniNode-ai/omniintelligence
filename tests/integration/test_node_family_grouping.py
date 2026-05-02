# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Integration tests for node family grouping against real codebase data.

Scans the actual omniintelligence/nodes/ directory and groups into NodeFamily
instances to validate the grouping pipeline works on real code.
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
    env = os.environ.get("OMNI_HOME")
    if env:
        return Path(env)
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "omnibase_core").is_dir() and (p / "omniintelligence").is_dir():
            return p
        p = p.parent
    msg = "Cannot resolve omni_home root."
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


@pytest.fixture()
def omniintelligence_families() -> list:
    nodes_dir = OMNI_HOME / "omniintelligence" / "src" / "omniintelligence" / "nodes"
    occurrences = scan_directory_for_role_occurrences(
        nodes_dir,
        FOUR_NODE_PATTERN,
        source_repo="omniintelligence",
        repo_root=OMNI_HOME / "omniintelligence",
    )
    return group_into_node_families(occurrences)


@pytest.mark.integration
class TestNodeFamilyGrouping:
    def test_scan_finds_multiple_families(
        self, omniintelligence_families: list
    ) -> None:
        assert len(omniintelligence_families) >= 5, (
            f"Expected at least 5 families, found {len(omniintelligence_families)}"
        )

    def test_pattern_storage_effect_is_effect_family(
        self, omniintelligence_families: list
    ) -> None:
        families_by_name = {f.directory_name: f for f in omniintelligence_families}
        assert "node_pattern_storage_effect" in families_by_name, (
            f"node_pattern_storage_effect not found in {sorted(families_by_name)}"
        )
        family = families_by_name["node_pattern_storage_effect"]
        assert "effect" in family.roles

    def test_all_families_have_nonempty_roles(
        self, omniintelligence_families: list
    ) -> None:
        for family in omniintelligence_families:
            assert len(family.roles) >= 1, f"{family.directory_name} has no roles"
            assert len(family.occurrences) >= 1, (
                f"{family.directory_name} has no occurrences"
            )

    def test_multiple_role_types_across_families(
        self, omniintelligence_families: list
    ) -> None:
        all_roles: set[str] = set()
        for family in omniintelligence_families:
            all_roles |= family.roles
        assert len(all_roles) >= 3, (
            f"Expected at least 3 distinct role types, found {sorted(all_roles)}"
        )
