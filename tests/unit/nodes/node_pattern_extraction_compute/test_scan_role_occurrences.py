# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Test scanning a directory for ONEX role occurrences."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_scan_role_occurrences import (
    scan_directory_for_role_occurrences,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_definition import (
    ModelPatternDefinition,
    ModelPatternRole,
)


def _omni_home() -> Path:
    """Resolve omni_home root."""
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
class TestScanRoleOccurrences:
    """Scan a nodes directory and find pattern instances."""

    def test_finds_compute_nodes_in_omniintelligence(self) -> None:
        """Scanning omniintelligence/nodes/ finds at least one compute node."""
        nodes_dir = (
            OMNI_HOME / "omniintelligence" / "src" / "omniintelligence" / "nodes"
        )
        instances = scan_directory_for_role_occurrences(
            nodes_dir,
            FOUR_NODE_PATTERN,
            source_repo="omniintelligence",
            repo_root=OMNI_HOME / "omniintelligence",
        )

        compute_instances = [i for i in instances if i.matched_role == "compute"]
        assert len(compute_instances) >= 1, (
            f"Expected at least 1 compute instance, found {len(compute_instances)}"
        )

    def test_finds_effect_nodes_in_omniintelligence(self) -> None:
        """Scanning omniintelligence/nodes/ finds at least one effect node."""
        nodes_dir = (
            OMNI_HOME / "omniintelligence" / "src" / "omniintelligence" / "nodes"
        )
        instances = scan_directory_for_role_occurrences(
            nodes_dir,
            FOUR_NODE_PATTERN,
            source_repo="omniintelligence",
            repo_root=OMNI_HOME / "omniintelligence",
        )

        effect_instances = [i for i in instances if i.matched_role == "effect"]
        assert len(effect_instances) >= 1

    def test_occurrence_has_entity_and_file_info(self) -> None:
        """Each occurrence records which entity matched and where."""
        nodes_dir = (
            OMNI_HOME / "omniintelligence" / "src" / "omniintelligence" / "nodes"
        )
        instances = scan_directory_for_role_occurrences(
            nodes_dir,
            FOUR_NODE_PATTERN,
            source_repo="omniintelligence",
            repo_root=OMNI_HOME / "omniintelligence",
        )

        assert len(instances) >= 1
        inst = instances[0]
        assert inst.entity_name != ""
        assert inst.file_path != ""
        assert inst.matched_role in {"compute", "effect", "orchestrator", "reducer"}
