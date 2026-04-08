#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Standalone promotion check — runs without the omniintelligence runtime.

Connects directly to PostgreSQL via asyncpg, wraps the connection as a
ProtocolPatternRepository, and invokes handle_auto_promote_check() with
producer=None (Kafka events are skipped; transitions happen in the DB only).

Safe to run repeatedly — idempotent by design (SQL status guards prevent
double-promotion).

Usage:
    # Dry-run: report eligible patterns without promoting
    uv run python scripts/run_promotion_check.py --dry-run

    # Execute: promote eligible patterns in the database
    uv run python scripts/run_promotion_check.py --execute

    # With explicit DB URL
    uv run python scripts/run_promotion_check.py --execute \
        --db-url postgresql://postgres:password@192.168.86.201:5436/omniintelligence

Environment:
    OMNIINTELLIGENCE_DB_URL — PostgreSQL connection string (required unless --db-url)

Reference: OMN-7810 — Wire pattern promotion pipeline for alpha readiness.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class _AsyncpgPoolRepository:
    """Thin wrapper around an asyncpg pool implementing ProtocolPatternRepository."""

    __slots__ = ("_pool",)

    def __init__(self, pool: Any) -> None:  # any-ok: asyncpg.Pool
        self._pool = pool

    async def fetch(self, query: str, *args: object) -> list[Mapping[str, Any]]:
        rows = await self._pool.fetch(query, *args)
        return [dict(row) for row in rows]

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None:
        row = await self._pool.fetchrow(query, *args)
        return dict(row) if row is not None else None

    async def execute(self, query: str, *args: object) -> str:
        result = await self._pool.execute(query, *args)
        return str(result)


async def run_promotion(*, db_url: str, dry_run: bool) -> None:
    """Connect to the database and run the auto-promote check."""
    import asyncpg

    from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers import (
        apply_transition,
    )
    from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote import (
        handle_auto_promote_check,
    )

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    if pool is None:
        print("ERROR: Failed to create connection pool", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    repository = _AsyncpgPoolRepository(pool)
    correlation_id = uuid4()

    try:
        if dry_run:
            # In dry-run mode, just query eligible patterns and report
            from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote import (
                SQL_FETCH_CANDIDATE_PATTERNS,
                SQL_FETCH_PROVISIONAL_PATTERNS_WITH_TIER,
                meets_candidate_to_provisional_criteria,
                meets_provisional_to_validated_criteria,
            )

            candidates = await repository.fetch(SQL_FETCH_CANDIDATE_PATTERNS)
            eligible_candidates = [
                p for p in candidates if meets_candidate_to_provisional_criteria(p)
            ]

            provisionals = await repository.fetch(
                SQL_FETCH_PROVISIONAL_PATTERNS_WITH_TIER
            )
            eligible_provisionals = [
                p for p in provisionals if meets_provisional_to_validated_criteria(p)
            ]

            print(f"[DRY RUN] Promotion check (correlation_id={correlation_id})")  # noqa: T201
            print(f"  Candidates fetched:  {len(candidates)}")  # noqa: T201
            print(f"  Candidates eligible: {len(eligible_candidates)}")  # noqa: T201
            print(f"  Provisionals fetched:  {len(provisionals)}")  # noqa: T201
            print(f"  Provisionals eligible: {len(eligible_provisionals)}")  # noqa: T201
            print()  # noqa: T201

            if eligible_candidates:
                print("  Eligible candidates (would promote to PROVISIONAL):")  # noqa: T201
                for p in eligible_candidates[:20]:
                    sig = str(p.get("pattern_signature", ""))[:60]
                    tier = p.get("evidence_tier", "?")
                    conf = p.get("confidence", 0.0)
                    print(f"    - {p['id']}  tier={tier}  conf={conf:.2f}  sig={sig}")  # noqa: T201

            if eligible_provisionals:
                print("  Eligible provisionals (would promote to VALIDATED):")  # noqa: T201
                for p in eligible_provisionals[:20]:
                    sig = str(p.get("pattern_signature", ""))[:60]
                    tier = p.get("evidence_tier", "?")
                    inj = p.get("injection_count_rolling_20", 0)
                    print(f"    - {p['id']}  tier={tier}  inj={inj}  sig={sig}")  # noqa: T201

            print()  # noqa: T201
            print("  Run with --execute to apply promotions.")  # noqa: T201
            return

        # Execute mode: actually promote
        result = await handle_auto_promote_check(
            repository=repository,
            apply_transition_fn=apply_transition,
            idempotency_store=None,
            producer=None,  # type: ignore[arg-type]  # Kafka optional — DB-only transitions
            correlation_id=correlation_id,
            publish_topic=None,
        )

        print(f"Promotion check completed (correlation_id={correlation_id})")  # noqa: T201
        print(f"  Candidates checked:   {result['candidates_checked']}")  # noqa: T201
        print(f"  Candidates promoted:  {result['candidates_promoted']}")  # noqa: T201
        print(f"  Provisionals checked: {result['provisionals_checked']}")  # noqa: T201
        print(f"  Provisionals promoted:{result['provisionals_promoted']}")  # noqa: T201

        if result["results"]:
            print()  # noqa: T201
            promoted = [r for r in result["results"] if r["promoted"]]
            skipped = [r for r in result["results"] if not r["promoted"]]
            if promoted:
                print(f"  Promoted ({len(promoted)}):")  # noqa: T201
                for r in promoted[:30]:
                    print(  # noqa: T201
                        f"    - {r['pattern_id']}  {r['from_status']} -> {r['to_status']}  "
                        f"tier={r['evidence_tier']}"
                    )
            if skipped:
                print(f"  Skipped ({len(skipped)}):")  # noqa: T201
                for r in skipped[:10]:
                    print(f"    - {r['pattern_id']}  reason={r['reason']}")  # noqa: T201

    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run pattern promotion check directly against PostgreSQL."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Report eligible patterns without promoting.",
    )
    group.add_argument(
        "--execute",
        action="store_true",
        help="Actually promote eligible patterns.",
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("OMNIINTELLIGENCE_DB_URL", ""),
        help="PostgreSQL connection string (default: $OMNIINTELLIGENCE_DB_URL).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db_url = args.db_url
    if not db_url:
        print(  # noqa: T201
            "ERROR: No database URL. Set OMNIINTELLIGENCE_DB_URL or pass --db-url.",
            file=sys.stderr,
        )
        sys.exit(1)

    asyncio.run(run_promotion(db_url=db_url, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
