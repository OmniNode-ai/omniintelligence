# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Golden chain test for node_bloom_eval_orchestrator → intelligenceBloomEvalResults.

Verifies the full event flow:
  ModelBloomEvalRunCommand → run_bloom_eval handler →
  bloom-eval-completed event published to Kafka →
  consumer read path (mocked) → projection row shape matches
  intelligenceBloomEvalResults schema.

Reference: OMN-8645
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_bloom_eval_orchestrator.handlers.handler_bloom_eval_effect import (
    ModelBloomEvalRunCommand,
    run_bloom_eval,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BLOOM_EVAL_COMPLETED_TOPIC = "onex.evt.omniintelligence.bloom-eval-completed.v1"

# Required projection columns (matches intelligenceBloomEvalResults Drizzle schema)
_REQUIRED_PROJECTION_FIELDS: frozenset[str] = frozenset(
    {
        "suite_id",
        "spec_id",
        "failure_mode",
        "total_scenarios",
        "passed_count",
        "failure_rate",
        "passed_threshold",
        "correlation_id",
        "emitted_at",
    }
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_llm_client(
    scenarios: list[str] | None = None,
    judgment: dict[str, Any] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.generate_scenarios = AsyncMock(
        return_value=scenarios or ["scenario_a", "scenario_b"]
    )
    client.judge_output = AsyncMock(
        return_value=judgment
        or {
            "metamorphic_stability_score": 0.9,
            "compliance_theater_risk": 0.1,
            "ambiguity_flags": [],
            "invented_requirements": [],
            "missing_acceptance_criteria": [],
            "schema_pass": True,
        }
    )
    return client


class MockKafkaPublisher:
    """Records published events without real Kafka."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        self.events.append((topic, key, value))

    def events_for(self, topic: str) -> list[dict[str, Any]]:
        return [v for t, _k, v in self.events if t == topic]


class MockProjectionConsumer:
    """Simulates the omnidash BloomEvalProjectionHandler read path.

    Projects a bloom-eval-completed payload into an in-memory row that
    mirrors the intelligence_bloom_eval_results table schema.
    """

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def project(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Simulate INSERT INTO intelligence_bloom_eval_results."""
        suite_id = payload.get("suite_id")
        spec_id = payload.get("spec_id")
        if not suite_id or not spec_id:
            return None

        row: dict[str, Any] = {
            "suite_id": suite_id,
            "spec_id": spec_id,
            "failure_mode": payload.get("failure_mode", ""),
            "total_scenarios": payload.get("total_scenarios", 0),
            "passed_count": payload.get("passed_count", 0),
            "failure_rate": payload.get("failure_rate", 0.0),
            "passed_threshold": bool(payload.get("passed_threshold", False)),
            "correlation_id": payload.get("correlation_id"),
            "emitted_at": payload.get("emitted_at"),
        }
        self.rows.append(row)
        return row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestBloomEvalGoldenChain:
    """Golden chain: orchestrator → Kafka event → projection row shape."""

    async def test_orchestrator_emits_bloom_eval_completed_event(self) -> None:
        """run_bloom_eval must emit one bloom-eval-completed event."""
        command = ModelBloomEvalRunCommand(
            failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
            scenarios_per_spec=2,
        )
        publisher = MockKafkaPublisher()
        llm = _make_llm_client()

        await run_bloom_eval(command, producer=publisher, llm_client=llm)
        await asyncio.sleep(0)

        events = publisher.events_for(BLOOM_EVAL_COMPLETED_TOPIC)
        assert len(events) == 1, f"Expected 1 event; got {len(events)}"

    async def test_emitted_event_contains_all_required_projection_fields(self) -> None:
        """Published payload must contain every field consumed by the DB projector."""
        command = ModelBloomEvalRunCommand(
            failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
            scenarios_per_spec=2,
        )
        publisher = MockKafkaPublisher()
        llm = _make_llm_client()

        await run_bloom_eval(command, producer=publisher, llm_client=llm)
        await asyncio.sleep(0)

        payload = publisher.events_for(BLOOM_EVAL_COMPLETED_TOPIC)[0]
        missing = _REQUIRED_PROJECTION_FIELDS - set(payload.keys())
        assert not missing, f"Payload missing fields: {missing}"

    async def test_projection_row_shape_matches_intelligence_bloom_eval_results(
        self,
    ) -> None:
        """Mock consumer must produce a row with all table columns populated."""
        command = ModelBloomEvalRunCommand(
            failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
            correlation_id="golden-chain-test-001",
            scenarios_per_spec=2,
        )
        publisher = MockKafkaPublisher()
        llm = _make_llm_client()

        await run_bloom_eval(command, producer=publisher, llm_client=llm)
        await asyncio.sleep(0)

        payload = publisher.events_for(BLOOM_EVAL_COMPLETED_TOPIC)[0]
        consumer = MockProjectionConsumer()
        row = consumer.project(payload)

        assert row is not None, "Consumer returned None — missing suite_id or spec_id"
        assert set(row.keys()) == _REQUIRED_PROJECTION_FIELDS

    async def test_projection_row_suite_id_matches_command(self) -> None:
        """Projected suite_id must match the originating command's suite_id."""
        command = ModelBloomEvalRunCommand(
            failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
            scenarios_per_spec=2,
        )
        publisher = MockKafkaPublisher()
        llm = _make_llm_client()

        await run_bloom_eval(command, producer=publisher, llm_client=llm)
        await asyncio.sleep(0)

        payload = publisher.events_for(BLOOM_EVAL_COMPLETED_TOPIC)[0]
        consumer = MockProjectionConsumer()
        row = consumer.project(payload)

        assert row is not None
        assert row["suite_id"] == str(command.suite_id)

    async def test_projection_row_failure_mode_round_trips(self) -> None:
        """failure_mode value must survive the orchestrator → payload → projection round-trip."""
        for failure_mode in (
            EnumFailureMode.REQUIREMENT_OMISSION,
            EnumFailureMode.UNSAFE_TOOL_SEQUENCING,
            EnumFailureMode.REGRESSION_AMNESIA,
        ):
            command = ModelBloomEvalRunCommand(
                failure_mode=failure_mode,
                scenarios_per_spec=2,
            )
            publisher = MockKafkaPublisher()
            llm = _make_llm_client()

            await run_bloom_eval(command, producer=publisher, llm_client=llm)
            await asyncio.sleep(0)

            payload = publisher.events_for(BLOOM_EVAL_COMPLETED_TOPIC)[0]
            consumer = MockProjectionConsumer()
            row = consumer.project(payload)

            assert row is not None
            assert row["failure_mode"] == failure_mode.value, (
                f"failure_mode mismatch for {failure_mode}"
            )

    async def test_projection_row_passed_threshold_true_for_all_passing(self) -> None:
        """passed_threshold must be True when all scenarios pass."""
        command = ModelBloomEvalRunCommand(
            failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
            scenarios_per_spec=2,
        )
        publisher = MockKafkaPublisher()
        llm = _make_llm_client(
            scenarios=["s1", "s2"],
            judgment={
                "metamorphic_stability_score": 0.95,
                "compliance_theater_risk": 0.05,
                "ambiguity_flags": [],
                "invented_requirements": [],
                "missing_acceptance_criteria": [],
                "schema_pass": True,
            },
        )

        await run_bloom_eval(command, producer=publisher, llm_client=llm)
        await asyncio.sleep(0)

        payload = publisher.events_for(BLOOM_EVAL_COMPLETED_TOPIC)[0]
        consumer = MockProjectionConsumer()
        row = consumer.project(payload)

        assert row is not None
        assert row["passed_threshold"] is True

    async def test_projection_row_passed_threshold_false_for_all_failing(
        self,
    ) -> None:
        """passed_threshold must be False when all scenarios fail."""
        command = ModelBloomEvalRunCommand(
            failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
            scenarios_per_spec=2,
        )
        publisher = MockKafkaPublisher()
        llm = _make_llm_client(
            scenarios=["s1", "s2"],
            judgment={
                "metamorphic_stability_score": 0.1,
                "compliance_theater_risk": 0.9,
                "ambiguity_flags": ["flag"],
                "invented_requirements": ["req"],
                "missing_acceptance_criteria": ["crit"],
                "schema_pass": False,
            },
        )

        await run_bloom_eval(command, producer=publisher, llm_client=llm)
        await asyncio.sleep(0)

        payload = publisher.events_for(BLOOM_EVAL_COMPLETED_TOPIC)[0]
        consumer = MockProjectionConsumer()
        row = consumer.project(payload)

        assert row is not None
        assert row["passed_threshold"] is False

    async def test_projection_row_total_scenarios_matches_llm_output(self) -> None:
        """total_scenarios in projected row must equal number of LLM-returned scenarios."""
        scenarios = ["x1", "x2", "x3"]
        command = ModelBloomEvalRunCommand(
            failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
            scenarios_per_spec=3,
        )
        publisher = MockKafkaPublisher()
        llm = _make_llm_client(scenarios=scenarios)

        await run_bloom_eval(command, producer=publisher, llm_client=llm)
        await asyncio.sleep(0)

        payload = publisher.events_for(BLOOM_EVAL_COMPLETED_TOPIC)[0]
        consumer = MockProjectionConsumer()
        row = consumer.project(payload)

        assert row is not None
        assert row["total_scenarios"] == len(scenarios)

    async def test_correlation_id_preserved_through_chain(self) -> None:
        """correlation_id must flow from command → payload → projection row."""
        cid = "bloom-chain-corr-xyz"
        command = ModelBloomEvalRunCommand(
            failure_mode=EnumFailureMode.COMPLIANCE_THEATER,
            correlation_id=cid,
            scenarios_per_spec=1,
        )
        publisher = MockKafkaPublisher()
        llm = _make_llm_client(scenarios=["s1"])

        await run_bloom_eval(command, producer=publisher, llm_client=llm)
        await asyncio.sleep(0)

        payload = publisher.events_for(BLOOM_EVAL_COMPLETED_TOPIC)[0]
        consumer = MockProjectionConsumer()
        row = consumer.project(payload)

        assert row is not None
        assert row["correlation_id"] == cid

    async def test_event_bus_delivery_round_trip(self) -> None:
        """Verify EventBusInmemory delivers the event and payload is parseable."""
        try:
            from omnibase_infra.event_bus.event_bus_inmemory import EventBusInmemory
            from omnibase_infra.models import ModelNodeIdentity
        except ImportError:
            pytest.skip("omnibase_infra not installed")

        bus = EventBusInmemory(environment="test", group="test-group")
        await bus.start()

        received: list[bytes] = []
        identity = ModelNodeIdentity(
            env="test",
            service="omniintelligence",
            node_name="bloom_eval_orchestrator",
            version="1.0.0",
        )

        try:
            unsub = await bus.subscribe(
                BLOOM_EVAL_COMPLETED_TOPIC,
                identity,
                lambda msg: received.append(msg.value),
            )

            # Publish directly as if the handler had fired
            test_payload = {
                "suite_id": str(uuid4()),
                "spec_id": str(uuid4()),
                "failure_mode": EnumFailureMode.REQUIREMENT_OMISSION.value,
                "total_scenarios": 2,
                "passed_count": 2,
                "failure_rate": 0.0,
                "passed_threshold": True,
                "correlation_id": "bus-test-corr",
                "emitted_at": datetime.now(UTC).isoformat(),
            }
            await bus.publish(
                BLOOM_EVAL_COMPLETED_TOPIC,
                key=test_payload["suite_id"].encode(),
                value=json.dumps(test_payload).encode(),
            )

            assert len(received) == 1
            delivered = json.loads(received[0])
            assert delivered["suite_id"] == test_payload["suite_id"]
            assert delivered["failure_mode"] == test_payload["failure_mode"]

            await unsub()
        finally:
            await bus.close()

    async def test_consumer_drops_payload_missing_suite_id(self) -> None:
        """MockProjectionConsumer must return None if suite_id is absent (matches handler guard)."""
        consumer = MockProjectionConsumer()
        result = consumer.project({"spec_id": str(uuid4()), "failure_mode": "x"})
        assert result is None

    async def test_consumer_drops_payload_missing_spec_id(self) -> None:
        """MockProjectionConsumer must return None if spec_id is absent."""
        consumer = MockProjectionConsumer()
        result = consumer.project({"suite_id": str(uuid4()), "failure_mode": "x"})
        assert result is None


__all__ = ["TestBloomEvalGoldenChain"]
