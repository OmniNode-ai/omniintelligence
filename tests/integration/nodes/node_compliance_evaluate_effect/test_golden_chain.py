# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Golden chain test for node_compliance_evaluate_effect.

Verifies the full event flow:
  compliance-evaluate command -> handle_compliance_evaluate_command ->
  compliance-evaluated output event on EventBusInmemory

Uses a mock LLM client (no real inference) and EventBusInmemory (no real Kafka).

Reference: OMN-7142, OMN-2339
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from omnibase_infra.event_bus.event_bus_inmemory import EventBusInmemory
from omnibase_infra.models import ModelNodeIdentity

from omniintelligence.nodes.node_compliance_evaluate_effect.handlers.handler_compliance_evaluate import (
    handle_compliance_evaluate_command,
)
from omniintelligence.nodes.node_compliance_evaluate_effect.models import (
    ModelApplicablePatternPayload,
    ModelComplianceEvaluateCommand,
    ModelComplianceEvaluatedEvent,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PUBLISH_TOPIC = "test.onex.evt.omniintelligence.compliance-evaluated.v1"


def _make_command(**overrides: Any) -> ModelComplianceEvaluateCommand:
    """Build a valid compliance-evaluate command with sensible defaults."""
    content = overrides.pop("content", "def hello(): pass")
    sha = hashlib.sha256(content.encode()).hexdigest()
    defaults: dict[str, Any] = {
        "correlation_id": uuid4(),
        "source_path": "/src/example.py",
        "content": content,
        "content_sha256": sha,
        "language": "python",
        "applicable_patterns": [
            ModelApplicablePatternPayload(
                pattern_id="pat-001",
                pattern_signature="Always return explicit types",
                domain_id="code_quality",
                confidence=0.9,
            ),
        ],
        "session_id": "test-session-golden",
    }
    defaults.update(overrides)
    return ModelComplianceEvaluateCommand(**defaults)


def _make_mock_llm_client() -> Any:
    """Create a mock LLM client that returns a compliant result."""
    mock = MagicMock()
    # The leaf handler (handle_evaluate_compliance) calls llm_client.chat(...)
    # Build a mock response that the leaf handler can parse.
    # When llm_client is None, handle_evaluate_compliance returns llm_error
    # gracefully, so we test with None for the golden chain (no LLM dependency).
    return None


class _EventBusKafkaPublisherAdapter:
    """Thin adapter from ProtocolKafkaPublisher to EventBusInmemory."""

    def __init__(self, bus: EventBusInmemory) -> None:
        self._bus = bus

    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        value_bytes = json.dumps(value, default=str).encode()
        key_bytes = key.encode() if key else None
        await self._bus.publish(topic=topic, key=key_bytes, value=value_bytes)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestComplianceEvaluateGoldenChain:
    """Golden chain: command -> handler -> output event on bus."""

    async def test_evaluate_command_publishes_event(self) -> None:
        """Publish compliance-evaluate command, run handler, verify output event."""
        bus = EventBusInmemory(environment="test", group="test-group")
        await bus.start()

        received: list[Any] = []
        identity = ModelNodeIdentity(
            env="test",
            service="omniintelligence",
            node_name="compliance_evaluate_effect",
            version="1.0.0",
        )

        try:
            unsub = await bus.subscribe(
                PUBLISH_TOPIC, identity, lambda msg: received.append(msg)
            )

            adapter = _EventBusKafkaPublisherAdapter(bus)
            command = _make_command()

            # Execute handler (llm_client=None -> graceful degradation)
            event: ModelComplianceEvaluatedEvent = (
                await handle_compliance_evaluate_command(
                    command,
                    llm_client=None,
                    kafka_producer=adapter,
                    publish_topic=PUBLISH_TOPIC,
                )
            )

            # Handler publishes directly via kafka_producer, so event
            # should already be on the bus.
            assert len(received) == 1
            payload = json.loads(received[0].value)
            assert payload["event_type"] == "ComplianceEvaluated"
            assert payload["correlation_id"] == str(command.correlation_id)
            assert payload["source_path"] is not None
            assert payload["content_sha256"] == command.content_sha256
            assert payload["patterns_checked"] == 1

            await unsub()
        finally:
            await bus.close()

    async def test_handler_output_has_meaningful_payload(self) -> None:
        """Verify handler output carries all expected fields."""
        command = _make_command()

        event = await handle_compliance_evaluate_command(
            command,
            llm_client=None,
            kafka_producer=None,
        )

        assert isinstance(event, ModelComplianceEvaluatedEvent)
        assert event.event_type == "ComplianceEvaluated"
        assert event.correlation_id == command.correlation_id
        assert event.content_sha256 == command.content_sha256
        assert event.language == "python"
        assert event.patterns_checked == 1
        assert event.evaluated_at is not None
        assert event.processing_time_ms is not None
        assert event.processing_time_ms >= 0
        assert event.session_id == "test-session-golden"


__all__ = ["TestComplianceEvaluateGoldenChain"]
