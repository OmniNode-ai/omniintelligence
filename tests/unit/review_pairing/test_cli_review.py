# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for the CLI wrapper for multi-model adversarial review.

Covers: argument parsing, model routing, exit codes, partial success,
per-model attribution, output file writing.

Reference: OMN-5793
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.review_pairing.cli_review import (
    build_parser,
    main,
    run_review,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
    ModelMultiReviewResult,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
)


def _success_result(model: str = "deepseek-r1") -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model,
        prompt_version=PROMPT_VERSION,
        success=True,
        findings=[],
        result_count=0,
    )


def _failure_result(
    model: str = "codex", error: str = "codex CLI not found"
) -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model,
        prompt_version=PROMPT_VERSION,
        success=False,
        error=error,
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
        args = parser.parse_args(["--file", "plan.md"])
        assert args.file == "plan.md"

    def test_model_repeatable(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["--file", "plan.md", "--model", "deepseek-r1", "--model", "codex"]
        )
        assert args.model == ["deepseek-r1", "codex"]

    def test_default_model_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--file", "plan.md"])
        assert args.model is None

    def test_output_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--file", "plan.md", "--output", "out.json"])
        assert args.output == "out.json"


# ---------------------------------------------------------------------------
# run_review
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRunReview:
    @pytest.mark.asyncio
    async def test_single_model_success(self) -> None:
        with patch(
            "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
            new_callable=AsyncMock,
            return_value=_success_result("deepseek-r1"),
        ):
            result = await run_review("# Plan", ["deepseek-r1"])

        assert isinstance(result, ModelMultiReviewResult)
        assert result.models_attempted == ["deepseek-r1"]
        assert result.models_succeeded == ["deepseek-r1"]
        assert result.models_failed == []

    @pytest.mark.asyncio
    async def test_codex_routes_to_codex_adapter(self) -> None:
        with patch(
            "omniintelligence.review_pairing.cli_review.codex_async_parse_raw",
            new_callable=AsyncMock,
            return_value=_success_result("codex"),
        ) as mock_codex:
            result = await run_review("# Plan", ["codex"])

        mock_codex.assert_called_once_with("# Plan", review_type="plan")
        assert result.models_succeeded == ["codex"]

    @pytest.mark.asyncio
    async def test_llm_model_routes_to_llm_adapter(self) -> None:
        with patch(
            "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
            new_callable=AsyncMock,
            return_value=_success_result("qwen3-coder"),
        ) as mock_llm:
            result = await run_review("# Plan", ["qwen3-coder"])

        mock_llm.assert_called_once_with(
            "# Plan", model="qwen3-coder", review_type="plan", system_prompt_prefix=None
        )
        assert result.models_succeeded == ["qwen3-coder"]

    @pytest.mark.asyncio
    async def test_multi_model_per_model_envelopes(self) -> None:
        with (
            patch(
                "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
                new_callable=AsyncMock,
                return_value=_success_result("deepseek-r1"),
            ),
            patch(
                "omniintelligence.review_pairing.cli_review.codex_async_parse_raw",
                new_callable=AsyncMock,
                return_value=_success_result("codex"),
            ),
        ):
            result = await run_review("# Plan", ["deepseek-r1", "codex"])

        assert len(result.results) == 2
        assert result.models_attempted == ["deepseek-r1", "codex"]
        assert set(result.models_succeeded) == {"deepseek-r1", "codex"}

    @pytest.mark.asyncio
    async def test_partial_success(self) -> None:
        with (
            patch(
                "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
                new_callable=AsyncMock,
                return_value=_success_result("deepseek-r1"),
            ),
            patch(
                "omniintelligence.review_pairing.cli_review.codex_async_parse_raw",
                new_callable=AsyncMock,
                return_value=_failure_result("codex"),
            ),
        ):
            result = await run_review("# Plan", ["deepseek-r1", "codex"])

        assert result.models_succeeded == ["deepseek-r1"]
        assert result.models_failed == ["codex"]

    @pytest.mark.asyncio
    async def test_all_failed(self) -> None:
        with patch(
            "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
            new_callable=AsyncMock,
            return_value=_failure_result("deepseek-r1", "Connection refused"),
        ):
            result = await run_review("# Plan", ["deepseek-r1"])

        assert result.models_succeeded == []
        assert result.models_failed == ["deepseek-r1"]

    @pytest.mark.asyncio
    async def test_prompt_version_in_all_results(self) -> None:
        with patch(
            "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
            new_callable=AsyncMock,
            return_value=_success_result("deepseek-r1"),
        ):
            result = await run_review("# Plan", ["deepseek-r1"])

        for r in result.results:
            assert r.prompt_version == PROMPT_VERSION


# ---------------------------------------------------------------------------
# main (CLI entry point)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMain:
    def test_exit_0_on_success(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")

        with patch(
            "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
            new_callable=AsyncMock,
            return_value=_success_result(),
        ):
            code = main(["--file", str(plan_file)])
        assert code == 0

    def test_exit_1_on_all_failed(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")

        with patch(
            "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
            new_callable=AsyncMock,
            return_value=_failure_result("deepseek-r1", "fail"),
        ):
            code = main(["--file", str(plan_file)])
        assert code == 1

    def test_exit_0_on_partial_success(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")

        with (
            patch(
                "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
                new_callable=AsyncMock,
                return_value=_success_result("deepseek-r1"),
            ),
            patch(
                "omniintelligence.review_pairing.cli_review.codex_async_parse_raw",
                new_callable=AsyncMock,
                return_value=_failure_result("codex"),
            ),
        ):
            code = main(
                ["--file", str(plan_file), "--model", "deepseek-r1", "--model", "codex"]
            )
        assert code == 0

    def test_file_not_found(self) -> None:
        code = main(["--file", "/nonexistent/plan.md"])
        assert code == 1

    def test_output_to_file(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")
        output_file = tmp_path / "results.json"

        with patch(
            "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
            new_callable=AsyncMock,
            return_value=_success_result(),
        ):
            code = main(["--file", str(plan_file), "--output", str(output_file)])

        assert code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "models_attempted" in data
        assert "results" in data

    def test_default_model_used_when_none_specified(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Test Plan")

        with patch(
            "omniintelligence.review_pairing.cli_review.llm_async_parse_raw",
            new_callable=AsyncMock,
            return_value=_success_result("deepseek-r1"),
        ) as mock_llm:
            main(["--file", str(plan_file)])

        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args
        assert call_kwargs[1]["model"] == "deepseek-r1"
