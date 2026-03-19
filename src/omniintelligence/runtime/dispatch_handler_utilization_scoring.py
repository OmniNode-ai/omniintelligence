# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Dispatch handler for LLM-based utilization scoring.

Receives a scoring command with session_id + injected pattern IDs,
looks up pattern signatures from DB, calls local Qwen3-14B to score
how much the session utilized the injected patterns, then emits
an updated context-utilization event with the real score.

Reference: OMN-5506 - Create LLM-based utilization scoring handler.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from omniintelligence.constants import TOPIC_CONTEXT_UTILIZATION_EVT_V1
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are evaluating whether injected code patterns were utilized in a coding session.

## Injected Patterns
{patterns}

## Session Outcome
{outcome}

## Task
Score from 0.0 to 1.0 how likely it is that these patterns influenced the session outcome.
- 1.0 = patterns were clearly central to the work done
- 0.5 = patterns may have been partially useful
- 0.0 = patterns were irrelevant to the session

Respond with JSON only: {{"utilization_score": <float>, "reasoning": "<one sentence>"}}"""


def create_utilization_scoring_dispatch_handler(
    *,
    repository: ProtocolPatternRepository,
    publisher: ProtocolKafkaPublisher,
    llm_client: Any,  # any-ok: duck-typed to ProtocolLlmClient.chat_completion
) -> Any:  # any-ok: dispatch handler callable
    """Create handler that scores pattern utilization via local LLM.

    Args:
        repository: Database repository for pattern signature lookup.
        publisher: Kafka publisher for emitting context-utilization events.
        llm_client: LLM client with async chat_completion(messages, model, temperature, max_tokens) -> str.

    Returns:
        Async handler callable for the dispatch engine.
    """

    async def handle(
        message: dict[str, Any],
    ) -> dict[str, Any]:  # any-ok: dispatch handler signature
        session_id = message["session_id"]
        correlation_id = message.get("correlation_id", str(uuid4()))
        session_outcome = message.get("session_outcome", "unknown")
        pattern_ids = message.get("injected_pattern_ids", [])

        if not pattern_ids:
            logger.debug("No patterns to score for session %s", session_id)
            return {"status": "skipped", "reason": "no_patterns"}

        # Look up pattern signatures
        placeholders = ", ".join(f"${i + 1}" for i in range(len(pattern_ids)))
        rows = await repository.fetch(
            f"SELECT id, pattern_signature FROM learned_patterns WHERE id::text IN ({placeholders})",
            *pattern_ids,
        )

        if not rows:
            logger.warning("No patterns found in DB for IDs: %s", pattern_ids)
            return {"status": "skipped", "reason": "patterns_not_found"}

        pattern_text = "\n".join(f"- {row['pattern_signature']}" for row in rows)

        # Call local LLM for scoring
        utilization_score = 0.0
        detection_method = "llm_qwen3_14b"
        try:
            prompt = SCORING_PROMPT.format(
                patterns=pattern_text,
                outcome=session_outcome,
            )
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="qwen3-14b",
                temperature=0.1,
                max_tokens=200,
            )
            parsed = json.loads(response)
            utilization_score = float(parsed.get("utilization_score", 0.0))
            utilization_score = max(0.0, min(1.0, utilization_score))
        except Exception:
            logger.exception("LLM scoring failed for session %s, using 0.0", session_id)
            detection_method = "llm_fallback"

        # Emit updated context-utilization event
        event = json.dumps(
            {
                "session_id": session_id,
                "correlation_id": correlation_id,
                "cohort": "treatment",
                "injection_occurred": True,
                "utilization_score": utilization_score,
                "utilization_method": detection_method,
                "detection_method": detection_method,
                "patterns_count": len(pattern_ids),
                "session_outcome": session_outcome,
            }
        ).encode()

        await publisher.publish(
            topic=TOPIC_CONTEXT_UTILIZATION_EVT_V1,
            key=session_id.encode(),
            value=event,
        )

        logger.info(
            "Utilization score computed",
            extra={
                "session_id": session_id,
                "score": utilization_score,
                "method": detection_method,
                "patterns_scored": len(rows),
            },
        )

        return {
            "status": "scored",
            "session_id": session_id,
            "utilization_score": utilization_score,
            "detection_method": detection_method,
        }

    return handle


__all__ = [
    "SCORING_PROMPT",
    "create_utilization_scoring_dispatch_handler",
]
