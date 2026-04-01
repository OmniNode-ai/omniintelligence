#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""End-to-end verification for Pattern Lifecycle Bootstrap + Context Effectiveness.

Verifies the full pipeline after all OMN-5496 epic tickets are merged:
1. Promotion scheduler is running (emitting promotion-check commands)
2. Bootstrap-eligible candidates were promoted to provisional
3. Context-utilization events reach omnidash (injection_effectiveness table)
4. /memory route loads in omnidash

Usage:
    source ~/.omnibase/.env
    uv run python scripts/verify_pattern_lifecycle_e2e.py

Reference: OMN-5509 - End-to-end verification.
"""

from __future__ import annotations

import asyncio
import os


async def check_pattern_lifecycle_status() -> bool:
    """Check that some patterns are in provisional status (not all candidate)."""
    import asyncpg

    dsn = os.environ.get("OMNIBASE_INFRA_DB_URL")
    if not dsn:
        print("[SKIP] OMNIBASE_INFRA_DB_URL not set")  # noqa: T201
        return False

    try:
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                "SELECT status, COUNT(*) as cnt FROM learned_patterns GROUP BY status ORDER BY status"
            )
            print("[CHECK] Pattern lifecycle status distribution:")  # noqa: T201
            has_provisional = False
            for row in rows:
                status = row["status"]
                cnt = row["cnt"]
                marker = " <--" if status == "provisional" else ""
                print(f"  {status}: {cnt}{marker}")  # noqa: T201
                if status == "provisional" and cnt > 0:
                    has_provisional = True

            if has_provisional:
                print("[PASS] Provisional patterns exist")  # noqa: T201
            else:
                print("[WARN] No provisional patterns yet (promotion may not have run)")  # noqa: T201
            return has_provisional
        finally:
            await conn.close()
    except Exception as e:
        print(f"[ERROR] DB check failed: {e}")  # noqa: T201
        return False


async def check_context_utilization_events() -> bool:
    """Check injection_effectiveness table for context_utilization events."""
    import asyncpg

    omnidash_dsn = os.environ.get("OMNIDASH_ANALYTICS_DB_URL")
    if not omnidash_dsn:
        # Try to construct from OMNIBASE_INFRA_DB_URL
        infra_dsn = os.environ.get("OMNIBASE_INFRA_DB_URL", "")
        if "localhost" in infra_dsn:
            omnidash_dsn = infra_dsn.replace("omnibase_infra", "omnidash_analytics")
        else:
            print("[SKIP] OMNIDASH_ANALYTICS_DB_URL not set")  # noqa: T201
            return False

    try:
        conn = await asyncpg.connect(omnidash_dsn)
        try:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM injection_effectiveness WHERE event_type = 'context_utilization'"
            )
            cnt = row["cnt"] if row else 0
            print(f"[CHECK] Context utilization events in omnidash: {cnt}")  # noqa: T201
            if cnt > 0:
                print("[PASS] Context utilization events present")  # noqa: T201
                return True
            else:
                print(
                    "[WARN] No context utilization events yet (requires a session with pattern injection)"
                )  # noqa: T201
                return False
        finally:
            await conn.close()
    except Exception as e:
        print(f"[ERROR] Omnidash DB check failed: {e}")  # noqa: T201
        return False


async def check_promotion_topic_has_messages() -> bool:
    """Check if promotion-check-requested topic has messages."""
    try:
        from aiokafka import AIOKafkaConsumer

        bootstrap = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
        from omniintelligence.constants import TOPIC_PROMOTION_CHECK_CMD_V1

        consumer = AIOKafkaConsumer(
            TOPIC_PROMOTION_CHECK_CMD_V1,
            bootstrap_servers=bootstrap,
            auto_offset_reset="earliest",
            consumer_timeout_ms=3000,
        )
        await consumer.start()
        try:
            messages = await consumer.getmany(timeout_ms=3000)
            total = sum(len(msgs) for msgs in messages.values())
            print(f"[CHECK] Promotion-check messages on topic: {total}")  # noqa: T201
            if total > 0:
                print("[PASS] Promotion scheduler is emitting")  # noqa: T201
                return True
            else:
                print(
                    "[WARN] No promotion-check messages yet (scheduler may not have fired)"
                )  # noqa: T201
                return False
        finally:
            await consumer.stop()
    except Exception as e:
        print(f"[ERROR] Kafka check failed: {e}")  # noqa: T201
        return False


async def main() -> None:
    """Run all E2E verification checks."""
    print("=" * 60)  # noqa: T201
    print("OMN-5509: Pattern Lifecycle E2E Verification")  # noqa: T201
    print("=" * 60)  # noqa: T201
    print()  # noqa: T201

    results = {}

    print("--- 1. Pattern Lifecycle Status ---")  # noqa: T201
    results["lifecycle"] = await check_pattern_lifecycle_status()
    print()  # noqa: T201

    print("--- 2. Context Utilization Events ---")  # noqa: T201
    results["utilization"] = await check_context_utilization_events()
    print()  # noqa: T201

    print("--- 3. Promotion Scheduler ---")  # noqa: T201
    results["scheduler"] = await check_promotion_topic_has_messages()
    print()  # noqa: T201

    print("=" * 60)  # noqa: T201
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Results: {passed}/{total} checks passed")  # noqa: T201

    if passed == total:
        print("[ALL PASS] Pipeline is fully operational")  # noqa: T201
    else:
        print("[PARTIAL] Some checks did not pass (may need time for events to flow)")  # noqa: T201

    print()  # noqa: T201
    print("Manual checks remaining:")  # noqa: T201
    print("  - Navigate to http://localhost:3000/context-effectiveness")  # noqa: T201
    print("  - Navigate to http://localhost:3000/memory")  # noqa: T201
    print("  - Verify non-zero metrics after a Claude Code session")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
