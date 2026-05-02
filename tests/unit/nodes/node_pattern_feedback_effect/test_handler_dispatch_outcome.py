# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for dispatch outcome recording in node_pattern_feedback_effect."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from omnibase_core.enums.cost import EnumUsageSource
from omnibase_core.enums.enum_dispatch_verdict import EnumDispatchVerdict
from omnibase_core.models.cost import ModelCostProvenance
from omnibase_core.models.dispatch import ModelCallRecord, ModelDispatchEvalResult

from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
    record_dispatch_outcome,
)
from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    EnumOutcomeRecordingStatus,
)

pytestmark = pytest.mark.unit


class MockDispatchRepository:
    """In-memory repository for dispatch_eval_results UPSERT assertions."""

    def __init__(self) -> None:
        self.dispatch_eval_results: dict[tuple[str, str], dict[str, Any]] = {}
        self.queries_executed: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: object) -> list[dict[str, Any]]:
        self.queries_executed.append((query, args))
        return []

    async def fetchrow(self, query: str, *args: object) -> dict[str, Any] | None:
        self.queries_executed.append((query, args))
        return None

    async def execute(self, query: str, *args: object) -> str:
        self.queries_executed.append((query, args))
        assert "ON CONFLICT (task_id, dispatch_id) DO UPDATE" in query
        key = (str(args[0]), str(args[1]))
        self.dispatch_eval_results[key] = {
            "task_id": args[0],
            "dispatch_id": args[1],
            "ticket_id": args[2],
            "verdict": args[3],
            "quality_score": args[4],
            "token_cost": args[5],
            "dollars_cost": args[6],
            "model_calls": json.loads(str(args[7])),
            "evaluated_at": args[8],
            "eval_latency_ms": args[9],
            "usage_source": args[10],
            "estimation_method": args[11],
            "source_payload_hash": args[12],
        }
        return "INSERT 0 1"


def _dispatch_result(
    *,
    task_id: str = "t1",
    dispatch_id: str = "d1",
    verdict: EnumDispatchVerdict = EnumDispatchVerdict.PASS,
    quality_score: float | None = 0.85,
    token_cost: int = 12_500,
    dollars_cost: float = 0.031,
) -> ModelDispatchEvalResult:
    return ModelDispatchEvalResult(
        task_id=task_id,
        dispatch_id=dispatch_id,
        ticket_id="OMN-10388",
        verdict=verdict,
        quality_score=quality_score,
        token_cost=token_cost,
        dollars_cost=dollars_cost,
        cost_provenance=ModelCostProvenance(
            usage_source=EnumUsageSource.MEASURED,
            source_payload_hash="a" * 64,
        ),
        model_calls=[
            ModelCallRecord(
                provider="anthropic",
                model="claude-sonnet-4",
                input_tokens=10_000,
                output_tokens=2_500,
                latency_ms=750,
                cost_dollars=dollars_cost,
                cost_provenance=ModelCostProvenance(
                    usage_source=EnumUsageSource.MEASURED,
                    source_payload_hash="b" * 64,
                ),
            )
        ],
        evaluated_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        eval_latency_ms=42,
    )


@pytest.mark.asyncio
async def test_record_dispatch_outcome_upserts_cost_provenance() -> None:
    repo = MockDispatchRepository()

    result = await record_dispatch_outcome(_dispatch_result(), repository=repo)

    assert result.status == EnumOutcomeRecordingStatus.SUCCESS
    assert result.task_id == "t1"
    assert result.dispatch_id == "d1"
    assert result.rows_updated == 1

    row = repo.dispatch_eval_results[("t1", "d1")]
    assert row["verdict"] == "PASS"
    assert row["quality_score"] == 0.85
    assert row["token_cost"] == 12_500
    assert row["dollars_cost"] == 0.031
    assert row["usage_source"] == "MEASURED"
    assert row["estimation_method"] is None
    assert row["source_payload_hash"] == "a" * 64
    assert row["model_calls"][0]["model"] == "claude-sonnet-4"


@pytest.mark.asyncio
async def test_record_dispatch_outcome_records_pass_fail_error_rows() -> None:
    repo = MockDispatchRepository()

    for dispatch_id, verdict in (
        ("d-pass", EnumDispatchVerdict.PASS),
        ("d-fail", EnumDispatchVerdict.FAIL),
        ("d-error", EnumDispatchVerdict.ERROR),
    ):
        await record_dispatch_outcome(
            _dispatch_result(
                dispatch_id=dispatch_id,
                verdict=verdict,
                quality_score=0.85 if verdict == EnumDispatchVerdict.PASS else None,
            ),
            repository=repo,
        )

    assert set(repo.dispatch_eval_results) == {
        ("t1", "d-pass"),
        ("t1", "d-fail"),
        ("t1", "d-error"),
    }
    assert repo.dispatch_eval_results[("t1", "d-pass")]["verdict"] == "PASS"
    assert repo.dispatch_eval_results[("t1", "d-fail")]["verdict"] == "FAIL"
    assert repo.dispatch_eval_results[("t1", "d-error")]["verdict"] == "ERROR"


@pytest.mark.asyncio
async def test_record_dispatch_outcome_replay_updates_one_row() -> None:
    repo = MockDispatchRepository()

    await record_dispatch_outcome(_dispatch_result(token_cost=12_500), repository=repo)
    await record_dispatch_outcome(_dispatch_result(token_cost=13_000), repository=repo)

    assert list(repo.dispatch_eval_results) == [("t1", "d1")]
    assert repo.dispatch_eval_results[("t1", "d1")]["token_cost"] == 13_000
