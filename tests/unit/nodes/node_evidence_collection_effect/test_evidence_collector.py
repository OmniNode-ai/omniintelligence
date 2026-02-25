# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for EvidenceCollector — pure extraction logic (OMN-2578).

These tests verify the pure evidence extraction logic with no I/O dependencies.
All tests are marked as unit tests.
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_evidence_collection_effect.errors import (
    DisallowedEvidenceSourceError,
)
from omniintelligence.nodes.node_evidence_collection_effect.handlers.handler_evidence_collection import (
    EvidenceCollector,
    _COST_NORMALIZATION_MAX_USD,
    _LATENCY_NORMALIZATION_MAX_SECONDS,
)
from omniintelligence.nodes.node_evidence_collection_effect.models.model_session_check_results import (
    ModelGateCheckResult,
    ModelSessionCheckResults,
    ModelStaticAnalysisResult,
    ModelTestRunResult,
)

pytestmark = pytest.mark.unit


# ============================================================================
# Helpers
# ============================================================================


def _results(**kwargs: object) -> ModelSessionCheckResults:
    """Build a ModelSessionCheckResults with defaults."""
    from datetime import UTC, datetime

    defaults: dict[str, object] = {
        "run_id": "run-001",
        "session_id": "sess-001",
        "gate_results": (),
        "test_results": (),
        "static_analysis_results": (),
        "cost_usd": None,
        "latency_seconds": None,
        "collected_at_utc": datetime.now(UTC).isoformat(),
    }
    defaults.update(kwargs)
    return ModelSessionCheckResults(**defaults)  # type: ignore[arg-type]


# ============================================================================
# Gate result extraction
# ============================================================================


class TestGateResultExtraction:
    def test_single_passing_gate(self) -> None:
        gate = ModelGateCheckResult(
            gate_id="pre_commit",
            passed=True,
            pass_rate=1.0,
            check_count=5,
            pass_count=5,
        )
        items = EvidenceCollector().collect(_results(gate_results=(gate,)))
        assert len(items) == 1
        item = items[0]
        assert item["source"] == "validator_result"
        assert item["item_id"] == "gate_pre_commit"
        assert item["value"] == pytest.approx(1.0)
        assert item["metadata"]["gate_id"] == "pre_commit"
        assert item["metadata"]["passed"] is True

    def test_failing_gate_has_zero_value(self) -> None:
        gate = ModelGateCheckResult(
            gate_id="mypy_strict",
            passed=False,
            pass_rate=0.0,
            check_count=10,
            pass_count=0,
        )
        items = EvidenceCollector().collect(_results(gate_results=(gate,)))
        assert items[0]["value"] == pytest.approx(0.0)

    def test_partial_gate_has_fractional_value(self) -> None:
        gate = ModelGateCheckResult(
            gate_id="lint",
            passed=False,
            pass_rate=0.7,
            check_count=10,
            pass_count=7,
        )
        items = EvidenceCollector().collect(_results(gate_results=(gate,)))
        assert items[0]["value"] == pytest.approx(0.7)

    def test_multiple_gates_all_collected(self) -> None:
        gates = (
            ModelGateCheckResult(gate_id="g1", passed=True, pass_rate=1.0),
            ModelGateCheckResult(gate_id="g2", passed=True, pass_rate=1.0),
            ModelGateCheckResult(gate_id="g3", passed=False, pass_rate=0.5),
        )
        items = EvidenceCollector().collect(_results(gate_results=gates))
        assert len(items) == 3
        assert items[0]["item_id"] == "gate_g1"
        assert items[1]["item_id"] == "gate_g2"
        assert items[2]["item_id"] == "gate_g3"


# ============================================================================
# Test run extraction
# ============================================================================


class TestTestRunExtraction:
    def test_full_pass_test_run(self) -> None:
        run = ModelTestRunResult(
            test_suite="unit",
            total_tests=20,
            passed_tests=20,
            pass_rate=1.0,
        )
        items = EvidenceCollector().collect(_results(test_results=(run,)))
        assert len(items) == 1
        assert items[0]["source"] == "test_output"
        assert items[0]["value"] == pytest.approx(1.0)

    def test_partial_pass_test_run(self) -> None:
        run = ModelTestRunResult(
            test_suite="integration",
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            pass_rate=0.8,
        )
        items = EvidenceCollector().collect(_results(test_results=(run,)))
        assert items[0]["value"] == pytest.approx(0.8)

    def test_test_run_metadata_includes_suite_name(self) -> None:
        run = ModelTestRunResult(
            test_suite="smoke",
            total_tests=5,
            passed_tests=5,
            pass_rate=1.0,
        )
        items = EvidenceCollector().collect(_results(test_results=(run,)))
        assert items[0]["metadata"]["test_suite"] == "smoke"


# ============================================================================
# Static analysis extraction
# ============================================================================


class TestStaticAnalysisExtraction:
    def test_clean_analysis(self) -> None:
        analysis = ModelStaticAnalysisResult(
            tool="mypy",
            files_checked=100,
            error_count=0,
            clean_rate=1.0,
        )
        items = EvidenceCollector().collect(_results(static_analysis_results=(analysis,)))
        assert items[0]["source"] == "static_analysis"
        assert items[0]["value"] == pytest.approx(1.0)

    def test_analysis_with_errors_has_zero_clean_rate(self) -> None:
        analysis = ModelStaticAnalysisResult(
            tool="ruff",
            error_count=5,
            clean_rate=0.0,
        )
        items = EvidenceCollector().collect(_results(static_analysis_results=(analysis,)))
        assert items[0]["value"] == pytest.approx(0.0)

    def test_analysis_tool_name_in_item_id(self) -> None:
        analysis = ModelStaticAnalysisResult(tool="pylint", clean_rate=1.0)
        items = EvidenceCollector().collect(_results(static_analysis_results=(analysis,)))
        assert items[0]["item_id"] == "static_pylint"


# ============================================================================
# Cost/latency normalization
# ============================================================================


class TestCostLatencyNormalization:
    def test_zero_cost_score_is_one(self) -> None:
        items = EvidenceCollector().collect(_results(cost_usd=0.0))
        assert items[0]["value"] == pytest.approx(1.0)

    def test_max_cost_score_is_zero(self) -> None:
        items = EvidenceCollector().collect(
            _results(cost_usd=_COST_NORMALIZATION_MAX_USD)
        )
        assert items[0]["value"] == pytest.approx(0.0, abs=1e-9)

    def test_half_cost_score_is_half(self) -> None:
        half_cost = _COST_NORMALIZATION_MAX_USD / 2
        items = EvidenceCollector().collect(_results(cost_usd=half_cost))
        assert items[0]["value"] == pytest.approx(0.5, abs=1e-6)

    def test_over_max_cost_clamps_to_zero(self) -> None:
        """Cost exceeding normalization max clamps to 0.0, not negative."""
        items = EvidenceCollector().collect(_results(cost_usd=10.0))
        assert items[0]["value"] == pytest.approx(0.0, abs=1e-9)

    def test_zero_latency_score_is_one(self) -> None:
        items = EvidenceCollector().collect(_results(latency_seconds=0.0))
        assert items[0]["value"] == pytest.approx(1.0)

    def test_max_latency_score_is_zero(self) -> None:
        items = EvidenceCollector().collect(
            _results(latency_seconds=_LATENCY_NORMALIZATION_MAX_SECONDS)
        )
        assert items[0]["value"] == pytest.approx(0.0, abs=1e-9)

    def test_over_max_latency_clamps_to_zero(self) -> None:
        """Latency exceeding max clamps to 0.0, not negative."""
        items = EvidenceCollector().collect(_results(latency_seconds=9999.0))
        assert items[0]["value"] == pytest.approx(0.0, abs=1e-9)

    def test_none_cost_produces_no_cost_item(self) -> None:
        items = EvidenceCollector().collect(_results(cost_usd=None))
        sources = [i["source"] for i in items]
        assert "cost_telemetry" not in sources

    def test_none_latency_produces_no_latency_item(self) -> None:
        items = EvidenceCollector().collect(_results(latency_seconds=None))
        sources = [i["source"] for i in items]
        assert "latency_telemetry" not in sources


# ============================================================================
# DisallowedEvidenceSourceError
# ============================================================================


class TestDisallowedEvidenceSourceError:
    def test_error_carries_source(self) -> None:
        err = DisallowedEvidenceSourceError(source="chat_log", reason="test reason")
        assert err.source == "chat_log"

    def test_error_carries_reason(self) -> None:
        err = DisallowedEvidenceSourceError(source="chat_log", reason="test reason")
        assert err.reason == "test reason"

    def test_error_message_contains_source(self) -> None:
        err = DisallowedEvidenceSourceError(source="llm_summary", reason="not allowed")
        assert "llm_summary" in str(err)

    def test_error_is_value_error_subclass(self) -> None:
        err = DisallowedEvidenceSourceError(source="x", reason="y")
        assert isinstance(err, ValueError)


# ============================================================================
# ModelRunEvaluatedEvent
# ============================================================================


class TestModelRunEvaluatedEvent:
    def test_default_failures_is_empty_tuple(self) -> None:
        from datetime import UTC, datetime

        from omniintelligence.nodes.node_evidence_collection_effect.models.model_run_evaluated_event import (
            ModelRunEvaluatedEvent,
        )

        evt = ModelRunEvaluatedEvent(
            run_id="r1",
            session_id="s1",
            bundle_fingerprint="fp1",
            passed=True,
            evaluated_at_utc=datetime.now(UTC).isoformat(),
        )
        assert evt.failures == ()
        assert evt.passed is True

    def test_score_fields_default_to_zero(self) -> None:
        from datetime import UTC, datetime

        from omniintelligence.nodes.node_evidence_collection_effect.models.model_run_evaluated_event import (
            ModelRunEvaluatedEvent,
        )

        evt = ModelRunEvaluatedEvent(
            run_id="r1",
            session_id="s1",
            bundle_fingerprint="fp1",
            passed=False,
            failures=("gate_a",),
            evaluated_at_utc=datetime.now(UTC).isoformat(),
        )
        assert evt.score_correctness == 0.0
        assert evt.score_safety == 0.0
        assert evt.score_cost == 0.0
        assert evt.score_latency == 0.0
        assert evt.score_maintainability == 0.0
        assert evt.score_human_time == 0.0


# ============================================================================
# ModelCollectionOutput
# ============================================================================


class TestModelCollectionOutput:
    def test_skipped_output_defaults(self) -> None:
        from omniintelligence.nodes.node_evidence_collection_effect.models.model_collection_output import (
            ModelCollectionOutput,
        )

        out = ModelCollectionOutput(
            run_id="r1",
            session_id="s1",
            skipped=True,
            skip_reason="no_evidence_items",
        )
        assert out.passed is None
        assert out.bundle_fingerprint is None
        assert out.kafka_emitted is False
        assert out.db_stored is False
        assert out.evidence_item_count == 0
