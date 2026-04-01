#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Seed learned_patterns from real node family scan.

Scans all ONEX repos (omniintelligence, omnibase_infra, omniclaude),
groups nodes into families, converts each to a learned_patterns row
via node_family_to_pattern_row(), and inserts into the omnibase_infra
database.

Supports --dry-run (default) and --execute modes. Uses
ON CONFLICT (pattern_signature, domain_id, version) DO UPDATE for
idempotency.

Usage:
    source ~/.omnibase/.env
    uv run python scripts/seed_patterns_from_families.py --dry-run
    uv run python scripts/seed_patterns_from_families.py --execute
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure src is on path when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_group_node_families import (
    group_into_node_families,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_scan_role_occurrences import (
    scan_directory_for_role_occurrences,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_store_node_families import (
    node_family_to_pattern_row,
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

_SQL_UPSERT = """\
INSERT INTO learned_patterns (
    id,
    pattern_signature,
    signature_hash,
    domain_id,
    domain_version,
    domain_candidates,
    keywords,
    confidence,
    status,
    promoted_at,
    source_session_ids,
    recurrence_count,
    first_seen_at,
    last_seen_at,
    distinct_days_seen,
    quality_score,
    evidence_tier,
    version,
    is_current,
    compiled_snippet,
    compiled_token_count,
    compiled_at
) VALUES (
    $1, $2, $3, $4, $5, $6::jsonb,
    $7, $8, $9, $10, $11,
    $12, $13, $14, $15,
    $16, $17, $18, $19,
    $20, $21, $22
)
ON CONFLICT (pattern_signature, domain_id, version) DO UPDATE SET
    confidence = EXCLUDED.confidence,
    quality_score = EXCLUDED.quality_score,
    compiled_snippet = EXCLUDED.compiled_snippet,
    compiled_token_count = EXCLUDED.compiled_token_count,
    compiled_at = EXCLUDED.compiled_at,
    last_seen_at = EXCLUDED.last_seen_at,
    updated_at = NOW()
"""


def _resolve_omni_home() -> Path:
    """Resolve omni_home root via OMNI_HOME env."""
    env = os.environ.get("OMNI_HOME")
    if env:
        return Path(env)
    print("ERROR: Set OMNI_HOME to the omni_home workspace root", file=sys.stderr)  # noqa: T201
    sys.exit(1)


def collect_all_families(omni_home: Path) -> list[dict]:
    """Scan all repos and return pattern rows."""
    all_rows: list[dict] = []

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
        print(
            f"  {repo_name}: {len(families)} families from {len(occurrences)} occurrences"
        )  # noqa: T201

        for family in families:
            row = node_family_to_pattern_row(family)
            all_rows.append(row)

    return all_rows


async def main(dry_run: bool) -> None:
    """Scan repos and seed learned_patterns."""
    omni_home = _resolve_omni_home()
    print(f"Scanning repos under: {omni_home}\n")  # noqa: T201

    rows = collect_all_families(omni_home)
    print(f"\nTotal pattern rows: {len(rows)}")  # noqa: T201

    if dry_run:
        print(f"\n[DRY RUN] Would upsert {len(rows)} patterns into learned_patterns:")  # noqa: T201
        for row in rows:
            print(  # noqa: T201
                f"  {row['id'][:8]}... | {row['domain_id']:12s} | "
                f"conf={row['confidence']:.2f} | {row['pattern_signature'][:60]}"
            )
        print("\nRun with --execute to actually insert")  # noqa: T201
        return

    # Use OMNIBASE_INFRA_DB_URL since learned_patterns is in omnibase_infra
    db_url = os.environ.get("OMNIBASE_INFRA_DB_URL")
    if not db_url:
        print(  # noqa: T201
            "ERROR: OMNIBASE_INFRA_DB_URL not set in environment",
            file=sys.stderr,
        )
        sys.exit(1)


    import asyncpg

    print("\nConnecting to database...")  # noqa: T201
    conn = await asyncpg.connect(db_url)

    try:
        # Purge existing architecture-domain patterns (clean slate)
        deleted = await conn.execute(
            "DELETE FROM learned_patterns WHERE domain_id = 'architecture'"
        )
        print(f"Purged existing architecture patterns: {deleted}")  # noqa: T201

        inserted = 0
        for row in rows:
            await conn.execute(
                _SQL_UPSERT,
                row["id"],  # $1
                row["pattern_signature"],  # $2
                row["signature_hash"],  # $3
                row["domain_id"],  # $4
                row["domain_version"],  # $5
                json.dumps(row["domain_candidates"]),  # $6
                row["keywords"],  # $7
                row["confidence"],  # $8
                row["status"],  # $9
                row["promoted_at"],  # $10
                row["source_session_ids"],  # $11
                row["recurrence_count"],  # $12
                row["first_seen_at"],  # $13
                row["last_seen_at"],  # $14
                row["distinct_days_seen"],  # $15
                row["quality_score"],  # $16
                row["evidence_tier"],  # $17
                row["version"],  # $18
                row["is_current"],  # $19
                row["compiled_snippet"],  # $20
                row["compiled_token_count"],  # $21
                row["compiled_at"],  # $22
            )
            inserted += 1

        # Verify
        count = await conn.fetchval(
            "SELECT count(*) FROM learned_patterns "
            "WHERE domain_id = 'architecture' AND is_current = TRUE"
        )
        total = await conn.fetchval(
            "SELECT count(*) FROM learned_patterns WHERE is_current = TRUE"
        )
        print(f"\nSeed complete: {inserted} patterns upserted")  # noqa: T201
        print(f"Architecture patterns (is_current=TRUE): {count}")  # noqa: T201
        print(f"Total patterns (is_current=TRUE): {total}")  # noqa: T201

    finally:
        await conn.close()


if __name__ == "__main__":
    if "--execute" in sys.argv:
        asyncio.run(main(dry_run=False))
    elif "--dry-run" in sys.argv:
        asyncio.run(main(dry_run=True))
    else:
        print(  # noqa: T201
            "Usage: uv run python scripts/seed_patterns_from_families.py --dry-run|--execute"
        )
        sys.exit(1)
