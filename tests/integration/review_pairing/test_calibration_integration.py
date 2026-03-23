# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Integration tests for the calibration pipeline.

Exercises the end-to-end flow: config -> orchestrator -> alignment -> scoring
-> few-shot extraction, using mock adapters (no real LLM calls).

Reference: OMN-6178
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from omniintelligence.review_pairing.alignment_engine import (
    FindingAlignmentEngine,
)
from omniintelligence.review_pairing.calibration_orchestrator import (
    CalibrationOrchestrator,
)
from omniintelligence.review_pairing.calibration_scorer import CalibrationScorer
from omniintelligence.review_pairing.fewshot_extractor import FewShotExtractor
from omniintelligence.review_pairing.models import (
    FindingSeverity,
    ReviewFindingObserved,
)
from omniintelligence.review_pairing.models_calibration import (
    CalibrationConfig,
    CalibrationRunResult,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
)
from omniintelligence.review_pairing.serializer_r1r6 import (
    serialize_external_finding,
)

# ---------------------------------------------------------------------------
# Fixtures: known ground-truth and challenger findings
# ---------------------------------------------------------------------------

_NOW = datetime.now(tz=UTC)


def _make_finding(
    category: str,
    message: str,
    file_path: str = "src/main.py",
    severity: FindingSeverity = FindingSeverity.ERROR,
    model: str = "codex",
) -> ReviewFindingObserved:
    """Build a ReviewFindingObserved with the given category/message."""
    return ReviewFindingObserved(
        finding_id=uuid4(),
        repo="OmniNode-ai/test-repo",
        pr_id=1,
        rule_id=f"ai-reviewer:{model}:{category}",
        severity=severity,
        file_path=file_path,
        line_start=1,
        line_end=None,
        tool_name="ai-reviewer",
        tool_version="1.0.0",
        normalized_message=message,
        raw_message=message,
        commit_sha_observed="abc1234",
        observed_at=_NOW,
    )


# 5 ground-truth findings
GROUND_TRUTH_FINDINGS: list[ReviewFindingObserved] = [
    _make_finding("security", "SQL injection vulnerability in query builder"),
    _make_finding("architecture", "Circular dependency between module A and B"),
    _make_finding("performance", "N+1 query pattern in user listing endpoint"),
    _make_finding("error-handling", "Bare except clause swallows critical errors"),
    _make_finding("testing", "No test coverage for authentication middleware"),
]

# Challenger findings: 3 matching + 2 noise + 1 miss (the "testing" finding is missed)
CHALLENGER_FINDINGS: list[ReviewFindingObserved] = [
    # Matches GT[0] - security/SQL injection (same words, high Jaccard)
    _make_finding(
        "security",
        "SQL injection vulnerability in query builder module",
        model="challenger-a",
    ),
    # Matches GT[1] - architecture/circular dependency
    _make_finding(
        "architecture",
        "Circular dependency between module A and B detected",
        model="challenger-a",
    ),
    # Matches GT[2] - performance/N+1
    _make_finding(
        "performance",
        "N+1 query pattern in user listing endpoint causing slowdowns",
        model="challenger-a",
    ),
    # Noise 1 - not in ground truth
    _make_finding(
        "style",
        "Variable names should use snake_case consistently",
        model="challenger-a",
    ),
    # Noise 2 - not in ground truth
    _make_finding(
        "documentation",
        "Missing docstring on public function process_data",
        model="challenger-a",
    ),
]


@pytest.fixture()
def calibration_config() -> CalibrationConfig:
    return CalibrationConfig(
        ground_truth_model="codex",
        challenger_models=["challenger-a"],
        similarity_threshold=0.3,
        min_runs_for_fewshot=1,
        fewshot_tp_count=3,
        fewshot_fp_count=3,
        fewshot_fn_count=3,
    )


@pytest.fixture()
def multi_run_config() -> CalibrationConfig:
    """Config with min_runs_for_fewshot=5 for multi-run extraction tests."""
    return CalibrationConfig(
        ground_truth_model="codex",
        challenger_models=["challenger-a"],
        similarity_threshold=0.3,
        min_runs_for_fewshot=5,
        fewshot_tp_count=3,
        fewshot_fp_count=3,
        fewshot_fn_count=3,
    )


# ---------------------------------------------------------------------------
# Mock adapters
# ---------------------------------------------------------------------------


async def _mock_codex_adapter(
    content: str, **kwargs: object
) -> ModelExternalReviewResult:
    """Mock codex adapter returning ground-truth findings."""
    return ModelExternalReviewResult(
        model="codex",
        prompt_version="test-v1",
        success=True,
        findings=GROUND_TRUTH_FINDINGS,
        result_count=len(GROUND_TRUTH_FINDINGS),
    )


async def _mock_challenger_adapter(
    content: str, **kwargs: object
) -> ModelExternalReviewResult:
    """Mock challenger adapter returning mix of matching + noise findings."""
    return ModelExternalReviewResult(
        model="challenger-a",
        prompt_version="test-v1",
        success=True,
        findings=CHALLENGER_FINDINGS,
        result_count=len(CHALLENGER_FINDINGS),
    )


async def _mock_failing_adapter(
    content: str, **kwargs: object
) -> ModelExternalReviewResult:
    """Mock adapter that simulates a model failure."""
    return ModelExternalReviewResult(
        model="failing-model",
        prompt_version="test-v1",
        success=False,
        error="Mock LLM timeout",
        findings=[],
        result_count=0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAlignmentIntegration:
    """Tests for the alignment engine with realistic findings."""

    async def test_alignment_pairs_matching_findings(
        self, calibration_config: CalibrationConfig
    ) -> None:
        engine = FindingAlignmentEngine(
            similarity_threshold=calibration_config.similarity_threshold,
        )

        gt_tuples = [serialize_external_finding(f) for f in GROUND_TRUTH_FINDINGS]
        ch_tuples = [serialize_external_finding(f) for f in CHALLENGER_FINDINGS]

        alignments = await engine.align(gt_tuples, ch_tuples)

        tp = [a for a in alignments if a.alignment_type == "true_positive"]
        fp = [a for a in alignments if a.alignment_type == "false_positive"]
        fn = [a for a in alignments if a.alignment_type == "false_negative"]

        assert len(tp) == 3, f"Expected 3 TPs, got {len(tp)}"
        assert len(fp) == 2, f"Expected 2 FPs, got {len(fp)}"
        assert len(fn) == 2, f"Expected 2 FNs, got {len(fn)}"

    async def test_alignment_scores_above_threshold(
        self, calibration_config: CalibrationConfig
    ) -> None:
        engine = FindingAlignmentEngine(
            similarity_threshold=calibration_config.similarity_threshold,
        )

        gt_tuples = [serialize_external_finding(f) for f in GROUND_TRUTH_FINDINGS]
        ch_tuples = [serialize_external_finding(f) for f in CHALLENGER_FINDINGS]

        alignments = await engine.align(gt_tuples, ch_tuples)

        for a in alignments:
            if a.alignment_type == "true_positive":
                assert a.similarity_score >= calibration_config.similarity_threshold
                assert a.aligned is True
            else:
                assert a.aligned is False

    async def test_alignment_preserves_finding_identity(
        self, calibration_config: CalibrationConfig
    ) -> None:
        engine = FindingAlignmentEngine(
            similarity_threshold=calibration_config.similarity_threshold,
        )

        gt_tuples = [serialize_external_finding(f) for f in GROUND_TRUTH_FINDINGS]
        ch_tuples = [serialize_external_finding(f) for f in CHALLENGER_FINDINGS]

        alignments = await engine.align(gt_tuples, ch_tuples)

        tp_alignments = [a for a in alignments if a.alignment_type == "true_positive"]
        for a in tp_alignments:
            assert a.ground_truth is not None
            assert a.challenger is not None
            assert a.ground_truth.source_model == "codex"
            assert a.challenger.source_model == "challenger-a"


@pytest.mark.integration
class TestScoringIntegration:
    """Tests for the scorer with alignment engine output."""

    async def test_metrics_match_expected_values(
        self, calibration_config: CalibrationConfig
    ) -> None:
        engine = FindingAlignmentEngine(
            similarity_threshold=calibration_config.similarity_threshold,
        )
        scorer = CalibrationScorer()

        gt_tuples = [serialize_external_finding(f) for f in GROUND_TRUTH_FINDINGS]
        ch_tuples = [serialize_external_finding(f) for f in CHALLENGER_FINDINGS]

        alignments = await engine.align(gt_tuples, ch_tuples)
        metrics = scorer.score(alignments, model="challenger-a")

        assert metrics.true_positives == 3
        assert metrics.false_positives == 2
        assert metrics.false_negatives == 2

        assert metrics.precision == pytest.approx(3 / 5, abs=0.01)
        assert metrics.recall == pytest.approx(3 / 5, abs=0.01)
        assert metrics.noise_ratio == pytest.approx(2 / 5, abs=0.01)

        expected_f1 = 2 * 0.6 * 0.6 / (0.6 + 0.6)
        assert metrics.f1_score == pytest.approx(expected_f1, abs=0.01)


@pytest.mark.integration
class TestOrchestratorIntegration:
    """Tests for the full orchestrator flow with mock adapters."""

    async def test_end_to_end_orchestrator_flow(
        self, calibration_config: CalibrationConfig
    ) -> None:
        orchestrator = CalibrationOrchestrator(
            config=calibration_config,
            codex_adapter=_mock_codex_adapter,
            ai_adapter=_mock_challenger_adapter,
        )

        result = await orchestrator.run(content="mock plan content")

        assert result.success is True
        assert result.error is None
        assert len(result.ground_truth_findings) == 5
        assert len(result.challenger_results) == 1

        run_result = result.challenger_results[0]
        assert run_result.error is None
        assert run_result.metrics is not None
        assert run_result.challenger_model == "challenger-a"
        assert run_result.ground_truth_model == "codex"

        metrics = run_result.metrics
        assert metrics.true_positives == 3
        assert metrics.false_positives == 2
        assert metrics.false_negatives == 2
        assert metrics.precision == pytest.approx(0.6, abs=0.01)
        assert metrics.recall == pytest.approx(0.6, abs=0.01)
        assert metrics.noise_ratio == pytest.approx(0.4, abs=0.01)

    async def test_orchestrator_handles_ground_truth_failure(
        self, calibration_config: CalibrationConfig
    ) -> None:
        config = CalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["challenger-a"],
            similarity_threshold=0.3,
        )

        orchestrator = CalibrationOrchestrator(
            config=config,
            codex_adapter=_mock_failing_adapter,
            ai_adapter=_mock_challenger_adapter,
        )

        result = await orchestrator.run(content="mock plan content")

        assert result.success is False
        assert result.error is not None
        assert "codex" in result.error
        assert len(result.challenger_results) == 0

    async def test_orchestrator_handles_challenger_failure(self) -> None:
        config = CalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["failing-model"],
            similarity_threshold=0.3,
        )

        orchestrator = CalibrationOrchestrator(
            config=config,
            codex_adapter=_mock_codex_adapter,
            ai_adapter=_mock_failing_adapter,
        )

        result = await orchestrator.run(content="mock plan content")

        assert result.success is True
        assert len(result.challenger_results) == 1

        run_result = result.challenger_results[0]
        assert run_result.error is not None
        assert run_result.metrics is None


@pytest.mark.integration
class TestFewShotExtractionIntegration:
    """Tests for few-shot extraction from calibration results."""

    async def test_fewshot_extraction_after_sufficient_runs(
        self, calibration_config: CalibrationConfig
    ) -> None:
        orchestrator = CalibrationOrchestrator(
            config=calibration_config,
            codex_adapter=_mock_codex_adapter,
            ai_adapter=_mock_challenger_adapter,
        )

        result = await orchestrator.run(content="mock plan content")
        assert result.success

        run_result = result.challenger_results[0]

        extractor = FewShotExtractor()
        examples = extractor.extract(
            runs=[run_result],
            config=calibration_config,
        )

        assert len(examples) > 0

        tp_examples = [e for e in examples if e.example_type == "true_positive"]
        fp_examples = [e for e in examples if e.example_type == "false_positive"]

        assert len(tp_examples) <= calibration_config.fewshot_tp_count
        assert len(fp_examples) <= calibration_config.fewshot_fp_count

        assert len(tp_examples) == 3
        assert len(fp_examples) == 2

        for ex in tp_examples:
            assert ex.ground_truth_present is True
            assert "similarity_score" in ex.evidence

        for ex in fp_examples:
            assert ex.ground_truth_present is False
            assert "recurrence_frequency" in ex.evidence

    async def test_fewshot_below_min_runs_returns_empty(
        self, multi_run_config: CalibrationConfig
    ) -> None:
        orchestrator = CalibrationOrchestrator(
            config=multi_run_config,
            codex_adapter=_mock_codex_adapter,
            ai_adapter=_mock_challenger_adapter,
        )

        result = await orchestrator.run(content="mock plan content")
        assert result.success

        extractor = FewShotExtractor()
        examples = extractor.extract(
            runs=[result.challenger_results[0]],
            config=multi_run_config,
        )

        assert examples == []

    async def test_fewshot_extraction_after_multiple_runs(
        self, multi_run_config: CalibrationConfig
    ) -> None:
        orchestrator = CalibrationOrchestrator(
            config=multi_run_config,
            codex_adapter=_mock_codex_adapter,
            ai_adapter=_mock_challenger_adapter,
        )

        runs: list[CalibrationRunResult] = []
        for _ in range(5):
            result = await orchestrator.run(content="mock plan content")
            assert result.success
            runs.append(result.challenger_results[0])

        extractor = FewShotExtractor()
        examples = extractor.extract(runs=runs, config=multi_run_config)

        assert len(examples) > 0
        tp_examples = [e for e in examples if e.example_type == "true_positive"]
        fp_examples = [e for e in examples if e.example_type == "false_positive"]
        assert len(tp_examples) > 0
        assert len(fp_examples) > 0


@pytest.mark.integration
class TestEndToEndCalibrationPipeline:
    """Full pipeline: config -> orchestrator -> alignment -> scoring -> few-shot."""

    async def test_full_pipeline(self, calibration_config: CalibrationConfig) -> None:
        # Step 1: Configure and run orchestration
        orchestrator = CalibrationOrchestrator(
            config=calibration_config,
            codex_adapter=_mock_codex_adapter,
            ai_adapter=_mock_challenger_adapter,
        )
        orch_result = await orchestrator.run(content="mock plan content")
        assert orch_result.success

        # Step 2: Verify alignment correctness
        run_result = orch_result.challenger_results[0]
        assert run_result.metrics is not None

        tp_alignments = [
            a for a in run_result.alignments if a.alignment_type == "true_positive"
        ]
        fp_alignments = [
            a for a in run_result.alignments if a.alignment_type == "false_positive"
        ]
        fn_alignments = [
            a for a in run_result.alignments if a.alignment_type == "false_negative"
        ]

        assert len(tp_alignments) == 3
        assert len(fp_alignments) == 2
        assert len(fn_alignments) == 2

        # Step 3: Verify metrics
        metrics = run_result.metrics
        assert metrics.precision == pytest.approx(0.6, abs=0.01)
        assert metrics.recall == pytest.approx(0.6, abs=0.01)
        assert metrics.noise_ratio == pytest.approx(0.4, abs=0.01)

        # Step 4: Verify few-shot extraction
        extractor = FewShotExtractor()
        examples = extractor.extract(
            runs=[run_result],
            config=calibration_config,
        )

        tp_ex = [e for e in examples if e.example_type == "true_positive"]
        fp_ex = [e for e in examples if e.example_type == "false_positive"]

        assert len(tp_ex) == 3
        assert len(fp_ex) == 2

        # Verify TP examples reference real categories from our findings
        tp_categories = {e.category for e in tp_ex}
        expected_tp_categories = {"security", "architecture", "performance"}
        assert tp_categories == expected_tp_categories

        # Verify FP examples reference the noise categories
        fp_categories = {e.category for e in fp_ex}
        expected_fp_categories = {"style", "documentation"}
        assert fp_categories == expected_fp_categories


@pytest.mark.integration
@pytest.mark.slow
class TestEmbeddingAlignmentPath:
    """Tests the embedding-based alignment path (requires LLM_EMBEDDING_URL)."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_embedding(self) -> None:
        url = os.environ.get("LLM_EMBEDDING_URL", "")
        if not url:
            pytest.skip("LLM_EMBEDDING_URL not set; skipping embedding tests")

    async def test_embedding_alignment_produces_valid_results(
        self, calibration_config: CalibrationConfig
    ) -> None:
        """Smoke test: embedding path produces structurally valid alignments."""
        # This test only runs when LLM_EMBEDDING_URL is reachable.
        # It verifies that the embedding client integrates without errors.
        import httpx

        from omniintelligence.review_pairing.alignment_engine import (
            EmbeddingClientProtocol,
        )

        embedding_url = os.environ["LLM_EMBEDDING_URL"]

        # Check reachability before proceeding
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{embedding_url}/health")
                if resp.status_code != 200:
                    pytest.skip(
                        f"Embedding server not healthy (status {resp.status_code})"
                    )
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("Embedding server not reachable")

        class HttpEmbeddingClient:
            """Minimal embedding client for integration testing."""

            def __init__(self, base_url: str) -> None:
                self._base_url = base_url

            async def embed_batch(self, texts: list[str]) -> list[list[float]]:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{self._base_url}/v1/embeddings",
                        json={"input": texts},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return [item["embedding"] for item in data["data"]]

        embedding_client: EmbeddingClientProtocol = HttpEmbeddingClient(embedding_url)

        engine = FindingAlignmentEngine(
            similarity_threshold=calibration_config.similarity_threshold,
            embedding_client=embedding_client,
        )

        gt_tuples = [serialize_external_finding(f) for f in GROUND_TRUTH_FINDINGS]
        ch_tuples = [serialize_external_finding(f) for f in CHALLENGER_FINDINGS]

        alignments = await engine.align(gt_tuples, ch_tuples)

        assert len(alignments) > 0

        tp = [a for a in alignments if a.alignment_type == "true_positive"]
        fp = [a for a in alignments if a.alignment_type == "false_positive"]
        fn = [a for a in alignments if a.alignment_type == "false_negative"]

        # With embeddings we expect at least 2 TPs (semantic matching may differ)
        assert len(tp) >= 2
        assert len(fp) >= 1
        assert len(fn) >= 1

        # All alignments should have the embedding model version
        for a in alignments:
            assert a.embedding_model_version == "embedding-client"
