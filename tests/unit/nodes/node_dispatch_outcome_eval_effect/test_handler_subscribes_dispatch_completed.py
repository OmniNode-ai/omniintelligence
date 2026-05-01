# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler tests for node_dispatch_outcome_eval_effect."""

from __future__ import annotations

import pytest

from omniintelligence.constants import (
    TOPIC_DISPATCH_OUTCOME_EVALUATED_V1,
    TOPIC_OMNICLAUDE_DISPATCH_WORKER_COMPLETED_V1,
)
from omniintelligence.nodes.node_dispatch_outcome_eval_effect.handlers.handler_dispatch_outcome import (
    PUBLISH_TOPIC,
    SUBSCRIBE_TOPIC,
    handle_dispatch_outcome,
)
from omniintelligence.nodes.node_dispatch_outcome_eval_effect.models import (
    EnumUsageSource,
    ModelCallRecord,
    ModelCostProvenance,
    ModelInput,
)

pytestmark = pytest.mark.unit


def _make_event(status: str, artifact_path: str | None = None) -> ModelInput:
    return ModelInput(
        task_id="task-123",
        dispatch_id="dispatch-456",
        ticket_id="OMN-10380",
        status=status,
        artifact_path=artifact_path,
        model_calls=[
            ModelCallRecord(
                provider="claude_code",
                model="claude_subprocess",
                input_tokens=700,
                output_tokens=300,
                latency_ms=25,
                cost_dollars=0.25,
                cost_provenance=ModelCostProvenance(
                    usage_source=EnumUsageSource.ESTIMATED,
                    estimation_method="test_estimate",
                ),
            )
        ],
        token_cost=1000,
        dollars_cost=0.25,
        cost_provenance=ModelCostProvenance(
            usage_source=EnumUsageSource.ESTIMATED,
            estimation_method="model_call_rollup",
        ),
    )


def test_handler_topics_match_dispatch_contract() -> None:
    """Handler topic constants match the dispatch outcome contract surface."""
    assert SUBSCRIBE_TOPIC == TOPIC_OMNICLAUDE_DISPATCH_WORKER_COMPLETED_V1
    assert PUBLISH_TOPIC == TOPIC_DISPATCH_OUTCOME_EVALUATED_V1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_verdict"),
    [
        ("completed", "PASS"),
        ("success", "PASS"),
        ("failed", "FAIL"),
        ("error", "ERROR"),
    ],
)
async def test_handler_routes_terminal_status_to_verdict(
    status: str,
    expected_verdict: str,
) -> None:
    """Handler maps terminal dispatch statuses to verdicts."""
    event = _make_event(status)

    result = await handle_dispatch_outcome(event)

    assert result.verdict == expected_verdict
    assert result.quality_score is None
    assert result.model_calls == len(event.model_calls)
    assert result.token_cost == event.token_cost
    assert result.dollars_cost == event.dollars_cost
    assert result.usage_source == "estimated"
    assert result.estimation_method == "model_call_rollup"
    assert result.published_event_id is None
    assert len(result.source_payload_hash) == 64
    assert result.eval_latency_ms >= 0
