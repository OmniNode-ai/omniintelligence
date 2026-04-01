#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Cross-repo four-node pattern baseline scan.

Scans three ONEX repositories (omniintelligence, omnibase_infra, omniclaude)
for classes that match the four-node architectural pattern roles (compute,
effect, orchestrator, reducer) by direct base-class inheritance.

This produces a baseline count of role occurrences per repo and per role.
It does NOT group occurrences into pattern instances (Sense 2) -- only
individual role matches (Sense 1).

Usage:
    cd /Volumes/PRO-G40/Code/omni_home/omniintelligence
    OMNI_HOME=/Volumes/PRO-G40/Code/omni_home uv run python scripts/scan_four_node_pattern.py
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_scan_role_occurrences import (
    RoleOccurrence,
    scan_directory_for_role_occurrences,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_definition import (
    ModelPatternDefinition,
    ModelPatternRole,
)

# ---------------------------------------------------------------------------
# Four-node pattern definition
# ---------------------------------------------------------------------------

FOUR_NODE_PATTERN = ModelPatternDefinition(
    pattern_name="onex_four_node",
    pattern_type="node_family",
    description=(
        "The canonical ONEX four-node architectural pattern: compute, effect, "
        "orchestrator, and reducer. Each role is identified by its base class."
    ),
    roles=[
        ModelPatternRole(
            role_name="compute",
            base_class="NodeCompute",
            distinguishing_mixin="MixinHandlerRouting",
            required=True,
            description="Stateless transformation node (input -> output).",
        ),
        ModelPatternRole(
            role_name="effect",
            base_class="NodeEffect",
            distinguishing_mixin="MixinEffectExecution",
            required=True,
            description="Side-effecting node (writes to external systems).",
        ),
        ModelPatternRole(
            role_name="orchestrator",
            base_class="NodeOrchestrator",
            distinguishing_mixin="MixinWorkflowExecution",
            required=False,
            description="Workflow coordinator that chains other nodes.",
        ),
        ModelPatternRole(
            role_name="reducer",
            base_class="NodeReducer",
            distinguishing_mixin="MixinFSMExecution",
            required=False,
            description="Stateful aggregation node with FSM lifecycle.",
        ),
    ],
    when_to_use="When building a new ONEX subsystem that transforms, persists, orchestrates, or aggregates data.",
    canonical_instance="node_pattern_storage_effect",
)

# ---------------------------------------------------------------------------
# Repos to scan
# ---------------------------------------------------------------------------

REPOS = [
    ("omniintelligence", "omniintelligence"),
    ("omnibase_infra", "omnibase_infra"),
    ("omniclaude", "omniclaude"),
]


def main() -> None:
    omni_home = Path(os.environ.get("OMNI_HOME", "/Volumes/PRO-G40/Code/omni_home"))

    if not omni_home.is_dir():
        print(f"ERROR: OMNI_HOME={omni_home} does not exist", file=sys.stderr)
        sys.exit(1)

    all_occurrences: dict[str, list[RoleOccurrence]] = {}

    for repo_dir_name, package_name in REPOS:
        nodes_dir = omni_home / repo_dir_name / "src" / package_name / "nodes"
        repo_root = omni_home / repo_dir_name / "src"

        if not nodes_dir.is_dir():
            print(f"WARNING: {nodes_dir} does not exist, skipping {repo_dir_name}")
            continue

        occurrences = scan_directory_for_role_occurrences(
            directory=nodes_dir,
            pattern=FOUR_NODE_PATTERN,
            source_repo=repo_dir_name,
            repo_root=repo_root,
        )
        all_occurrences[repo_dir_name] = occurrences

    # -----------------------------------------------------------------------
    # Print summary
    # -----------------------------------------------------------------------

    total = sum(len(v) for v in all_occurrences.values())
    print("=" * 72)
    print("FOUR-NODE PATTERN BASELINE SCAN")
    print(f"Pattern: {FOUR_NODE_PATTERN.pattern_name}")
    print(f"Repos scanned: {len(all_occurrences)}")
    print(f"Total role occurrences: {total}")
    print("=" * 72)

    # Repo-level summary
    print("\n--- Repo-Level Counts ---")
    for repo_name in sorted(all_occurrences.keys()):
        occ = all_occurrences[repo_name]
        print(f"  {repo_name}: {len(occ)} occurrences")

    # Role-level summary
    print("\n--- Role-Level Counts ---")
    role_counts: dict[str, int] = defaultdict(int)
    for occ_list in all_occurrences.values():
        for occ in occ_list:
            role_counts[occ.matched_role] += 1
    for role_name in ["compute", "effect", "orchestrator", "reducer"]:
        print(f"  {role_name}: {role_counts.get(role_name, 0)}")

    # Per-instance details
    print("\n--- Per-Instance Details ---")
    for repo_name in sorted(all_occurrences.keys()):
        occ_list = all_occurrences[repo_name]
        if not occ_list:
            continue
        print(f"\n  [{repo_name}]")
        sorted_occ = sorted(occ_list, key=lambda o: (o.matched_role, o.entity_name))
        for occ in sorted_occ:
            print(f"    role={occ.matched_role}  entity={occ.entity_name}")
            print(f"      file={occ.file_path}")
            print(f"      bases={occ.bases}")

    print("\n" + "=" * 72)
    print("Scan complete.")


if __name__ == "__main__":
    main()
