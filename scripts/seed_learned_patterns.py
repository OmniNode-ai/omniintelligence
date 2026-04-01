#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Seed script to populate learned_patterns table with realistic pattern data.

Inserts 15 realistic patterns (tool_sequence, file_access, error_recovery types)
into the learned_patterns table so the projection handler has rows to query.

All seeded patterns use deterministic UUID5 IDs (namespace=SEED_NS, name=signature)
so re-running is idempotent (ON CONFLICT DO NOTHING). Seeded patterns are
distinguishable from organic patterns via:
  - source_session_ids contains a single deterministic UUID with prefix seed-*
  - domain_version = "seed-1.0.0"

Usage:
    source ~/.omnibase/.env
    uv run python scripts/seed_learned_patterns.py
    uv run python scripts/seed_learned_patterns.py --dry-run

Related:
    - OMN-7140: Pattern intelligence pipeline end-to-end wiring
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

# Deterministic namespace for seed patterns
SEED_NS = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Deterministic session ID marker for seed provenance
SEED_SESSION_ID = UUID("00000000-5eed-0000-5eed-000000000001")


def _seed_id(signature: str) -> UUID:
    """Generate a deterministic UUID5 from the pattern signature."""
    return uuid5(SEED_NS, signature)


# fmt: off
SEED_PATTERNS: list[dict] = [
    # --- tool_sequence patterns ---
    {
        "signature": "tool_sequence: Read -> Grep -> Edit (targeted file modification)",
        "domain_id": "general",
        "confidence": 0.92,
        "status": "validated",
        "quality_score": 0.85,
        "recurrence_count": 12,
        "distinct_days_seen": 5,
        "injection_count_rolling_20": 15,
        "success_count_rolling_20": 13,
        "failure_count_rolling_20": 2,
        "keywords": ["read", "grep", "edit", "targeted-modification"],
    },
    {
        "signature": "tool_sequence: Glob -> Read -> Write (new file creation from template)",
        "domain_id": "general",
        "confidence": 0.88,
        "status": "validated",
        "quality_score": 0.78,
        "recurrence_count": 8,
        "distinct_days_seen": 4,
        "injection_count_rolling_20": 10,
        "success_count_rolling_20": 8,
        "failure_count_rolling_20": 2,
        "keywords": ["glob", "read", "write", "file-creation"],
    },
    {
        "signature": "tool_sequence: Bash(git status) -> Bash(git diff) -> Bash(git commit) (commit workflow)",
        "domain_id": "general",
        "confidence": 0.90,
        "status": "validated",
        "quality_score": 0.82,
        "recurrence_count": 20,
        "distinct_days_seen": 7,
        "injection_count_rolling_20": 18,
        "success_count_rolling_20": 16,
        "failure_count_rolling_20": 2,
        "keywords": ["git", "commit", "workflow"],
    },
    {
        "signature": "tool_sequence: Grep -> Read -> Grep -> Read (multi-file investigation)",
        "domain_id": "general",
        "confidence": 0.85,
        "status": "provisional",
        "quality_score": 0.70,
        "recurrence_count": 6,
        "distinct_days_seen": 3,
        "injection_count_rolling_20": 8,
        "success_count_rolling_20": 6,
        "failure_count_rolling_20": 2,
        "keywords": ["grep", "read", "investigation", "multi-file"],
    },
    {
        "signature": "tool_sequence: Bash(uv run pytest) -> Read -> Edit -> Bash(uv run pytest) (TDD loop)",
        "domain_id": "general",
        "confidence": 0.93,
        "status": "validated",
        "quality_score": 0.90,
        "recurrence_count": 15,
        "distinct_days_seen": 6,
        "injection_count_rolling_20": 14,
        "success_count_rolling_20": 13,
        "failure_count_rolling_20": 1,
        "keywords": ["pytest", "tdd", "test-driven", "edit"],
    },
    # --- file_access patterns ---
    {
        "signature": "file_access: CLAUDE.md read at session start (context loading)",
        "domain_id": "general",
        "confidence": 0.95,
        "status": "validated",
        "quality_score": 0.88,
        "recurrence_count": 18,
        "distinct_days_seen": 7,
        "injection_count_rolling_20": 16,
        "success_count_rolling_20": 15,
        "failure_count_rolling_20": 1,
        "keywords": ["claude-md", "context", "session-start"],
    },
    {
        "signature": "file_access: pyproject.toml read before dependency changes",
        "domain_id": "general",
        "confidence": 0.87,
        "status": "validated",
        "quality_score": 0.75,
        "recurrence_count": 9,
        "distinct_days_seen": 4,
        "injection_count_rolling_20": 11,
        "success_count_rolling_20": 9,
        "failure_count_rolling_20": 2,
        "keywords": ["pyproject", "dependencies", "toml"],
    },
    {
        "signature": "file_access: conftest.py read before writing test files",
        "domain_id": "general",
        "confidence": 0.82,
        "status": "provisional",
        "quality_score": 0.68,
        "recurrence_count": 5,
        "distinct_days_seen": 3,
        "injection_count_rolling_20": 7,
        "success_count_rolling_20": 5,
        "failure_count_rolling_20": 2,
        "keywords": ["conftest", "test", "fixtures"],
    },
    {
        "signature": "file_access: contract.yaml read before handler implementation",
        "domain_id": "general",
        "confidence": 0.89,
        "status": "validated",
        "quality_score": 0.80,
        "recurrence_count": 7,
        "distinct_days_seen": 4,
        "injection_count_rolling_20": 9,
        "success_count_rolling_20": 7,
        "failure_count_rolling_20": 2,
        "keywords": ["contract", "yaml", "handler"],
    },
    {
        "signature": "file_access: .env read before infrastructure operations",
        "domain_id": "general",
        "confidence": 0.91,
        "status": "validated",
        "quality_score": 0.83,
        "recurrence_count": 10,
        "distinct_days_seen": 5,
        "injection_count_rolling_20": 12,
        "success_count_rolling_20": 10,
        "failure_count_rolling_20": 2,
        "keywords": ["env", "infrastructure", "config"],
    },
    # --- error_recovery patterns ---
    {
        "signature": "error_recovery: pre-commit failure -> ruff fix -> re-stage -> re-commit",
        "domain_id": "general",
        "confidence": 0.86,
        "status": "validated",
        "quality_score": 0.76,
        "recurrence_count": 11,
        "distinct_days_seen": 5,
        "injection_count_rolling_20": 13,
        "success_count_rolling_20": 10,
        "failure_count_rolling_20": 3,
        "keywords": ["pre-commit", "ruff", "lint", "recovery"],
    },
    {
        "signature": "error_recovery: import error -> read traceback -> fix import path",
        "domain_id": "general",
        "confidence": 0.84,
        "status": "provisional",
        "quality_score": 0.72,
        "recurrence_count": 7,
        "distinct_days_seen": 4,
        "injection_count_rolling_20": 9,
        "success_count_rolling_20": 7,
        "failure_count_rolling_20": 2,
        "keywords": ["import", "traceback", "fix"],
    },
    {
        "signature": "error_recovery: test failure -> read test output -> edit test -> re-run",
        "domain_id": "general",
        "confidence": 0.88,
        "status": "validated",
        "quality_score": 0.79,
        "recurrence_count": 14,
        "distinct_days_seen": 6,
        "injection_count_rolling_20": 16,
        "success_count_rolling_20": 13,
        "failure_count_rolling_20": 3,
        "keywords": ["test", "failure", "debug", "re-run"],
    },
    {
        "signature": "error_recovery: mypy type error -> read error -> add type annotation",
        "domain_id": "general",
        "confidence": 0.81,
        "status": "provisional",
        "quality_score": 0.65,
        "recurrence_count": 4,
        "distinct_days_seen": 2,
        "injection_count_rolling_20": 6,
        "success_count_rolling_20": 4,
        "failure_count_rolling_20": 2,
        "keywords": ["mypy", "type-error", "annotation"],
    },
    {
        "signature": "error_recovery: docker build failure -> read Dockerfile -> fix base image -> rebuild",
        "domain_id": "general",
        "confidence": 0.79,
        "status": "candidate",
        "quality_score": 0.60,
        "recurrence_count": 3,
        "distinct_days_seen": 2,
        "injection_count_rolling_20": 4,
        "success_count_rolling_20": 3,
        "failure_count_rolling_20": 1,
        "keywords": ["docker", "build", "dockerfile", "recovery"],
    },
]
# fmt: on


_SQL_INSERT = """\
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
    injection_count_rolling_20,
    success_count_rolling_20,
    failure_count_rolling_20,
    failure_streak,
    version,
    is_current
) VALUES (
    $1, $2, $3, $4, $5, $6::jsonb,
    $7, $8, $9, $10, $11,
    $12, $13, $14, $15,
    $16, $17, $18, $19, $20, $21, $22
)
ON CONFLICT (id) DO NOTHING
"""


async def main(dry_run: bool) -> None:
    """Insert seed patterns into learned_patterns table."""
    db_url = os.environ.get("OMNIINTELLIGENCE_DB_URL")
    if not db_url:
        print("ERROR: OMNIINTELLIGENCE_DB_URL not set in environment", file=sys.stderr)  # noqa: T201
        sys.exit(1)


    import hashlib
    import json

    import asyncpg

    now = datetime.now(UTC)

    if dry_run:
        print(f"[DRY RUN] Would insert {len(SEED_PATTERNS)} seed patterns:")  # noqa: T201
        for p in SEED_PATTERNS:
            pid = _seed_id(p["signature"])
            print(
                f"  {pid} | {p['status']:12s} | conf={p['confidence']:.2f} | {p['signature'][:60]}"
            )  # noqa: T201
        print("\nRun without --dry-run to actually insert")  # noqa: T201
        return

    print("Connecting to database...")  # noqa: T201
    conn = await asyncpg.connect(db_url)

    try:
        # Check current count
        count_before = await conn.fetchval(
            "SELECT count(*) FROM learned_patterns WHERE is_current = TRUE"
        )
        print(f"Current pattern count (is_current=TRUE): {count_before}")  # noqa: T201

        inserted = 0
        for p in SEED_PATTERNS:
            pid = _seed_id(p["signature"])
            status = p["status"]
            promoted_at = (
                now - timedelta(days=3)
                if status in ("provisional", "validated")
                else None
            )
            sig_hash = hashlib.sha256(p["signature"].encode()).hexdigest()

            result = await conn.execute(
                _SQL_INSERT,
                pid,  # $1 id
                p["signature"],  # $2 pattern_signature
                sig_hash,  # $3 signature_hash
                p["domain_id"],  # $4 domain_id
                "seed-1.0.0",  # $5 domain_version (seed marker)
                json.dumps(
                    [{"domain": p["domain_id"], "confidence": p["confidence"]}]
                ),  # $6 domain_candidates
                p.get("keywords", []),  # $7 keywords
                p["confidence"],  # $8 confidence
                status,  # $9 status
                promoted_at,  # $10 promoted_at
                [SEED_SESSION_ID],  # $11 source_session_ids (seed marker)
                p["recurrence_count"],  # $12 recurrence_count
                now - timedelta(days=p["distinct_days_seen"]),  # $13 first_seen_at
                now,  # $14 last_seen_at
                p["distinct_days_seen"],  # $15 distinct_days_seen
                p["quality_score"],  # $16 quality_score
                p["injection_count_rolling_20"],  # $17 injection_count_rolling_20
                p["success_count_rolling_20"],  # $18 success_count_rolling_20
                p["failure_count_rolling_20"],  # $19 failure_count_rolling_20
                0,  # $20 failure_streak
                1,  # $21 version
                True,  # $22 is_current
            )
            if "INSERT 0 1" in result:
                inserted += 1
                print(f"  Inserted: {pid} | {status:12s} | {p['signature'][:60]}")  # noqa: T201
            else:
                print(f"  Skipped (exists): {pid} | {p['signature'][:60]}")  # noqa: T201

        # Verify final count
        count_after = await conn.fetchval(
            "SELECT count(*) FROM learned_patterns WHERE is_current = TRUE"
        )
        by_status = await conn.fetch(
            "SELECT status, count(*) as cnt FROM learned_patterns "
            "WHERE is_current = TRUE GROUP BY status ORDER BY status"
        )

        print(f"\nSeed complete: {inserted} new patterns inserted")  # noqa: T201
        print(f"Total patterns (is_current=TRUE): {count_after}")  # noqa: T201
        print("By status:")  # noqa: T201
        for row in by_status:
            print(f"  {row['status']:12s}: {row['cnt']}")  # noqa: T201

    finally:
        await conn.close()


if __name__ == "__main__":
    is_dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=is_dry_run))
