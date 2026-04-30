# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler skeleton for dispatch outcome evaluation."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from omniintelligence.constants import (
    TOPIC_DISPATCH_OUTCOME_EVALUATED_V1,
    TOPIC_OMNICLAUDE_DISPATCH_WORKER_COMPLETED_V1,
)
from omniintelligence.nodes.node_dispatch_outcome_eval_effect.models import (
    ModelInput,
    ModelOutput,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    handle_quality_scoring_compute,
)
from omniintelligence.nodes.node_quality_scoring_compute.models import (
    ModelQualityScoringInput,
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


def _language_for_artifact(artifact_path: str) -> str | None:
    """Infer the quality-scoring language from a dispatch artifact path."""
    suffix = Path(artifact_path).suffix.lower()
    if suffix == ".py":
        return "python"
    return None


def _compute_quality_score(artifact_path: str) -> float | None:
    """Invoke node_quality_scoring_compute for a dispatch artifact."""
    artifact = Path(artifact_path)
    language = _language_for_artifact(artifact_path)
    if language is None:
        return None

    try:
        content = artifact.read_text(encoding="utf-8")
        scoring_result = handle_quality_scoring_compute(
            ModelQualityScoringInput(
                source_path=artifact_path,
                content=content,
                language=language,
            )
        )
    except (OSError, RuntimeError):
        return None

    return float(scoring_result.quality_score)


async def handle_dispatch_outcome(event: ModelInput) -> ModelOutput:
    """Evaluate a dispatch worker completion event.

    The handler normalizes dispatch status to a verdict, carries source usage
    fields forward, and invokes quality scoring when a dispatch artifact exists.
    Database writes and downstream projection publishing are intentionally out
    of scope here.
    """
    started_at = time.perf_counter()
    evaluated_at = datetime.now(UTC)
    quality_score = (
        _compute_quality_score(event.artifact_path)
        if event.artifact_path is not None
        else None
    )
    eval_latency_ms = int((time.perf_counter() - started_at) * 1000)

    return ModelOutput(
        verdict=_verdict_for_status(event.status),
        quality_score=quality_score,
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
