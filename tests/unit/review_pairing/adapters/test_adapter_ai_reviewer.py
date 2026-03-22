# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for the LLM-backed AI reviewer adapter.

Covers: build_review_prompt, parse_review_response, map_severity,
to_review_findings, parse_raw, async_parse_raw, model registry.

Reference: OMN-5790, OMN-5791
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    MODEL_REGISTRY,
    build_review_prompt,
    map_severity,
    parse_raw,
    parse_review_response,
    to_review_findings,
)
from omniintelligence.review_pairing.models import (
    FindingSeverity,
    ReviewFindingObserved,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
)

_REPO = "plan-review"
_PR_ID = 1
_SHA = "abc1234"


def _well_formed_findings() -> list[dict[str, str | None]]:
    return [
        {
            "category": "architecture",
            "severity": "critical",
            "title": "Missing error handling",
            "description": "No retry logic for API calls",
            "evidence": "Task 3 step 2 assumes stable NDJSON",
            "proposed_fix": "Add exponential backoff",
            "location": "task-3",
        },
        {
            "category": "testing",
            "severity": "minor",
            "title": "Incomplete test coverage",
            "description": "No edge case tests for empty input",
            "evidence": "Acceptance criteria missing empty plan test",
            "proposed_fix": "Add test for empty plan content",
            "location": None,
        },
    ]


# ---------------------------------------------------------------------------
# build_review_prompt
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildReviewPrompt:
    def test_returns_system_and_user_prompt(self) -> None:
        sys_prompt, user_prompt = build_review_prompt("# My Plan")
        assert sys_prompt == SYSTEM_PROMPT
        assert "# My Plan" in user_prompt

    def test_user_prompt_does_not_contain_placeholder(self) -> None:
        _, user_prompt = build_review_prompt("test content")
        assert "{plan_content}" not in user_prompt


# ---------------------------------------------------------------------------
# parse_review_response
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseReviewResponse:
    def test_parses_raw_json_array(self) -> None:
        raw = json.dumps(_well_formed_findings())
        result = parse_review_response(raw)
        assert len(result) == 2
        assert result[0]["category"] == "architecture"

    def test_parses_json_in_markdown_fences(self) -> None:
        raw = (
            "Here are my findings:\n```json\n"
            + json.dumps(_well_formed_findings())
            + "\n```\nThank you."
        )
        result = parse_review_response(raw)
        assert len(result) == 2

    def test_parses_json_with_leading_commentary(self) -> None:
        raw = "I found issues:\n\n" + json.dumps(_well_formed_findings())
        result = parse_review_response(raw)
        assert len(result) == 2

    def test_returns_empty_for_completely_malformed(self) -> None:
        result = parse_review_response("This is not JSON at all")
        assert result == []

    def test_returns_empty_for_non_list_json(self) -> None:
        result = parse_review_response('{"key": "value"}')
        assert result == []

    def test_returns_empty_for_empty_string(self) -> None:
        result = parse_review_response("")
        assert result == []

    def test_parses_fenced_json_without_language_tag(self) -> None:
        raw = (
            "```\n"
            + json.dumps(
                [
                    {
                        "category": "style",
                        "severity": "nit",
                        "title": "Test",
                        "description": "D",
                        "evidence": "E",
                        "proposed_fix": "F",
                        "location": None,
                    }
                ]
            )
            + "\n```"
        )
        result = parse_review_response(raw)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# map_severity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMapSeverity:
    def test_critical_maps_to_error(self) -> None:
        assert map_severity("critical") == FindingSeverity.ERROR

    def test_major_maps_to_warning(self) -> None:
        assert map_severity("major") == FindingSeverity.WARNING

    def test_minor_maps_to_info(self) -> None:
        assert map_severity("minor") == FindingSeverity.INFO

    def test_nit_maps_to_hint(self) -> None:
        assert map_severity("nit") == FindingSeverity.HINT

    def test_case_insensitive(self) -> None:
        assert map_severity("Critical") == FindingSeverity.ERROR
        assert map_severity("MAJOR") == FindingSeverity.WARNING

    def test_strips_whitespace(self) -> None:
        assert map_severity("  minor  ") == FindingSeverity.INFO

    def test_unknown_defaults_to_info(self) -> None:
        assert map_severity("major issue") == FindingSeverity.INFO

    def test_empty_defaults_to_info(self) -> None:
        assert map_severity("") == FindingSeverity.INFO


# ---------------------------------------------------------------------------
# to_review_findings
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestToReviewFindings:
    def test_converts_well_formed_findings(self) -> None:
        findings = to_review_findings(
            _well_formed_findings(),
            "deepseek-r1",
            repo=_REPO,
            pr_id=_PR_ID,
            commit_sha=_SHA,
        )
        assert len(findings) == 2
        assert all(isinstance(f, ReviewFindingObserved) for f in findings)

    def test_rule_id_format(self) -> None:
        findings = to_review_findings(
            _well_formed_findings(),
            "deepseek-r1",
        )
        assert findings[0].rule_id == "ai-reviewer:deepseek-r1:architecture"
        assert findings[1].rule_id == "ai-reviewer:deepseek-r1:testing"

    def test_rule_id_changes_per_model(self) -> None:
        findings = to_review_findings(
            _well_formed_findings(),
            "qwen3-coder",
        )
        assert findings[0].rule_id == "ai-reviewer:qwen3-coder:architecture"

    def test_severity_mapping(self) -> None:
        findings = to_review_findings(
            _well_formed_findings(),
            "deepseek-r1",
        )
        assert findings[0].severity == FindingSeverity.ERROR  # critical
        assert findings[1].severity == FindingSeverity.INFO  # minor

    def test_confidence_tier_is_probabilistic(self) -> None:
        findings = to_review_findings(
            _well_formed_findings(),
            "deepseek-r1",
        )
        for f in findings:
            # Confidence tier is implicit via tool_name convention
            assert f.tool_name.startswith("ai-reviewer:")
            assert f.tool_version == PROMPT_VERSION

    def test_tool_name_includes_model(self) -> None:
        findings = to_review_findings(
            _well_formed_findings(),
            "deepseek-r1",
        )
        assert findings[0].tool_name == "ai-reviewer:deepseek-r1"

    def test_skips_non_dict_items(self) -> None:
        findings = to_review_findings(
            [
                {
                    "category": "style",
                    "severity": "nit",
                    "title": "OK",
                    "description": "D",
                    "evidence": "E",
                    "proposed_fix": "F",
                    "location": None,
                },
                "not a dict",
                42,
            ],
            "deepseek-r1",
        )
        assert len(findings) == 1

    def test_empty_input_returns_empty(self) -> None:
        assert to_review_findings([], "deepseek-r1") == []

    def test_missing_fields_use_defaults(self) -> None:
        findings = to_review_findings(
            [{"severity": "major"}],
            "deepseek-r1",
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "ai-reviewer:deepseek-r1:unknown"
        assert findings[0].severity == FindingSeverity.WARNING


# ---------------------------------------------------------------------------
# parse_raw (synchronous public interface)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseRaw:
    def test_well_formed_json_string(self) -> None:
        raw = json.dumps(_well_formed_findings())
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 2
        assert all(isinstance(f, ReviewFindingObserved) for f in findings)

    def test_malformed_json_returns_empty(self) -> None:
        findings = parse_raw("not json", repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    def test_empty_findings_returns_empty(self) -> None:
        findings = parse_raw("[]", repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    def test_model_kwarg_changes_rule_id(self) -> None:
        raw = json.dumps(_well_formed_findings())
        findings = parse_raw(raw, model="qwen3-coder")
        assert findings[0].rule_id == "ai-reviewer:qwen3-coder:architecture"

    def test_default_model_is_deepseek_r1(self) -> None:
        raw = json.dumps(_well_formed_findings())
        findings = parse_raw(raw)
        assert findings[0].rule_id == "ai-reviewer:deepseek-r1:architecture"

    def test_unknown_model_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown model 'foo'"):
            parse_raw("[]", model="foo")

    def test_unknown_model_error_lists_valid_keys(self) -> None:
        with pytest.raises(ValueError, match="deepseek-r1"):
            parse_raw("[]", model="invalid-model")

    def test_dict_input(self) -> None:
        # parse_raw also accepts dict; it JSON-serializes it
        findings = parse_raw({"not": "a list"})
        assert findings == []


# ---------------------------------------------------------------------------
# async_parse_raw
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAsyncParseRaw:
    @pytest.mark.asyncio
    async def test_success_returns_result_envelope(self) -> None:
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        mock_response = json.dumps(_well_formed_findings())

        with patch.object(
            adapter_ai_reviewer,
            "call_model",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await adapter_ai_reviewer.async_parse_raw(
                "# Test Plan\nDo stuff.",
                model="deepseek-r1",
            )

        assert isinstance(result, ModelExternalReviewResult)
        assert result.success is True
        assert result.model == "deepseek-r1"
        assert result.prompt_version == PROMPT_VERSION
        assert result.result_count == 2
        assert len(result.findings) == 2

    @pytest.mark.asyncio
    async def test_malformed_response_returns_empty_findings(self) -> None:
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.object(
            adapter_ai_reviewer,
            "call_model",
            new_callable=AsyncMock,
            return_value="not json at all",
        ):
            result = await adapter_ai_reviewer.async_parse_raw(
                "# Plan",
                model="deepseek-r1",
            )

        assert result.success is True  # Parsing succeeded, just no findings
        assert result.result_count == 0
        assert result.findings == []

    @pytest.mark.asyncio
    async def test_call_failure_returns_error_envelope(self) -> None:
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.object(
            adapter_ai_reviewer,
            "call_model",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Connection refused"),
        ):
            result = await adapter_ai_reviewer.async_parse_raw(
                "# Plan",
                model="deepseek-r1",
            )

        assert result.success is False
        assert "Connection refused" in (result.error or "")
        assert result.result_count == 0

    @pytest.mark.asyncio
    async def test_prompt_version_in_result(self) -> None:
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.object(
            adapter_ai_reviewer,
            "call_model",
            new_callable=AsyncMock,
            return_value="[]",
        ):
            result = await adapter_ai_reviewer.async_parse_raw(
                "# Plan",
                model="deepseek-r1",
            )

        assert result.prompt_version == PROMPT_VERSION

    @pytest.mark.asyncio
    async def test_unknown_model_returns_error(self) -> None:
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        result = await adapter_ai_reviewer.async_parse_raw(
            "# Plan",
            model="nonexistent",
        )
        assert result.success is False
        assert "Unknown model" in (result.error or "")


# ---------------------------------------------------------------------------
# Model registry (OMN-5791)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestModelRegistry:
    def test_registry_has_expected_models(self) -> None:
        assert "deepseek-r1" in MODEL_REGISTRY
        assert "qwen3-coder" in MODEL_REGISTRY
        assert "qwen3-14b" in MODEL_REGISTRY

    def test_deepseek_r1_config(self) -> None:
        config = MODEL_REGISTRY["deepseek-r1"]
        assert config.env_var == "LLM_DEEPSEEK_R1_URL"
        assert config.kind == "reasoning"
        assert config.timeout_seconds == 120.0

    def test_qwen3_coder_config(self) -> None:
        config = MODEL_REGISTRY["qwen3-coder"]
        assert config.env_var == "LLM_CODER_URL"
        assert config.kind == "long_context"

    def test_qwen3_14b_config(self) -> None:
        config = MODEL_REGISTRY["qwen3-14b"]
        assert config.env_var == "LLM_CODER_FAST_URL"
        assert config.kind == "fast_review"
        assert config.timeout_seconds == 60.0

    def test_env_var_override(self) -> None:
        """Verify model URL resolution respects env vars."""
        from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
            _resolve_model_url,
        )

        with patch.dict("os.environ", {"LLM_CODER_URL": "http://custom:9999"}):
            url = _resolve_model_url("qwen3-coder")
        assert url == "http://custom:9999"

    def test_default_url_when_env_unset(self) -> None:
        from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
            _resolve_model_url,
        )

        with patch.dict("os.environ", {}, clear=True):
            url = _resolve_model_url("deepseek-r1")
        assert url == "http://192.168.86.200:8101"

    def test_unknown_model_raises(self) -> None:
        from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
            _resolve_model_url,
        )

        with pytest.raises(ValueError, match=r"Unknown model 'foo'\. Valid:"):
            _resolve_model_url("foo")
