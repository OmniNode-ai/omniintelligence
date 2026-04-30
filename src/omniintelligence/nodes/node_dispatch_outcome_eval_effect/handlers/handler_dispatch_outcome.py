# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler skeleton for dispatch outcome evaluation."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Final, Literal

from omniintelligence.constants import (
    TOPIC_DISPATCH_OUTCOME_EVALUATED_V1,
    TOPIC_OMNICLAUDE_DISPATCH_WORKER_COMPLETED_V1,
)
from omniintelligence.nodes.node_dispatch_outcome_eval_effect.models import (
    ModelInput,
    ModelOutput,
)

SUBSCRIBE_TOPIC: Final[str] = TOPIC_OMNICLAUDE_DISPATCH_WORKER_COMPLETED_V1
PUBLISH_TOPIC: Final[str] = TOPIC_DISPATCH_OUTCOME_EVALUATED_V1


def _verdict_for_status(status: str) -> Literal["PASS", "FAIL", "ERROR"]:
    """Map producer terminal status to the skeleton evaluation verdict."""
    normalized_status = status.strip().lower()
    if normalized_status == "completed":
        return "PASS"
    if normalized_status == "failed":
        return "FAIL"
    if normalized_status == "error":
        return "ERROR"
    return "ERROR"


def _source_payload_hash(event: ModelInput) -> str:
    """Return a deterministic SHA-256 hash for the source payload."""
    payload = event.model_dump(mode="json")
    serialized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


async def handle_dispatch_outcome(event: ModelInput) -> ModelOutput:
    """Evaluate a dispatch worker completion event.

    OMN-10380 is intentionally a skeleton: no scoring, database write, or Kafka
    publish occurs here yet. The handler only normalizes status to a verdict and
    carries source usage fields forward.
    """
    started_at = time.perf_counter()
    evaluated_at = datetime.now(UTC)
    eval_latency_ms = int((time.perf_counter() - started_at) * 1000)

    return ModelOutput(
        verdict=_verdict_for_status(event.status),
        quality_score=None,
        token_cost=event.token_cost,
        dollars_cost=event.dollars_cost,
        model_calls=event.model_calls,
        usage_source=None,
        estimation_method=None,
        source_payload_hash=_source_payload_hash(event),
        published_event_id=None,
        evaluated_at=evaluated_at,
        eval_latency_ms=eval_latency_ms,
    )


__all__ = [
    "PUBLISH_TOPIC",
    "SUBSCRIBE_TOPIC",
    "handle_dispatch_outcome",
]
