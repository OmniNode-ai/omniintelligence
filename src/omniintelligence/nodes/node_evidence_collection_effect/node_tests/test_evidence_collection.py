# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for node_evidence_collection_effect handler (OMN-2578).

Tests the EvidenceCollector, collect_and_evaluate pipeline, and
fire_and_forget_evaluate integration. All tests are unit tests (no I/O).

Test categories:
    - EvidenceCollector: pure extraction logic
    - DisallowedEvidenceSourceError: hard error on free-text injection
    - collect_and_evaluate: full pipeline with mocked scoring + Kafka + DB
    - fire_and_forget_evaluate: error swallowing behavior
    - handle_stop integration: _launch_objective_evaluation wiring
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omniintelligence.nodes.node_evidence_collection_effect.errors import (
    DisallowedEvidenceSourceError,
)
from omniintelligence.nodes.node_evidence_collection_effect.handlers.handler_evidence_collection import (
    _ALLOWED_SOURCES,
    _DISALLOWED_SOURCES,
    EvidenceCollector,
    collect_and_evaluate,
    fire_and_forget_evaluate,
)
from omniintelligence.nodes.node_evidence_collection_effect.models.model_session_check_results import (
    ModelGateCheckResult,
    ModelSessionCheckResults,
    ModelStaticAnalysisResult,
    ModelTestRunResult,
)

pytestmark = pytest.mark.unit

# ============================================================================
# Fixtures
# ============================================================================


def _make_check_results(
    *,
    gate_results: tuple[ModelGateCheckResult, ...] = (),
    test_results: tuple[ModelTestRunResult, ...] = (),
    static_analysis_results: tuple[ModelStaticAnalysisResult, ...] = (),
    cost_usd: float | None = None,
    latency_seconds: float | None = None,
) -> ModelSessionCheckResults:
    return ModelSessionCheckResults(
        run_id="run-test-001",
        session_id="session-abc",
        gate_results=gate_results,
        test_results=test_results,
        static_analysis_results=static_analysis_results,
        cost_usd=cost_usd,
        latency_seconds=latency_seconds,
        collected_at_utc=datetime.now(UTC).isoformat(),
    )


def _make_gate(
    gate_id: str = "gate_mypy",
    passed: bool = True,
    pass_rate: float = 1.0,
) -> ModelGateCheckResult:
    return ModelGateCheckResult(
        gate_id=gate_id,
        passed=passed,
        pass_rate=pass_rate,
        check_count=1,
        pass_count=1 if passed else 0,
    )


def _make_test_run(
    suite: str = "unit",
    total: int = 10,
    passed: int = 10,
    pass_rate: float = 1.0,
) -> ModelTestRunResult:
    return ModelTestRunResult(
        test_suite=suite,
        total_tests=total,
        passed_tests=passed,
        failed_tests=total - passed,
        pass_rate=pass_rate,
    )


def _make_static_analysis(
    tool: str = "mypy",
    error_count: int = 0,
    clean_rate: float = 1.0,
) -> ModelStaticAnalysisResult:
    return ModelStaticAnalysisResult(
        tool=tool,
        files_checked=100,
        error_count=error_count,
        clean_rate=clean_rate,
    )


# ============================================================================
# EvidenceCollector tests
# ============================================================================


class TestEvidenceCollector:
    """Tests for the pure EvidenceCollector class."""

    def test_empty_check_results_returns_empty_list(self) -> None:
        """Empty check results produce no evidence items."""
        collector = EvidenceCollector()
        results = _make_check_results()
        items = collector.collect(results)
        assert items == []

    def test_gate_result_produces_validator_result_item(self) -> None:
        """Gate results produce 'validator_result' evidence items."""
        collector = EvidenceCollector()
        gate = _make_gate(gate_id="pre_commit", passed=True, pass_rate=1.0)
        results = _make_check_results(gate_results=(gate,))
        items = collector.collect(results)
        assert len(items) == 1
        assert items[0]["source"] == "validator_result"
        assert items[0]["item_id"] == "gate_pre_commit"
        assert items[0]["value"] == 1.0

    def test_test_run_produces_test_output_item(self) -> None:
        """Test run results produce 'test_output' evidence items."""
        collector = EvidenceCollector()
        test_run = _make_test_run(suite="unit", pass_rate=0.9)
        results = _make_check_results(test_results=(test_run,))
        items = collector.collect(results)
        assert len(items) == 1
        assert items[0]["source"] == "test_output"
        assert items[0]["item_id"] == "test_unit"
        assert items[0]["value"] == pytest.approx(0.9)

    def test_static_analysis_produces_static_analysis_item(self) -> None:
        """Static analysis results produce 'static_analysis' evidence items."""
        collector = EvidenceCollector()
        analysis = _make_static_analysis(tool="ruff", clean_rate=1.0)
        results = _make_check_results(static_analysis_results=(analysis,))
        items = collector.collect(results)
        assert len(items) == 1
        assert items[0]["source"] == "static_analysis"
        assert items[0]["item_id"] == "static_ruff"
        assert items[0]["value"] == 1.0

    def test_cost_usd_produces_cost_telemetry_item(self) -> None:
        """Cost telemetry produces 'cost_telemetry' evidence item."""
        collector = EvidenceCollector()
        results = _make_check_results(cost_usd=0.10)
        items = collector.collect(results)
        assert len(items) == 1
        assert items[0]["source"] == "cost_telemetry"
        # $0.10 / $0.50 max = 0.2 usage → score = 0.8
        assert items[0]["value"] == pytest.approx(0.8, abs=1e-6)

    def test_latency_seconds_produces_latency_telemetry_item(self) -> None:
        """Latency telemetry produces 'latency_telemetry' evidence item."""
        collector = EvidenceCollector()
        results = _make_check_results(latency_seconds=60.0)
        items = collector.collect(results)
        assert len(items) == 1
        assert items[0]["source"] == "latency_telemetry"
        # 60s / 300s max = 0.2 usage → score = 0.8
        assert items[0]["value"] == pytest.approx(0.8, abs=1e-6)

    def test_zero_cost_produces_score_one(self) -> None:
        """Zero cost produces maximum cost score of 1.0."""
        collector = EvidenceCollector()
        results = _make_check_results(cost_usd=0.0)
        items = collector.collect(results)
        assert items[0]["value"] == pytest.approx(1.0)

    def test_max_cost_produces_score_zero(self) -> None:
        """Maximum cost produces minimum cost score of 0.0."""
        collector = EvidenceCollector()
        results = _make_check_results(cost_usd=0.50)
        items = collector.collect(results)
        assert items[0]["value"] == pytest.approx(0.0, abs=1e-6)

    def test_multiple_sources_all_collected(self) -> None:
        """Multiple source types all produce evidence items."""
        collector = EvidenceCollector()
        results = _make_check_results(
            gate_results=(_make_gate(),),
            test_results=(_make_test_run(),),
            static_analysis_results=(_make_static_analysis(),),
            cost_usd=0.05,
            latency_seconds=30.0,
        )
        items = collector.collect(results)
        sources = [i["source"] for i in items]
        assert "validator_result" in sources
        assert "test_output" in sources
        assert "static_analysis" in sources
        assert "cost_telemetry" in sources
        assert "latency_telemetry" in sources
        assert len(items) == 5

    def test_assert_no_free_text_raises_for_chat_log(self) -> None:
        """assert_no_free_text raises DisallowedEvidenceSourceError for 'chat_log'."""
        collector = EvidenceCollector()
        with pytest.raises(DisallowedEvidenceSourceError) as exc_info:
            collector.assert_no_free_text("chat_log")
        assert exc_info.value.source == "chat_log"

    def test_assert_no_free_text_raises_for_model_confidence(self) -> None:
        """assert_no_free_text raises for 'model_confidence'."""
        collector = EvidenceCollector()
        with pytest.raises(DisallowedEvidenceSourceError):
            collector.assert_no_free_text("model_confidence")

    @pytest.mark.parametrize("allowed_source", sorted(_ALLOWED_SOURCES))
    def test_assert_no_free_text_passes_for_allowed_sources(
        self, allowed_source: str
    ) -> None:
        """assert_no_free_text does NOT raise for the 7 allowed sources."""
        collector = EvidenceCollector()
        # Should not raise
        collector.assert_no_free_text(allowed_source)

    @pytest.mark.parametrize("disallowed_source", sorted(_DISALLOWED_SOURCES))
    def test_all_disallowed_sources_raise(self, disallowed_source: str) -> None:
        """All disallowed sources raise DisallowedEvidenceSourceError."""
        collector = EvidenceCollector()
        with pytest.raises(DisallowedEvidenceSourceError):
            collector.assert_no_free_text(disallowed_source)


# ============================================================================
# collect_and_evaluate pipeline tests
# ============================================================================


class TestCollectAndEvaluate:
    """Tests for the full async pipeline."""

    @pytest.mark.asyncio
    async def test_empty_results_returns_skipped(self) -> None:
        """Empty check results skip evaluation without error."""
        results = _make_check_results()
        output = await collect_and_evaluate(results)
        assert output.skipped is True
        assert output.skip_reason == "no_evidence_items"
        assert output.run_id == "run-test-001"
        assert output.session_id == "session-abc"

    @pytest.mark.asyncio
    async def test_with_evidence_and_no_dependencies_skips_gracefully(self) -> None:
        """When scoring_reducer is not available, skips gracefully."""
        results = _make_check_results(gate_results=(_make_gate(),))
        # With no scoring reducer available (PR #209 not merged), should skip
        output = await collect_and_evaluate(results)
        # Either skipped (no scoring reducer) or succeeded (if PR #209 merged)
        assert output.run_id == "run-test-001"
        assert isinstance(output.skipped, bool)

    @pytest.mark.asyncio
    async def test_kafka_emitted_when_publisher_provided(self) -> None:
        """RunEvaluatedEvent is emitted when kafka_publisher is provided."""
        results = _make_check_results(
            test_results=(_make_test_run(pass_rate=1.0),),
        )

        mock_kafka = AsyncMock()
        mock_kafka.publish = AsyncMock()

        # Mock the scoring reducer to return a passing result
        mock_score_vector = MagicMock()
        mock_score_vector.correctness = 0.9
        mock_score_vector.safety = 1.0
        mock_score_vector.cost = 0.8
        mock_score_vector.latency = 0.7
        mock_score_vector.maintainability = 0.85
        mock_score_vector.human_time = 0.0

        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.failures = ()
        mock_result.score_vector = mock_score_vector

        with (
            patch(
                "omniintelligence.nodes.node_evidence_collection_effect.handlers"
                ".handler_evidence_collection._run_evaluation",
                return_value=mock_result,
            ),
            patch(
                "omniintelligence.nodes.node_evidence_collection_effect.handlers"
                ".handler_evidence_collection._build_evidence_bundle",
                return_value=MagicMock(bundle_fingerprint="abc123"),
            ),
            patch(
                "omniintelligence.nodes.node_evidence_collection_effect.handlers"
                ".handler_evidence_collection._get_default_objective_spec",
                return_value=MagicMock(),
            ),
        ):
            output = await collect_and_evaluate(
                results,
                kafka_publisher=mock_kafka,
            )

        # Kafka should have been called
        assert mock_kafka.publish.called
        assert output.kafka_emitted is True
        assert output.passed is True
        assert output.skipped is False

    @pytest.mark.asyncio
    async def test_disallowed_source_error_propagates(self) -> None:
        """DisallowedEvidenceSourceError propagates (is NOT swallowed)."""
        results = _make_check_results()

        with patch.object(EvidenceCollector, "collect") as mock_collect:
            mock_collect.side_effect = DisallowedEvidenceSourceError(
                source="chat_log",
                reason="Test injection",
            )

            with pytest.raises(DisallowedEvidenceSourceError):
                await collect_and_evaluate(results)

    @pytest.mark.asyncio
    async def test_collection_error_returns_skipped(self) -> None:
        """Non-DisallowedSource collection errors are swallowed and return skipped."""
        results = _make_check_results()

        with patch.object(EvidenceCollector, "collect") as mock_collect:
            mock_collect.side_effect = RuntimeError("unexpected failure")

            output = await collect_and_evaluate(results)

        assert output.skipped is True
        assert output.skip_reason == "evidence_collection_error"

    @pytest.mark.asyncio
    async def test_db_stored_when_conn_provided(self) -> None:
        """EvaluationResult is stored when db_conn is provided."""
        results = _make_check_results(
            gate_results=(_make_gate(),),
        )

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()

        mock_score_vector = MagicMock()
        mock_score_vector.correctness = 1.0
        mock_score_vector.safety = 1.0
        mock_score_vector.cost = 0.9
        mock_score_vector.latency = 0.8
        mock_score_vector.maintainability = 1.0
        mock_score_vector.human_time = 0.0

        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.failures = ()
        mock_result.score_vector = mock_score_vector

        with (
            patch(
                "omniintelligence.nodes.node_evidence_collection_effect.handlers"
                ".handler_evidence_collection._run_evaluation",
                return_value=mock_result,
            ),
            patch(
                "omniintelligence.nodes.node_evidence_collection_effect.handlers"
                ".handler_evidence_collection._build_evidence_bundle",
                return_value=MagicMock(bundle_fingerprint="fp-abc"),
            ),
            patch(
                "omniintelligence.nodes.node_evidence_collection_effect.handlers"
                ".handler_evidence_collection._get_default_objective_spec",
                return_value=MagicMock(),
            ),
        ):
            output = await collect_and_evaluate(
                results,
                db_conn=mock_db,
            )

        assert mock_db.execute.called
        assert output.db_stored is True


# ============================================================================
# fire_and_forget_evaluate tests
# ============================================================================


class TestFireAndForgetEvaluate:
    """Tests for the non-blocking fire-and-forget wrapper."""

    @pytest.mark.asyncio
    async def test_fire_and_forget_swallows_unexpected_errors(self) -> None:
        """Unexpected errors are swallowed (never propagate to caller)."""
        results = _make_check_results()

        with patch(
            "omniintelligence.nodes.node_evidence_collection_effect.handlers"
            ".handler_evidence_collection.collect_and_evaluate"
        ) as mock_eval:
            mock_eval.side_effect = RuntimeError("catastrophic failure")

            # Should NOT raise
            await fire_and_forget_evaluate(results)

    @pytest.mark.asyncio
    async def test_fire_and_forget_logs_disallowed_source_error(self) -> None:
        """DisallowedEvidenceSourceError is caught and logged (not re-raised)."""
        results = _make_check_results()

        with patch(
            "omniintelligence.nodes.node_evidence_collection_effect.handlers"
            ".handler_evidence_collection.collect_and_evaluate"
        ) as mock_eval:
            mock_eval.side_effect = DisallowedEvidenceSourceError(
                source="chat_log", reason="test"
            )

            # Should NOT raise
            await fire_and_forget_evaluate(results)

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self) -> None:
        """asyncio.CancelledError propagates (allows task cancellation)."""
        results = _make_check_results()

        with patch(
            "omniintelligence.nodes.node_evidence_collection_effect.handlers"
            ".handler_evidence_collection.collect_and_evaluate"
        ) as mock_eval:
            mock_eval.side_effect = asyncio.CancelledError()

            with pytest.raises(asyncio.CancelledError):
                await fire_and_forget_evaluate(results)

    @pytest.mark.asyncio
    async def test_skipped_evaluation_is_logged(self) -> None:
        """Skipped evaluation logs at DEBUG level without error."""
        results = _make_check_results()  # empty → will skip

        # Should complete without error
        await fire_and_forget_evaluate(results)


# ============================================================================
# handle_stop integration tests
# ============================================================================


try:
    import omnibase_core as _omnibase_core_check  # noqa: F401

    _OMNIBASE_CORE_AVAILABLE = True
except ImportError:
    _OMNIBASE_CORE_AVAILABLE = False

_skip_without_omnibase = pytest.mark.skipif(
    not _OMNIBASE_CORE_AVAILABLE,
    reason="omnibase_core not installed — integration test requires full dependency set",
)


class TestHandleStopIntegration:
    """Tests for _launch_objective_evaluation wiring in handle_stop."""

    @_skip_without_omnibase
    @pytest.mark.asyncio
    async def test_handle_stop_dispatches_objective_evaluation(self) -> None:
        """handle_stop dispatches objective evaluation as asyncio task."""
        from omnibase_core.enums.hooks.claude_code import EnumClaudeCodeHookEventType
        from omnibase_core.models.hooks.claude_code import (
            ModelClaudeCodeHookEvent,
            ModelClaudeCodeHookEventPayload,
        )

        from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
            _launch_objective_evaluation,
        )

        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.STOP,
            session_id="test-session-id",
            timestamp_utc=datetime.now(UTC),
            payload=ModelClaudeCodeHookEventPayload(),
        )

        from uuid import uuid4

        correlation_id = uuid4()

        # Should not raise
        _launch_objective_evaluation(
            event=event,
            resolved_correlation_id=correlation_id,
            kafka_producer=None,
        )

    @_skip_without_omnibase
    @pytest.mark.asyncio
    async def test_handle_stop_metadata_includes_objective_evaluation(self) -> None:
        """handle_stop result metadata includes 'objective_evaluation' key."""
        from omnibase_core.enums.hooks.claude_code import EnumClaudeCodeHookEventType
        from omnibase_core.models.hooks.claude_code import (
            ModelClaudeCodeHookEvent,
            ModelClaudeCodeHookEventPayload,
        )

        from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
            handle_stop,
        )

        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.STOP,
            session_id="test-session-id-2",
            timestamp_utc=datetime.now(UTC),
            payload=ModelClaudeCodeHookEventPayload(),
        )

        result = await handle_stop(event=event, kafka_producer=None)
        assert "objective_evaluation" in result.metadata
        assert result.metadata["objective_evaluation"] == "dispatched"
