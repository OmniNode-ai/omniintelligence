# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for the CLI entry point for calibration.

Covers: argument parsing, stream policy (JSON stdout / summary stderr),
exit codes, --persist gate, --no-embedding flag, --output file writing.

Reference: OMN-6172
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.review_pairing.cli_calibration import (
    build_parser,
    format_metrics_table,
    main,
)
from omniintelligence.review_pairing.models_calibration import (
    ModelCalibrationMetrics,
    ModelCalibrationOrchestrationResult,
    ModelCalibrationRunResult,
)


def _make_metrics(
    model: str = "deepseek-r1",
    precision: float = 0.8,
    recall: float = 0.7,
    f1: float = 0.74,
    noise: float = 0.2,
) -> ModelCalibrationMetrics:
    return ModelCalibrationMetrics(
        model=model,
        true_positives=4,
        false_positives=1,
        false_negatives=2,
        precision=precision,
        recall=recall,
        f1_score=f1,
        noise_ratio=noise,
    )


def _make_run_result(
    model: str = "deepseek-r1",
    *,
    error: str | None = None,
    metrics: ModelCalibrationMetrics | None = None,
) -> ModelCalibrationRunResult:
    if metrics is None and error is None:
        metrics = _make_metrics(model=model)
    return ModelCalibrationRunResult(
        run_id="test-run-1",
        ground_truth_model="codex",
        challenger_model=model,
        alignments=[],
        metrics=metrics,
        prompt_version="v1.0",
        embedding_model_version="jaccard-v1",
        error=error,
        created_at=datetime(2026, 3, 23, tzinfo=timezone.utc),
    )


def _make_orchestration_result(
    *,
    success: bool = True,
    challenger_results: list[ModelCalibrationRunResult] | None = None,
) -> ModelCalibrationOrchestrationResult:
    if challenger_results is None:
        challenger_results = [_make_run_result()]
    return ModelCalibrationOrchestrationResult(
        success=success,
        error=None if success else "all challengers failed",
        ground_truth_findings=[],
        challenger_results=challenger_results,
    )


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildParser:
    def test_file_required(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_file_accepted(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--file", "plan.md", "--challenger", "deepseek-r1"])
        assert args.file == "plan.md"

    def test_ground_truth_default(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--file", "plan.md", "--challenger", "deepseek-r1"])
        assert args.ground_truth == "codex"

    def test_ground_truth_override(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--file",
                "plan.md",
                "--ground-truth",
                "deepseek-r1",
                "--challenger",
                "qwen3-coder",
            ]
        )
        assert args.ground_truth == "deepseek-r1"

    def test_challenger_repeatable(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--file",
                "plan.md",
                "--challenger",
                "deepseek-r1",
                "--challenger",
                "qwen3-coder",
            ]
        )
        assert args.challenger == ["deepseek-r1", "qwen3-coder"]

    def test_challenger_required(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--file", "plan.md"])

    def test_output_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["--file", "plan.md", "--challenger", "deepseek-r1", "--output", "out.json"]
        )
        assert args.output == "out.json"

    def test_persist_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["--file", "plan.md", "--challenger", "deepseek-r1", "--persist"]
        )
        assert args.persist is True

    def test_no_persist_default(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--file", "plan.md", "--challenger", "deepseek-r1"])
        assert args.persist is False

    def test_no_embedding_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["--file", "plan.md", "--challenger", "deepseek-r1", "--no-embedding"]
        )
        assert args.no_embedding is True

    def test_r1r6_findings_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--file",
                "plan.md",
                "--challenger",
                "deepseek-r1",
                "--r1r6-findings",
                "findings.json",
            ]
        )
        assert args.r1r6_findings == "findings.json"

    def test_dry_run_fewshot_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["--file", "plan.md", "--challenger", "deepseek-r1", "--dry-run-fewshot"]
        )
        assert args.dry_run_fewshot is True


# ---------------------------------------------------------------------------
# format_metrics_table
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatMetricsTable:
    def test_single_model(self) -> None:
        metrics = [_make_metrics(model="deepseek-r1")]
        table = format_metrics_table(metrics)
        assert "deepseek-r1" in table
        assert "Precision" in table
        assert "Recall" in table
        assert "F1" in table
        assert "Noise" in table

    def test_multiple_models(self) -> None:
        metrics = [
            _make_metrics(model="deepseek-r1"),
            _make_metrics(
                model="qwen3-coder", precision=0.6, recall=0.9, f1=0.72, noise=0.4
            ),
        ]
        table = format_metrics_table(metrics)
        assert "deepseek-r1" in table
        assert "qwen3-coder" in table

    def test_empty_list(self) -> None:
        table = format_metrics_table([])
        assert "No metrics" in table


# ---------------------------------------------------------------------------
# main (CLI entry point)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMain:
    def test_exit_0_on_success(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")

        with patch(
            "omniintelligence.review_pairing.cli_calibration._run_calibration",
            new_callable=AsyncMock,
            return_value=_make_orchestration_result(),
        ):
            code = main(["--file", str(plan_file), "--challenger", "deepseek-r1"])
        assert code == 0

    def test_exit_1_on_all_failed(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")

        result = _make_orchestration_result(
            success=False,
            challenger_results=[
                _make_run_result("deepseek-r1", error="transport error", metrics=None)
            ],
        )
        with patch(
            "omniintelligence.review_pairing.cli_calibration._run_calibration",
            new_callable=AsyncMock,
            return_value=result,
        ):
            code = main(["--file", str(plan_file), "--challenger", "deepseek-r1"])
        assert code == 1

    def test_file_not_found(self) -> None:
        code = main(["--file", "/nonexistent/plan.md", "--challenger", "deepseek-r1"])
        assert code == 1

    def test_output_to_file(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")
        output_file = tmp_path / "results.json"

        with patch(
            "omniintelligence.review_pairing.cli_calibration._run_calibration",
            new_callable=AsyncMock,
            return_value=_make_orchestration_result(),
        ):
            code = main(
                [
                    "--file",
                    str(plan_file),
                    "--challenger",
                    "deepseek-r1",
                    "--output",
                    str(output_file),
                ]
            )

        assert code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "success" in data
        assert "challenger_results" in data

    def test_json_on_stdout(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")

        with patch(
            "omniintelligence.review_pairing.cli_calibration._run_calibration",
            new_callable=AsyncMock,
            return_value=_make_orchestration_result(),
        ):
            main(["--file", str(plan_file), "--challenger", "deepseek-r1"])

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "success" in data

    def test_summary_on_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")

        with patch(
            "omniintelligence.review_pairing.cli_calibration._run_calibration",
            new_callable=AsyncMock,
            return_value=_make_orchestration_result(),
        ):
            main(["--file", str(plan_file), "--challenger", "deepseek-r1"])

        captured = capsys.readouterr()
        assert "Precision" in captured.err
        assert "deepseek-r1" in captured.err

    def test_persist_requires_db_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")
        monkeypatch.delenv("OMNIBASE_INFRA_DB_URL", raising=False)

        code = main(
            ["--file", str(plan_file), "--challenger", "deepseek-r1", "--persist"]
        )
        assert code == 1

    def test_no_embedding_disables_embedding(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")

        with patch(
            "omniintelligence.review_pairing.cli_calibration._run_calibration",
            new_callable=AsyncMock,
            return_value=_make_orchestration_result(),
        ) as mock_run:
            main(
                [
                    "--file",
                    str(plan_file),
                    "--challenger",
                    "deepseek-r1",
                    "--no-embedding",
                ]
            )

        # Verify no_embedding was passed through
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("no_embedding") is True
