#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
Backfill historical episodes from routing decisions.

Reconstructs episode structure from existing agent_routing_decisions and
llm_routing_decisions rows in omnidash_analytics, writing to the rl_episodes
table for the Learned Decision Optimization Platform (OMN-5556).

Usage:
    source ~/.omnibase/.env
    uv run python scripts/backfill_episodes.py \
        --database-url "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5436/omnidash_analytics"

    # Dry run (default) — report only, no writes
    uv run python scripts/backfill_episodes.py \
        --database-url "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5436/omnidash_analytics" \
        --dry-run

    # Execute — actually write episodes
    uv run python scripts/backfill_episodes.py \
        --database-url "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5436/omnidash_analytics" \
        --execute
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from argparse import ArgumentParser
from dataclasses import dataclass, field
from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SURFACE_AGENT_ROUTING = "agent_routing"
SURFACE_LLM_ROUTING = "llm_routing"

# Deterministic UUID namespace for episode_id generation.
# Using a fixed namespace ensures that the same decision row always produces
# the same episode_id, which is the foundation of idempotency.
EPISODE_UUID_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# SQL to ensure the rl_episodes table exists.  This is compatible with the
# schema that OMN-5559 will create; if that migration has already run, this
# is a no-op thanks to IF NOT EXISTS.
CREATE_RL_EPISODES_DDL = """
CREATE TABLE IF NOT EXISTS rl_episodes (
    episode_id   UUID PRIMARY KEY,
    surface      TEXT        NOT NULL,
    decision_snapshot JSONB  NOT NULL DEFAULT '{}'::jsonb,
    action_taken JSONB       NOT NULL DEFAULT '{}'::jsonb,
    outcome_metrics  JSONB   NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    backfilled   BOOLEAN     NOT NULL DEFAULT false,
    source_table TEXT,
    source_id    UUID
);

CREATE INDEX IF NOT EXISTS idx_rl_episodes_surface
    ON rl_episodes (surface);
CREATE INDEX IF NOT EXISTS idx_rl_episodes_created_at
    ON rl_episodes (created_at);
CREATE INDEX IF NOT EXISTS idx_rl_episodes_backfilled
    ON rl_episodes (backfilled) WHERE backfilled = true;
"""

# ---------------------------------------------------------------------------
# Data quality filters
# ---------------------------------------------------------------------------


@dataclass
class RejectionStats:
    """Track rejection reasons during backfill."""

    counts: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        self.counts[reason] = self.counts.get(reason, 0) + 1

    @property
    def total(self) -> int:
        return sum(self.counts.values())


@dataclass
class BackfillReport:
    """Summary of a backfill run."""

    accepted: int = 0
    duplicates: int = 0
    rejections: RejectionStats = field(default_factory=RejectionStats)

    def print_report(self) -> None:
        print("\n" + "=" * 60)
        print("BACKFILL REPORT")
        print("=" * 60)
        print(f"  Accepted (inserted):  {self.accepted}")
        print(f"  Duplicates (skipped): {self.duplicates}")
        print(f"  Rejected (filtered):  {self.rejections.total}")
        if self.rejections.counts:
            print("  Rejection breakdown:")
            for reason, count in sorted(
                self.rejections.counts.items(), key=lambda x: -x[1]
            ):
                print(f"    - {reason}: {count}")
        print(
            f"  Total processed:      "
            f"{self.accepted + self.duplicates + self.rejections.total}"
        )
        print("=" * 60)


# ---------------------------------------------------------------------------
# Episode reconstruction
# ---------------------------------------------------------------------------


def make_episode_id(surface: str, source_id: str) -> uuid.UUID:
    """Deterministic episode_id from surface + source row id."""
    return uuid.uuid5(EPISODE_UUID_NAMESPACE, f"{surface}:{source_id}")


def _jsonb_safe(value: Any) -> Any:
    """Ensure a value is JSON-serialisable for JSONB columns."""
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {"raw": value}
    if isinstance(value, dict):
        return value
    return {"raw": str(value)}


def filter_agent_routing_row(
    row: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Apply data-quality filters to an agent_routing_decisions row.

    Returns (episode_dict, None) on success, or (None, rejection_reason).
    """
    # 1. Non-null created_at (emitted_at proxy)
    if row.get("created_at") is None:
        return None, "null_created_at"

    # 2. Unambiguous action identity — agent must be known
    agent = row.get("selected_agent")
    if not agent or agent in ("unknown", ""):
        return None, "unknown_agent"

    # 3. Must have some confidence signal (terminal outcome proxy)
    confidence = row.get("confidence_score")
    if confidence is None or float(confidence) == 0.0:
        return None, "zero_confidence"

    # 4. Reconstructable observation features — need at least context or reasoning
    has_context = row.get("context_snapshot") is not None
    has_reasoning = row.get("reasoning") is not None and row["reasoning"].strip() != ""
    has_request = row.get("user_request") is not None and row["user_request"].strip() != ""
    if not (has_context or has_reasoning or has_request):
        return None, "no_observation_features"

    # Build episode
    source_id = str(row["id"])
    episode_id = make_episode_id(SURFACE_AGENT_ROUTING, source_id)

    decision_snapshot: dict[str, Any] = {}
    if row.get("context_snapshot"):
        decision_snapshot["context_snapshot"] = _jsonb_safe(row["context_snapshot"])
    if row.get("user_request"):
        decision_snapshot["user_request"] = row["user_request"]
    if row.get("reasoning"):
        decision_snapshot["reasoning"] = row["reasoning"]
    if row.get("routing_strategy"):
        decision_snapshot["routing_strategy"] = row["routing_strategy"]
    if row.get("alternatives"):
        decision_snapshot["alternatives"] = _jsonb_safe(row["alternatives"])

    action_taken: dict[str, Any] = {
        "selected_agent": agent,
        "confidence_score": float(confidence),
    }
    if row.get("cache_hit") is not None:
        action_taken["cache_hit"] = row["cache_hit"]

    outcome_metrics: dict[str, Any] = {
        "routing_time_ms": row.get("routing_time_ms"),
    }
    # Include sub-confidence scores when available
    for key in (
        "trigger_confidence",
        "context_confidence",
        "capability_confidence",
        "historical_confidence",
    ):
        val = row.get(key)
        if val is not None:
            outcome_metrics[key] = float(val)
    if row.get("actual_success") is not None:
        outcome_metrics["actual_success"] = row["actual_success"]
    if row.get("execution_succeeded") is not None:
        outcome_metrics["execution_succeeded"] = row["execution_succeeded"]
    if row.get("actual_quality_score") is not None:
        outcome_metrics["actual_quality_score"] = float(row["actual_quality_score"])

    return {
        "episode_id": episode_id,
        "surface": SURFACE_AGENT_ROUTING,
        "decision_snapshot": json.dumps(decision_snapshot),
        "action_taken": json.dumps(action_taken),
        "outcome_metrics": json.dumps(outcome_metrics),
        "created_at": row["created_at"],
        "backfilled": True,
        "source_table": "agent_routing_decisions",
        "source_id": row["id"],
    }, None


def filter_llm_routing_row(
    row: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Apply data-quality filters to an llm_routing_decisions row.

    Returns (episode_dict, None) on success, or (None, rejection_reason).
    """
    # 1. Non-null created_at
    if row.get("created_at") is None:
        return None, "null_created_at"

    # 2. Unambiguous action identity
    agent = row.get("llm_agent")
    if not agent or agent in ("unknown", ""):
        return None, "unknown_agent"

    # 3. Must have confidence signal
    confidence = row.get("llm_confidence")
    if confidence is None or float(confidence) == 0.0:
        return None, "zero_confidence"

    # 4. Terminal outcome — agreement field is always present and boolean
    if row.get("agreement") is None:
        return None, "no_terminal_outcome"

    source_id = str(row["id"])
    episode_id = make_episode_id(SURFACE_LLM_ROUTING, source_id)

    decision_snapshot: dict[str, Any] = {
        "routing_prompt_version": row.get("routing_prompt_version"),
    }
    if row.get("intent"):
        decision_snapshot["intent"] = row["intent"]
    if row.get("model"):
        decision_snapshot["model"] = row["model"]

    action_taken: dict[str, Any] = {
        "llm_agent": agent,
        "llm_confidence": float(confidence),
        "used_fallback": row.get("used_fallback", False),
    }
    if row.get("fuzzy_agent"):
        action_taken["fuzzy_agent"] = row["fuzzy_agent"]
    if row.get("fuzzy_confidence") is not None:
        action_taken["fuzzy_confidence"] = float(row["fuzzy_confidence"])

    outcome_metrics: dict[str, Any] = {
        "agreement": row["agreement"],
        "llm_latency_ms": row.get("llm_latency_ms"),
        "fuzzy_latency_ms": row.get("fuzzy_latency_ms"),
    }
    if row.get("cost_usd") is not None:
        outcome_metrics["cost_usd"] = float(row["cost_usd"])
    if row.get("total_tokens") is not None:
        outcome_metrics["total_tokens"] = row["total_tokens"]
    if row.get("prompt_tokens") is not None:
        outcome_metrics["prompt_tokens"] = row["prompt_tokens"]
    if row.get("completion_tokens") is not None:
        outcome_metrics["completion_tokens"] = row["completion_tokens"]

    return {
        "episode_id": episode_id,
        "surface": SURFACE_LLM_ROUTING,
        "decision_snapshot": json.dumps(decision_snapshot),
        "action_taken": json.dumps(action_taken),
        "outcome_metrics": json.dumps(outcome_metrics),
        "created_at": row["created_at"],
        "backfilled": True,
        "source_table": "llm_routing_decisions",
        "source_id": row["id"],
    }, None


# ---------------------------------------------------------------------------
# Backfill execution
# ---------------------------------------------------------------------------


async def ensure_table(conn: asyncpg.Connection) -> None:
    """Create rl_episodes table if it does not exist."""
    await conn.execute(CREATE_RL_EPISODES_DDL)


async def fetch_existing_episode_ids(conn: asyncpg.Connection) -> set[uuid.UUID]:
    """Fetch all existing episode_ids for idempotency checks."""
    rows = await conn.fetch("SELECT episode_id FROM rl_episodes")
    return {row["episode_id"] for row in rows}


async def backfill_agent_routing(
    conn: asyncpg.Connection,
    existing_ids: set[uuid.UUID],
    report: BackfillReport,
    *,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """Process agent_routing_decisions rows."""
    rows = await conn.fetch("SELECT * FROM agent_routing_decisions ORDER BY created_at")
    episodes: list[dict[str, Any]] = []

    for row in rows:
        row_dict = dict(row)
        episode, rejection = filter_agent_routing_row(row_dict)
        if rejection:
            report.rejections.reject(f"agent_routing:{rejection}")
            continue
        assert episode is not None
        if episode["episode_id"] in existing_ids:
            report.duplicates += 1
            continue
        episodes.append(episode)

    return episodes


async def backfill_llm_routing(
    conn: asyncpg.Connection,
    existing_ids: set[uuid.UUID],
    report: BackfillReport,
    *,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """Process llm_routing_decisions rows."""
    rows = await conn.fetch("SELECT * FROM llm_routing_decisions ORDER BY created_at")
    episodes: list[dict[str, Any]] = []

    for row in rows:
        row_dict = dict(row)
        episode, rejection = filter_llm_routing_row(row_dict)
        if rejection:
            report.rejections.reject(f"llm_routing:{rejection}")
            continue
        assert episode is not None
        if episode["episode_id"] in existing_ids:
            report.duplicates += 1
            continue
        episodes.append(episode)

    return episodes


async def insert_episodes(
    conn: asyncpg.Connection,
    episodes: list[dict[str, Any]],
) -> int:
    """Batch-insert episodes with ON CONFLICT skip for idempotency."""
    if not episodes:
        return 0

    inserted = 0
    for ep in episodes:
        result = await conn.execute(
            """
            INSERT INTO rl_episodes
                (episode_id, surface, decision_snapshot, action_taken,
                 outcome_metrics, created_at, backfilled, source_table, source_id)
            VALUES ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb, $6, $7, $8, $9)
            ON CONFLICT (episode_id) DO NOTHING
            """,
            ep["episode_id"],
            ep["surface"],
            ep["decision_snapshot"],
            ep["action_taken"],
            ep["outcome_metrics"],
            ep["created_at"],
            ep["backfilled"],
            ep["source_table"],
            ep["source_id"],
        )
        # asyncpg returns "INSERT 0 1" or "INSERT 0 0"
        if result and result.endswith("1"):
            inserted += 1

    return inserted


async def run_backfill(database_url: str, *, dry_run: bool = True) -> BackfillReport:
    """
    Main backfill entry point.

    Args:
        database_url: PostgreSQL connection string.
        dry_run: If True, report only without writing.

    Returns:
        BackfillReport with counts.
    """
    report = BackfillReport()
    conn = await asyncpg.connect(database_url)
    try:
        await ensure_table(conn)
        existing_ids = await fetch_existing_episode_ids(conn)

        agent_episodes = await backfill_agent_routing(
            conn, existing_ids, report, dry_run=dry_run
        )
        llm_episodes = await backfill_llm_routing(
            conn, existing_ids, report, dry_run=dry_run
        )

        all_episodes = agent_episodes + llm_episodes

        if dry_run:
            report.accepted = len(all_episodes)
            print(f"\n[DRY RUN] Would insert {len(all_episodes)} episodes")
        else:
            report.accepted = await insert_episodes(conn, all_episodes)
            print(f"\nInserted {report.accepted} episodes")

        report.print_report()
        return report
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main() -> None:
    import os

    parser = ArgumentParser(
        description="Backfill rl_episodes from historical routing decisions"
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection URL (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Report only, no writes (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually write episodes to rl_episodes",
    )

    args = parser.parse_args()

    if not args.database_url:
        print("Error: --database-url or DATABASE_URL required")
        sys.exit(1)

    dry_run = not args.execute
    if dry_run:
        print("[DRY RUN MODE] — pass --execute to write")
    else:
        print("[EXECUTE MODE] — writing episodes to rl_episodes")

    report = await run_backfill(args.database_url, dry_run=dry_run)

    if report.accepted == 0 and report.duplicates == 0:
        print("\nNo episodes to backfill.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
