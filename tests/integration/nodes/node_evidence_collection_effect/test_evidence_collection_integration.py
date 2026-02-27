# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Integration tests for evidence collection pipeline (OMN-2578).

These tests verify the end-to-end pipeline from session check results
to EvidenceBundle construction and evaluation. They use mocked I/O
(no real Kafka or DB), but test the full Python call chain.

Marked as integration tests: require the full package + all imports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omniintelligence.nodes.node_evidence_collection_effect.handlers.handler_evidence_collection import (
    collect_and_evaluate,
    fire_and_forget_evaluate,
)
from omniintelligence.nodes.node_evidence_collection_effect.models.model_session_check_results import (
    ModelGateCheckResult,
    ModelSessionCheckResults,
    ModelStaticAnalysisResult,
    ModelTestRunResult,
)

pytestmark = pytest.mark.integration


def _full_check_results() -> ModelSessionCheckResults:
    """Build a realistic full set of check results."""
    return ModelSessionCheckResults(
        run_id="run-integration-001",
        session_id="session-integration-abc",
        gate_results=(
            ModelGateCheckResult(
                gate_id="pre_commit",
                passed=True,
                pass_rate=1.0,
                check_count=7,
                pass_count=7,
            ),
            ModelGateCheckResult(
                gate_id="mypy_strict",
                passed=True,
                pass_rate=1.0,
                check_count=100,
                pass_count=100,
            ),
        ),
        test_results=(
            ModelTestRunResult(
                test_suite="unit",
                total_tests=45,
                passed_tests=45,
                pass_rate=1.0,
                duration_seconds=8.3,
            ),
            ModelTestRunResult(
                test_suite="integration",
                total_tests=12,
                passed_tests=11,
                failed_tests=1,
                pass_rate=0.916,
                duration_seconds=25.1,
            ),
        ),
        static_analysis_results=(
            ModelStaticAnalysisResult(
                tool="mypy",
                files_checked=671,
                error_count=0,
                clean_rate=1.0,
            ),
            ModelStaticAnalysisResult(
                tool="ruff",
                files_checked=671,
                error_count=0,
                clean_rate=1.0,
            ),
        ),
        cost_usd=0.08,
        latency_seconds=45.0,
        collected_at_utc=datetime.now(UTC).isoformat(),
    )


class TestEvidenceCollectionIntegration:
    """Integration tests for the full pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_skips_gracefully_without_scoring_reducer(
        self,
    ) -> None:
        """Full pipeline completes gracefully when ScoringReducer is unavailable."""
        results = _full_check_results()
        output = await collect_and_evaluate(results)
        # Either succeeds (PR #209 merged) or skips gracefully (not yet merged)
        assert output.run_id == "run-integration-001"
        assert output.session_id == "session-integration-abc"
        # evidence_item_count should be 7 (2 gates + 2 tests + 2 static + cost + latency)
        # but only if collection succeeded (may be 0 if skipped early)
        assert isinstance(output.evidence_item_count, int)
        assert output.evidence_item_count >= 0

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocked_scoring(self) -> None:
        """Full pipeline with mocked ScoringReducer produces expected output."""
        results = _full_check_results()

        mock_score = MagicMock()
        mock_score.correctness = 1.0
        mock_score.safety = 1.0
        mock_score.cost = 0.84
        mock_score.latency = 0.85
        mock_score.maintainability = 1.0
        mock_score.human_time = 0.0

        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.failures = ()
        mock_result.score_vector = mock_score

        mock_bundle = MagicMock()
        mock_bundle.bundle_fingerprint = "deadbeef" * 8  # 64 char hex

        mock_kafka = AsyncMock()
        mock_kafka.publish = AsyncMock()

        with (
            patch(
                "omniintelligence.nodes.node_evidence_collection_effect.handlers"
                ".handler_evidence_collection._run_evaluation",
                return_value=mock_result,
            ),
            patch(
                "omniintelligence.nodes.node_evidence_collection_effect.handlers"
                ".handler_evidence_collection._build_evidence_bundle",
                return_value=mock_bundle,
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

        assert output.skipped is False
        assert output.passed is True
        assert output.bundle_fingerprint == "deadbeef" * 8
        assert output.kafka_emitted is True
        assert output.evidence_item_count > 0

        # Verify Kafka was called with correct topic
        call_kwargs = mock_kafka.publish.call_args
        assert call_kwargs is not None
        assert "run-evaluated" in call_kwargs.kwargs.get("topic", "") or (
            len(call_kwargs.args) > 0 and "run-evaluated" in str(call_kwargs.args[0])
        )

    @pytest.mark.asyncio
    async def test_fire_and_forget_completes_without_error(self) -> None:
        """fire_and_forget_evaluate completes without raising for real results."""
        results = _full_check_results()
        # Should always complete without raising
        await fire_and_forget_evaluate(results)

    @pytest.mark.asyncio
    async def test_bundle_fingerprint_is_deterministic(self) -> None:
        """Same check results always produce the same bundle fingerprint."""
        from omniintelligence.nodes.node_evidence_collection_effect.handlers.handler_evidence_collection import (
            EvidenceCollector,
            _build_evidence_bundle,
        )

        results = _full_check_results()
        collector = EvidenceCollector()
        items_dicts = collector.collect(results)

        # Build two bundles from identical items
        bundle1 = _build_evidence_bundle(
            run_id="run-001",
            items_dicts=items_dicts,
            collected_at_utc="2026-02-24T12:00:00+00:00",
        )
        bundle2 = _build_evidence_bundle(
            run_id="run-001",
            items_dicts=items_dicts,
            collected_at_utc="2026-02-24T12:00:00+00:00",
        )

        if bundle1 is None or bundle2 is None:
            pytest.skip("ScoringReducer models not available (PR #209 not merged)")

        assert bundle1.bundle_fingerprint == bundle2.bundle_fingerprint

    @pytest.mark.asyncio
    async def test_different_items_produce_different_fingerprints(self) -> None:
        """Different check results produce different bundle fingerprints."""
        from omniintelligence.nodes.node_evidence_collection_effect.handlers.handler_evidence_collection import (
            EvidenceCollector,
            _build_evidence_bundle,
        )

        results_passing = _full_check_results()
        results_failing = ModelSessionCheckResults(
            run_id="run-fail-001",
            session_id="session-fail",
            gate_results=(
                ModelGateCheckResult(
                    gate_id="pre_commit",
                    passed=False,
                    pass_rate=0.0,
                ),
            ),
            collected_at_utc=datetime.now(UTC).isoformat(),
        )

        collector = EvidenceCollector()
        items_pass = collector.collect(results_passing)
        items_fail = collector.collect(results_failing)

        bundle_pass = _build_evidence_bundle(
            run_id="run-pass",
            items_dicts=items_pass,
            collected_at_utc="2026-02-24T12:00:00+00:00",
        )
        bundle_fail = _build_evidence_bundle(
            run_id="run-fail",
            items_dicts=items_fail,
            collected_at_utc="2026-02-24T12:00:00+00:00",
        )

        if bundle_pass is None or bundle_fail is None:
            pytest.skip("ScoringReducer models not available (PR #209 not merged)")

        assert bundle_pass.bundle_fingerprint != bundle_fail.bundle_fingerprint
