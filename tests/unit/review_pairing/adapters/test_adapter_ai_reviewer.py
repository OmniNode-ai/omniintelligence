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
    EnumFindingSeverity,
    ModelReviewFindingObserved,
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

    def test_wraps_single_finding_object_as_one_element_list(self) -> None:
        """OMN-14176: a bare JSON object (no array wrapper) is treated as a
        single finding rather than discarded. Observed live with
        enable_thinking:false -- without a reasoning scratchpad, the model
        sometimes emits one well-formed finding without the array wrapper
        the system prompt requires."""
        result = parse_review_response('{"key": "value"}')
        assert result == [{"key": "value"}]

    def test_returns_empty_for_non_dict_non_list_json(self) -> None:
        result = parse_review_response('"just a string"')
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
        assert map_severity("critical") == EnumFindingSeverity.ERROR

    def test_major_maps_to_warning(self) -> None:
        assert map_severity("major") == EnumFindingSeverity.WARNING

    def test_minor_maps_to_info(self) -> None:
        assert map_severity("minor") == EnumFindingSeverity.INFO

    def test_nit_maps_to_hint(self) -> None:
        assert map_severity("nit") == EnumFindingSeverity.HINT

    def test_case_insensitive(self) -> None:
        assert map_severity("Critical") == EnumFindingSeverity.ERROR
        assert map_severity("MAJOR") == EnumFindingSeverity.WARNING

    def test_strips_whitespace(self) -> None:
        assert map_severity("  minor  ") == EnumFindingSeverity.INFO

    def test_unknown_defaults_to_info(self) -> None:
        assert map_severity("major issue") == EnumFindingSeverity.INFO

    def test_empty_defaults_to_info(self) -> None:
        assert map_severity("") == EnumFindingSeverity.INFO


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
        assert all(isinstance(f, ModelReviewFindingObserved) for f in findings)

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
        assert findings[0].severity == EnumFindingSeverity.ERROR  # critical
        assert findings[1].severity == EnumFindingSeverity.INFO  # minor

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
        assert findings[0].severity == EnumFindingSeverity.WARNING


# ---------------------------------------------------------------------------
# parse_raw (synchronous public interface)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseRaw:
    def test_well_formed_json_string(self) -> None:
        raw = json.dumps(_well_formed_findings())
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 2
        assert all(isinstance(f, ModelReviewFindingObserved) for f in findings)

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
        # parse_raw also accepts dict; it JSON-serializes it. A dict that
        # isn't a findings list is still a single well-formed JSON object,
        # so OMN-14176's parse_review_response wraps it as one finding
        # (with defaults for missing fields) rather than discarding it.
        findings = parse_raw({"not": "a list"})
        assert len(findings) == 1

    def test_dict_input_missing_all_fields_uses_defaults(self) -> None:
        findings = parse_raw({"not": "a list"})
        assert findings[0].severity.value == "info"


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
        assert config.timeout_seconds == 300.0

    def test_deepseek_r1_enable_thinking_false(self) -> None:
        """OMN-16407 residual: repointed to the same SGLang :8000 endpoint
        as qwen3-review/qwen3-review-b, which requires enable_thinking:false
        to avoid the truncated-preamble bug (OMN-14176)."""
        assert MODEL_REGISTRY["deepseek-r1"].enable_thinking is False

    def test_qwen3_coder_config(self) -> None:
        config = MODEL_REGISTRY["qwen3-coder"]
        assert config.env_var == "LLM_CODER_URL"
        assert config.kind == "long_context"

    def test_qwen3_14b_config(self) -> None:
        config = MODEL_REGISTRY["qwen3-14b"]
        assert config.env_var == "LLM_CODER_FAST_URL"
        assert config.kind == "fast_review"
        assert config.timeout_seconds == 60.0

    def test_qwen3_review_enable_thinking_false(self) -> None:
        """OMN-14176: model_registry.yaml declares enable_thinking: false
        for qwen3-review -- proves the YAML round-trips into config, not
        just that call_model's mocked behavior matches."""
        assert MODEL_REGISTRY["qwen3-review"].enable_thinking is False

    def test_qwen3_review_b_enable_thinking_false(self) -> None:
        assert MODEL_REGISTRY["qwen3-review-b"].enable_thinking is False

    def test_qwen3_review_b_timeout_lowered_after_gpu1_rma(self) -> None:
        """OMN-16407: lowered 1200 -> 300 after the RTX 4090 qwen3-review-b
        targeted was physically removed for RMA and it was repointed to the
        SGLang :8000 endpoint, live-measured this session at ~131 tok/s
        (a 37,230-prompt-token / 3,694-completion-token real review payload
        completed in 34.7s wall-clock, finish_reason=stop). 300s keeps
        ~8.6x margin over that measured worst case."""
        assert MODEL_REGISTRY["qwen3-review-b"].timeout_seconds == 300.0

    def test_qwen3_review_b_max_retries_lowered(self) -> None:
        """OMN-15115: lowered default(3) -> 1 -- retrying a systematically-slow
        (not transiently-flaky) single-concurrency-slot endpoint just re-spends
        the same wall-clock budget for the same outcome."""
        assert MODEL_REGISTRY["qwen3-review-b"].max_retries == 1

    def test_qwen3_review_max_retries_unset(self) -> None:
        """qwen3-review (the 5090 endpoint) is untouched by OMN-15115 -- no
        per-model max_retries override, so call_model() applies the
        transport's own default."""
        assert MODEL_REGISTRY["qwen3-review"].max_retries is None

    def test_unconfigured_model_defaults_enable_thinking_true(self) -> None:
        """A model that doesn't set enable_thinking in the registry
        defaults to True (additive: pre-OMN-14176 behavior unaffected)."""
        assert MODEL_REGISTRY["qwen3-coder"].enable_thinking is True

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
        assert url == "http://192.168.86.201:8000"

    def test_deepseek_r1_default_model_id(self) -> None:
        """Assert deepseek-r1 resolves the live model ID (OMN-8654; repointed
        OMN-16407 residual 2026-08-23 after the RTX 4090 backend was
        physically removed for RMA -- now the same SGLang :8000 id
        qwen3-review/qwen3-review-b serve)."""
        config = MODEL_REGISTRY["deepseek-r1"]
        assert config.api_model_id == "qwen3.8"

    def test_deepseek_r1_default_url_is_201_8000(self) -> None:
        """Assert deepseek-r1 default URL points to .201:8000 (OMN-8654;
        repointed OMN-16407 residual 2026-08-23 -- :8001's RTX 4090 was
        physically removed for RMA)."""
        from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
            _resolve_model_url,
        )

        with patch.dict("os.environ", {}, clear=True):
            url = _resolve_model_url("deepseek-r1")
        assert url == "http://192.168.86.201:8000"

    def test_unknown_model_raises(self) -> None:
        from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
            _resolve_model_url,
        )

        with pytest.raises(ValueError, match=r"Unknown model 'foo'\. Valid:"):
            _resolve_model_url("foo")


# ---------------------------------------------------------------------------
# OMN-11008: LOCAL_LLM_SHARED_SECRET ownership
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLocalLlmSharedSecretOwnership:
    """The adapter must not synthesize or mutate LOCAL_LLM_SHARED_SECRET.

    Ownership lives in the LLM HTTP transport
    (omnibase_infra.mixins.mixin_llm_http_transport), which reads the secret
    from os.environ on every call and fails closed if absent. The adapter
    previously wrote a 'cli-review-unsigned' placeholder into os.environ as
    a side-channel, which defeated the fail-closed design and put the
    runtime/security source path outside typed contract/config ownership.

    See OMN-11008 and the OMN-11004 env/local-path classification.
    """

    def test_module_does_not_set_local_llm_shared_secret_in_source(self) -> None:
        """call_model must not contain a write to os.environ['LOCAL_LLM_SHARED_SECRET'].

        Static source-text check — the regression would be re-introducing the
        synthesis line.
        """
        import inspect

        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        source = inspect.getsource(adapter_ai_reviewer)
        # The synthesis pattern that OMN-11008 removes: writing into os.environ
        # with the LOCAL_LLM_SHARED_SECRET key. Reads (os.environ.get/[]) are
        # fine; the transport itself reads on every call.
        assert (
            'os.environ["LOCAL_LLM_SHARED_SECRET"]' not in source
            and "os.environ['LOCAL_LLM_SHARED_SECRET']" not in source
        ), (
            "adapter_ai_reviewer must not write LOCAL_LLM_SHARED_SECRET into "
            "os.environ; ownership lives in the LLM HTTP transport (OMN-11008)."
        )

    @pytest.mark.asyncio
    async def test_call_model_does_not_mutate_environ_when_secret_set(self) -> None:
        """When the secret is set, call_model must not rewrite or clobber it."""
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        sentinel = "preset-by-caller-do-not-overwrite"  # pragma: allowlist secret
        with patch.dict(
            "os.environ",
            {"LOCAL_LLM_SHARED_SECRET": sentinel, "LLM_CODER_URL": "http://x:1"},
            clear=False,
        ):
            with patch(
                "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
            ) as handler_cls:
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text="[]")
                handler_cls.return_value = handler_inst
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="qwen3-coder"
                )
            import os as _os

            assert _os.environ["LOCAL_LLM_SHARED_SECRET"] == sentinel

    @pytest.mark.asyncio
    async def test_call_model_does_not_set_environ_when_secret_absent(self) -> None:
        """When the secret is absent, call_model must not write a placeholder.

        The transport will fail closed when invoked without the secret; that
        is the contract. The adapter must not paper over it with a side-channel
        write.
        """
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.dict("os.environ", {"LLM_CODER_URL": "http://x:1"}, clear=True):
            with patch(
                "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
            ) as handler_cls:
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text="[]")
                handler_cls.return_value = handler_inst
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="qwen3-coder"
                )
            import os as _os

            assert "LOCAL_LLM_SHARED_SECRET" not in _os.environ


class TestCallModelThinkingSuppression:
    """call_model reads enable_thinking from the DECLARATIVE per-model
    registry config (model_registry.yaml -> ModelEndpointConfig.enable_thinking)
    and threads it into extra_body -- it is not a code-baked constant.
    Flipping reasoning on/off for a model is a config edit, not a code
    change + redeploy.

    OMN-14176: the extra_body passthrough mechanism itself is the proven,
    merged fix (already live in node_generation_consumer for SEA generation,
    OMN-12816) -- it was never wired into the reviewer. Without disabling
    reasoning, reviewer models spend most of max_tokens on an unwrapped
    reasoning preamble that defeats the strip-think-tags fallback below and
    the JSON extraction in parse_review_response. qwen3-review and
    qwen3-review-b are configured enable_thinking: false in the registry.
    """

    @pytest.mark.asyncio
    async def test_call_model_reads_enable_thinking_false_from_registry(self) -> None:
        """qwen3-review-b is configured enable_thinking: false in
        model_registry.yaml -- the request must carry that value, read from
        config, not a hardcoded literal."""
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.dict(
            "os.environ",
            {
                "LOCAL_LLM_SHARED_SECRET": "x",  # pragma: allowlist secret
                "LLM_QWEN3_REVIEW_B_URL": "http://x:1",
            },
            clear=False,
        ):
            with patch(
                "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
            ) as handler_cls:
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text="[]")
                handler_cls.return_value = handler_inst
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="qwen3-review-b"
                )

            request = handler_inst.handle.call_args[0][0]
            assert request.extra_body == {
                "chat_template_kwargs": {"enable_thinking": False}
            }

    @pytest.mark.asyncio
    async def test_call_model_reads_enable_thinking_true_default_from_registry(
        self,
    ) -> None:
        """A model that does NOT set enable_thinking in the registry
        (qwen3-coder) defaults to True (additive: pre-OMN-14176 behavior).
        Proves the toggle is genuinely declarative config, not a hardcoded
        constant -- different models resolve to different values from the
        same code path."""
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.dict(
            "os.environ",
            {
                "LOCAL_LLM_SHARED_SECRET": "x",  # pragma: allowlist secret
                "LLM_CODER_URL": "http://x:1",
            },
            clear=False,
        ):
            with patch(
                "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
            ) as handler_cls:
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text="[]")
                handler_cls.return_value = handler_inst
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="qwen3-coder"
                )

            request = handler_inst.handle.call_args[0][0]
            assert request.extra_body == {
                "chat_template_kwargs": {"enable_thinking": True}
            }

    @pytest.mark.asyncio
    async def test_call_model_strips_through_unmatched_closing_think_tag(
        self,
    ) -> None:
        """A response with only a closing </think> (no opener) must still be
        stripped down to the content following it.

        Reproduces the live-observed failure: the model narrates reasoning as
        plain prose (no <think> opener) but emits a trailing </think> marker,
        which the paired-tag regex cannot match, leaving reasoning-preamble
        brackets to defeat parse_review_response's bracket-search fallback.
        """
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        raw = (
            "Here's a thinking process: - [Done] - [Proceeds]\n</think>\n\n"
            '[{"category": "correctness"}]'
        )
        with patch.dict(
            "os.environ",
            {
                "LOCAL_LLM_SHARED_SECRET": "x",  # pragma: allowlist secret
                "LLM_CODER_URL": "http://x:1",
            },
            clear=False,
        ):
            with patch(
                "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
            ) as handler_cls:
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text=raw)
                handler_cls.return_value = handler_inst
                result = await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="qwen3-coder"
                )

        assert result == '[{"category": "correctness"}]'

    @pytest.mark.asyncio
    async def test_call_model_still_strips_paired_think_tags(self) -> None:
        """The original paired <think>...</think> case must keep working."""
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        raw = "<think>reasoning here</think>\n\n[]"
        with patch.dict(
            "os.environ",
            {
                "LOCAL_LLM_SHARED_SECRET": "x",  # pragma: allowlist secret
                "LLM_CODER_URL": "http://x:1",
            },
            clear=False,
        ):
            with patch(
                "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
            ) as handler_cls:
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text=raw)
                handler_cls.return_value = handler_inst
                result = await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="qwen3-coder"
                )

        assert result == "[]"


class TestCallModelCloudBearerAuth:
    """OMN-17492: authenticated cloud reviewers (api_key_env in the registry).

    glm-review rides the z.ai GLM Coding Plan through the SAME
    HandlerLlmOpenaiCompatible path as the local models; the only deltas are
    a Bearer key read from the declared env var (fail-closed per-model), the
    COMPLETE endpoint URL used verbatim, and the GLM spelling of the
    thinking toggle. The key VALUE never appears in the registry or in any
    error message.
    """

    @pytest.mark.asyncio
    async def test_glm_review_threads_bearer_key_and_glm_wire_shape(self) -> None:
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.dict(
            "os.environ",
            {
                "LOCAL_LLM_SHARED_SECRET": "x",  # pragma: allowlist secret
                "LLM_GLM_API_KEY": "test-glm-key",  # pragma: allowlist secret
            },
            clear=False,
        ):
            with patch(
                "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
            ) as handler_cls:
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text="[]")
                handler_cls.return_value = handler_inst
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="glm-review"
                )

            request = handler_inst.handle.call_args[0][0]
            assert request.api_key == "test-glm-key"  # pragma: allowlist secret
            # Registry URL is COMPLETE (ends /chat/completions) and must be
            # used verbatim -- appending /v1/chat/completions would 404.
            assert (
                request.endpoint_url
                == "https://api.z.ai/api/coding/paas/v4/chat/completions"
            )
            assert request.model == "glm-5.3-flash"
            # GLM wire shape for the declarative enable_thinking:false --
            # z.ai has no chat_template_kwargs surface.
            assert request.extra_body == {"thinking": {"type": "disabled"}}

    @pytest.mark.asyncio
    async def test_glm_review_fails_closed_when_key_missing(self) -> None:
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.dict(
            "os.environ",
            {"LOCAL_LLM_SHARED_SECRET": "x"},  # pragma: allowlist secret
            clear=True,
        ):
            with patch(
                "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
            ) as handler_cls:
                handler_inst = AsyncMock()
                handler_cls.return_value = handler_inst
                with pytest.raises(ValueError, match="LLM_GLM_API_KEY"):
                    await adapter_ai_reviewer.call_model(
                        "sys", "usr", model_key="glm-review"
                    )
                handler_inst.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_glm_review_fails_closed_when_key_empty(self) -> None:
        """Whitespace-only key is as absent as no key at all."""
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.dict(
            "os.environ",
            {
                "LOCAL_LLM_SHARED_SECRET": "x",  # pragma: allowlist secret
                "LLM_GLM_API_KEY": "   ",
            },
            clear=True,
        ):
            with pytest.raises(ValueError, match="LLM_GLM_API_KEY"):
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="glm-review"
                )

    @pytest.mark.asyncio
    async def test_glm_review_missing_key_error_never_leaks_a_value(self) -> None:
        """The fail-closed error names the ENV VAR, never any value."""
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.dict(
            "os.environ",
            {"LOCAL_LLM_SHARED_SECRET": "sekrit-local"},  # pragma: allowlist secret
            clear=True,
        ):
            with pytest.raises(ValueError) as exc_info:
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="glm-review"
                )
        assert "sekrit-local" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_local_model_sends_no_api_key(self) -> None:
        """Pre-OMN-17492 entries are unaffected: no Bearer key on local calls."""
        from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

        with patch.dict(
            "os.environ",
            {
                "LOCAL_LLM_SHARED_SECRET": "x",  # pragma: allowlist secret
                "LLM_CODER_URL": "http://x:1",
            },
            clear=False,
        ):
            with patch(
                "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
            ) as handler_cls:
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text="[]")
                handler_cls.return_value = handler_inst
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="qwen3-coder"
                )

            request = handler_inst.handle.call_args[0][0]
            assert request.api_key is None
