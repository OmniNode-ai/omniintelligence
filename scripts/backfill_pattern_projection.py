#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""One-time backfill script to publish a pattern projection snapshot to Kafka.

Reads all current validated/provisional patterns from the omniintelligence
learned_patterns table and publishes a pattern-projection.v1 snapshot event
to Kafka. The omnidash read-model consumer will project this into the
pattern_learning_artifacts table, replacing stale "requested" rows with
actual pattern data including lifecycle state and composite scores.

This script addresses OMN-5611 where the pattern-projection topic was empty
because the projection handler was only triggered by promotion/lifecycle
events, which never fired. The structural fix (wiring pattern-stored events
to the projection handler) prevents recurrence; this script backfills the
existing gap.

Re-running is safe: the omnidash projection handler uses upsert semantics
(ON CONFLICT DO UPDATE) keyed on pattern_id.

Usage:
    source ~/.omnibase/.env
    uv run python scripts/backfill_pattern_projection.py --dry-run
    uv run python scripts/backfill_pattern_projection.py --execute
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4


_SQL_QUERY_ALL_PATTERNS = """\
SELECT
    id,
    pattern_signature,
    domain_id,
    domain_version,
    confidence,
    status,
    quality_score,
    signature_hash,
    recurrence_count,
    first_seen_at,
    last_seen_at,
    distinct_days_seen,
    injection_count_rolling_20,
    success_count_rolling_20,
    failure_count_rolling_20,
    evidence_tier,
    created_at,
    updated_at
FROM learned_patterns
WHERE is_current = TRUE
  AND status IN ('candidate', 'provisional', 'validated')
ORDER BY quality_score DESC, confidence DESC
"""


def _compute_composite_score(row: dict) -> float:
    """Compute a composite score from available pattern data.

    Formula:
        composite = 0.4 * quality_score + 0.3 * confidence + 0.2 * recurrence_norm + 0.1 * days_norm

    quality_score: effectiveness ratio from injection feedback (0.0-1.0, default 0.5)
    confidence: ML extraction confidence (0.5-1.0)
    recurrence_norm: min(1.0, recurrence_count / 10) - how often the pattern recurs
    days_norm: min(1.0, distinct_days_seen / 5) - how many distinct days seen
    """
    quality = float(row.get("quality_score") or 0.5)
    confidence = float(row.get("confidence") or 0.5)
    recurrence = int(row.get("recurrence_count") or 1)
    days = int(row.get("distinct_days_seen") or 1)

    recurrence_norm = min(1.0, recurrence / 10.0)
    days_norm = min(1.0, days / 5.0)

    return round(0.4 * quality + 0.3 * confidence + 0.2 * recurrence_norm + 0.1 * days_norm, 6)


def _row_to_pattern_dict(row: dict) -> dict:
    """Convert a learned_patterns row to the pattern dict expected by omnidash projection."""
    composite = _compute_composite_score(row)

    return {
        "id": str(row["id"]),
        "pattern_id": str(row["id"]),
        "domain_id": row["domain_id"],
        "pattern_name": row["domain_id"],
        "pattern_type": row.get("evidence_tier", "unmeasured"),
        "status": row["status"],
        "lifecycle_state": row["status"],
        "quality_score": float(row.get("quality_score") or 0.5),
        "composite_score": composite,
        "confidence": float(row.get("confidence") or 0.5),
        "signature_hash": row.get("signature_hash", ""),
        "signature": {"hash": row.get("signature_hash", "")},
        "scoring_evidence": {
            "quality_score": float(row.get("quality_score") or 0.5),
            "confidence": float(row.get("confidence") or 0.5),
            "recurrence_count": int(row.get("recurrence_count") or 1),
            "distinct_days_seen": int(row.get("distinct_days_seen") or 1),
            "injection_count_rolling_20": int(row.get("injection_count_rolling_20") or 0),
            "success_count_rolling_20": int(row.get("success_count_rolling_20") or 0),
            "failure_count_rolling_20": int(row.get("failure_count_rolling_20") or 0),
            "evidence_tier": row.get("evidence_tier", "unmeasured"),
        },
        "metrics": {
            "recurrence_count": int(row.get("recurrence_count") or 1),
            "distinct_days_seen": int(row.get("distinct_days_seen") or 1),
        },
        "metadata": {
            "source": "backfill_pattern_projection",
            "domain_version": row.get("domain_version", "1.0.0"),
        },
    }


async def main(dry_run: bool) -> None:
    """Read patterns from DB and publish projection snapshot to Kafka."""
    db_url = os.environ.get("OMNIINTELLIGENCE_DB_URL")
    if not db_url:
        print("ERROR: OMNIINTELLIGENCE_DB_URL not set in environment", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    # Convert Docker-internal hostname to localhost for host-side scripts
    db_url = db_url.replace("@postgres:5432/", "@localhost:5436/")

    kafka_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")

    import asyncpg

    print(f"Connecting to database...")  # noqa: T201
    conn = await asyncpg.connect(db_url)

    try:
        rows = await conn.fetch(_SQL_QUERY_ALL_PATTERNS)
        print(f"Found {len(rows)} current patterns in learned_patterns")  # noqa: T201

        if not rows:
            print("No patterns to project. Exiting.")  # noqa: T201
            return

        # Build the projection snapshot
        patterns = [_row_to_pattern_dict(dict(row)) for row in rows]

        # Compute score distribution for summary
        scores = [p["composite_score"] for p in patterns]
        avg_score = sum(scores) / len(scores) if scores else 0
        min_score = min(scores) if scores else 0
        max_score = max(scores) if scores else 0

        snapshot_id = str(uuid4())
        snapshot_at = datetime.now(UTC).isoformat()

        snapshot = {
            "snapshot_id": snapshot_id,
            "snapshot_at": snapshot_at,
            "patterns": patterns,
            "total_count": len(patterns),
            "version": 1,
            "correlation_id": str(uuid4()),
        }

        # Status distribution
        by_status: dict[str, int] = {}
        for p in patterns:
            s = p["status"]
            by_status[s] = by_status.get(s, 0) + 1

        print(f"\nSnapshot summary:")  # noqa: T201
        print(f"  snapshot_id: {snapshot_id}")  # noqa: T201
        print(f"  total_count: {len(patterns)}")  # noqa: T201
        print(f"  by_status: {by_status}")  # noqa: T201
        print(f"  composite_score: avg={avg_score:.4f}, min={min_score:.4f}, max={max_score:.4f}")  # noqa: T201

        if dry_run:
            print(f"\n[DRY RUN] Would publish snapshot to:")  # noqa: T201
            print(f"  topic: onex.evt.omniintelligence.pattern-projection.v1")  # noqa: T201
            print(f"  kafka: {kafka_servers}")  # noqa: T201
            print(f"  payload size: {len(json.dumps(snapshot))} bytes")  # noqa: T201
            print("\nRun with --execute to actually publish")  # noqa: T201
            return

        from aiokafka import AIOKafkaProducer

        from omniintelligence.constants import TOPIC_SUFFIX_PATTERN_PROJECTION_V1

        topic = TOPIC_SUFFIX_PATTERN_PROJECTION_V1
        print(f"\nPublishing to {topic} via {kafka_servers}...")  # noqa: T201

        # Chunk patterns into batches to stay under Kafka message size limits
        batch_size = 200  # ~200 patterns per message stays well under 1MB
        batches = [patterns[i : i + batch_size] for i in range(0, len(patterns), batch_size)]

        producer = AIOKafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
        await producer.start()
        try:
            for batch_idx, batch in enumerate(batches):
                batch_snapshot = {
                    "snapshot_id": str(uuid4()),
                    "snapshot_at": snapshot_at,
                    "patterns": batch,
                    "total_count": len(batch),
                    "version": 1,
                    "correlation_id": str(uuid4()),
                }
                await producer.send_and_wait(
                    topic,
                    key=batch_snapshot["snapshot_id"].encode(),
                    value=batch_snapshot,
                )
                print(  # noqa: T201
                    f"  Published batch {batch_idx + 1}/{len(batches)} "
                    f"({len(batch)} patterns)"
                )
            print(f"Published {len(patterns)} patterns in {len(batches)} batches")  # noqa: T201
        finally:
            await producer.stop()

    finally:
        await conn.close()


if __name__ == "__main__":
    is_dry_run = "--execute" not in sys.argv
    if is_dry_run and "--dry-run" not in sys.argv:
        print("Usage: uv run python scripts/backfill_pattern_projection.py --dry-run|--execute")  # noqa: T201
        sys.exit(1)
    asyncio.run(main(dry_run=is_dry_run))
