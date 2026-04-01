#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Report node families across all ONEX repos.

Scans omniintelligence, omnibase_infra, and omniclaude for ONEX node
directories, groups them into node families, and prints a summary report
with per-repo counts and role composition.

Usage:
    OMNI_HOME=/Volumes/PRO-G40/Code/omni_home uv run python scripts/report_node_families.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src is on path when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_group_node_families import (
    NodeFamily,
    group_into_node_families,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_scan_role_occurrences import (
    scan_directory_for_role_occurrences,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_definition import (
    ModelPatternDefinition,
    ModelPatternRole,
)

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

REPOS = [
    ("omniintelligence", "src/omniintelligence/nodes"),
    ("omnibase_infra", "src/omnibase_infra/nodes"),
    ("omniclaude", "src/omniclaude/nodes"),
]


def _resolve_omni_home() -> Path:
    """Resolve omni_home root via OMNI_HOME env."""
    env = os.environ.get("OMNI_HOME")
    if env:
        return Path(env)
    print("ERROR: Set OMNI_HOME to the omni_home workspace root", file=sys.stderr)  # noqa: T201
    sys.exit(1)


def scan_all_repos(omni_home: Path) -> dict[str, list[NodeFamily]]:
    """Scan all repos and return families grouped by repo."""
    results: dict[str, list[NodeFamily]] = {}

    for repo_name, nodes_rel_path in REPOS:
        nodes_dir = omni_home / repo_name / nodes_rel_path
        if not nodes_dir.is_dir():
            print(f"  SKIP {repo_name}: {nodes_dir} not found")  # noqa: T201
            continue

        repo_root = omni_home / repo_name
        occurrences = scan_directory_for_role_occurrences(
            nodes_dir,
            FOUR_NODE_PATTERN,
            source_repo=repo_name,
            repo_root=repo_root,
        )
        families = group_into_node_families(occurrences)
        results[repo_name] = families

    return results


def print_report(results: dict[str, list[NodeFamily]]) -> None:
    """Print a formatted report of node families across repos."""
    total_families = sum(len(fams) for fams in results.values())
    total_occurrences = sum(
        sum(len(f.occurrences) for f in fams) for fams in results.values()
    )

    print("=" * 72)  # noqa: T201
    print("  ONEX Node Family Report")  # noqa: T201
    print("=" * 72)  # noqa: T201
    print(f"\nTotal families: {total_families}")  # noqa: T201
    print(f"Total role occurrences: {total_occurrences}")  # noqa: T201
    print(f"Repos scanned: {len(results)}")  # noqa: T201

    # Role distribution across all repos
    role_counts: dict[str, int] = {}
    for fams in results.values():
        for f in fams:
            for role in f.roles:
                role_counts[role] = role_counts.get(role, 0) + 1

    print("\nRole distribution (families with role):")  # noqa: T201
    for role, count in sorted(role_counts.items(), key=lambda x: -x[1]):
        print(f"  {role:15s}: {count}")  # noqa: T201

    # Per-repo breakdown
    for repo_name, families in sorted(results.items()):
        print(f"\n{'─' * 72}")  # noqa: T201
        print(f"  {repo_name} ({len(families)} families)")  # noqa: T201
        print(f"{'─' * 72}")  # noqa: T201

        for family in sorted(families, key=lambda f: f.directory_name):
            roles_str = ", ".join(sorted(family.roles))
            print(f"  {family.directory_name:50s} [{roles_str}]")  # noqa: T201

    print(f"\n{'=' * 72}")  # noqa: T201


def main() -> None:
    """Entry point."""
    omni_home = _resolve_omni_home()
    print(f"Scanning repos under: {omni_home}\n")  # noqa: T201
    results = scan_all_repos(omni_home)
    print_report(results)


if __name__ == "__main__":
    main()
