"""Unit tests for bloom_eval_cli.

Tests list-specs and run subcommands without calling real LLM endpoints.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.bloom_eval_cli.__main__ import _build_parser, _cmd_list_specs
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)

# ---------------------------------------------------------------------------
# list-specs
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_specs_prints_json_array(capsys: pytest.CaptureFixture[str]) -> None:
    _cmd_list_specs()
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert isinstance(parsed, list)


@pytest.mark.unit
def test_list_specs_has_exactly_15_entries(capsys: pytest.CaptureFixture[str]) -> None:
    _cmd_list_specs()
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert len(parsed) == 15


@pytest.mark.unit
def test_list_specs_entries_have_required_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _cmd_list_specs()
    captured = capsys.readouterr()
    parsed: list[dict[str, Any]] = json.loads(captured.out)
    required = {
        "spec_id",
        "failure_mode",
        "domain",
        "description",
        "expected_behavior",
        "failure_indicators",
    }
    for entry in parsed:
        assert required <= entry.keys(), f"Missing keys in entry: {entry}"


@pytest.mark.unit
def test_list_specs_all_failure_modes_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _cmd_list_specs()
    captured = capsys.readouterr()
    parsed: list[dict[str, Any]] = json.loads(captured.out)
    modes_in_output = {e["failure_mode"] for e in parsed}
    all_modes = {m.value for m in EnumFailureMode}
    assert modes_in_output == all_modes


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parser_list_specs_command() -> None:
    parser = _build_parser()
    args = parser.parse_args(["list-specs"])
    assert args.command == "list-specs"


@pytest.mark.unit
def test_parser_run_command_defaults() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        ["run", "--failure-mode", "requirement_omission", "--n", "3"]
    )
    assert args.command == "run"
    assert args.failure_mode == EnumFailureMode.REQUIREMENT_OMISSION
    assert args.n == 3


@pytest.mark.unit
def test_parser_run_default_n() -> None:
    parser = _build_parser()
    args = parser.parse_args(["run", "--failure-mode", "invented_requirements"])
    assert args.n == 5


# ---------------------------------------------------------------------------
# run subcommand (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_run_cmd_exits_without_env_vars() -> None:
    from omniintelligence.bloom_eval_cli.__main__ import _cmd_run

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            await _cmd_run(EnumFailureMode.REQUIREMENT_OMISSION, n=1)
        assert exc_info.value.code == 1


@pytest.mark.unit
async def test_run_cmd_prints_suite_result_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from omniintelligence.bloom_eval_cli.__main__ import _cmd_run

    mock_scenarios = ["scenario text 0", "scenario text 1", "scenario text 2"]

    env = {
        "LLM_CODER_FAST_URL": "http://localhost:8001",
        "LLM_DEEPSEEK_R1_URL": "http://localhost:8101",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.generate_scenarios = AsyncMock(return_value=mock_scenarios)

    with patch.dict("os.environ", env):
        with patch(
            "omniintelligence.bloom_eval_cli.__main__.EvalLLMClient",
            return_value=mock_client,
        ):
            await _cmd_run(EnumFailureMode.REQUIREMENT_OMISSION, n=3)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert "suite_id" in parsed
    assert "failure_mode" in parsed
    assert parsed["failure_mode"] == "requirement_omission"
    assert parsed["total_scenarios"] == 3


@pytest.mark.unit
async def test_run_cmd_suite_result_passed_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from omniintelligence.bloom_eval_cli.__main__ import _cmd_run

    mock_scenarios = ["s0", "s1"]

    env = {
        "LLM_CODER_FAST_URL": "http://localhost:8001",
        "LLM_DEEPSEEK_R1_URL": "http://localhost:8101",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.generate_scenarios = AsyncMock(return_value=mock_scenarios)

    with patch.dict("os.environ", env):
        with patch(
            "omniintelligence.bloom_eval_cli.__main__.EvalLLMClient",
            return_value=mock_client,
        ):
            await _cmd_run(EnumFailureMode.INVENTED_REQUIREMENTS, n=2)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["total_scenarios"] == 2
    assert parsed["passed_count"] == parsed["total_scenarios"]
