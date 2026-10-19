# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Compact review verdict models, call response and prompt 2.0.0 (OMN-20910).

The v1 prompt (1.5.0) and every v1 transport behaviour stay byte for byte; v2
is selected by version.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from omniintelligence.models.review import (
    ModelReviewCallResponse,
    ModelReviewFindingCompact,
    ModelReviewStandingRule,
    ModelReviewStandingRules,
    ModelReviewVerdictCompact,
)
from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    build_review_prompt,
)
from omniintelligence.review_pairing.models_external_review import ModelEndpointConfig
from omniintelligence.review_pairing.prompts import adversarial_reviewer as v1


def _finding(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"c": "T01", "p": "src/x.py", "l": 42, "s": "M"}
    base.update(overrides)
    return base


def _verdict(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "v": "1.0.0",
        "f": [_finding()],
        "more": False,
        "done": True,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Compact verdict models
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCompactModels:
    def test_valid_verdict_round_trips(self) -> None:
        verdict = ModelReviewVerdictCompact.model_validate(_verdict())
        assert verdict.f[0].c == "T01"
        assert verdict.f[0].line == 42
        assert verdict.model_dump(by_alias=True, exclude_none=True) == _verdict()

    def test_done_absent_or_false_is_invalid(self) -> None:
        body = _verdict()
        del body["done"]
        with pytest.raises(ValidationError):
            ModelReviewVerdictCompact.model_validate(body)
        with pytest.raises(ValidationError):
            ModelReviewVerdictCompact.model_validate(_verdict(done=False))

    def test_extra_field_and_bad_severity_are_invalid(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewFindingCompact.model_validate(_finding(extra="x"))
        with pytest.raises(ValidationError):
            ModelReviewFindingCompact.model_validate(_finding(s="critical"))
        with pytest.raises(ValidationError):
            ModelReviewFindingCompact.model_validate(_finding(l=-1))

    def test_x_requires_family_and_note(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewFindingCompact.model_validate(_finding(c="X", n="odd"))
        with pytest.raises(ValidationError):
            ModelReviewFindingCompact.model_validate(_finding(c="X", y="style"))
        ok = ModelReviewFindingCompact.model_validate(
            _finding(c="X", y="style", n="odd retry loop")
        )
        assert ok.y == "style"

    def test_note_is_capped_at_120_characters(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewFindingCompact.model_validate(
                _finding(c="X", y="style", n="n" * 121)
            )

    def test_rule_finding_requires_family(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewFindingCompact.model_validate(
                _finding(c="R:no-hardcoded-topics")
            )
        ok = ModelReviewFindingCompact.model_validate(
            _finding(c="R:no-hardcoded-topics", y="style")
        )
        assert ok.c == "R:no-hardcoded-topics"

    def test_catalog_finding_forbids_family(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewFindingCompact.model_validate(_finding(y="testing"))

    def test_unshaped_code_is_invalid(self) -> None:
        for code in ("", "t01", "T1", "TT01", "R:", "R:Bad Id"):
            with pytest.raises(ValidationError):
                ModelReviewFindingCompact.model_validate(_finding(c=code, y="style"))


# ---------------------------------------------------------------------------
# Typed call response
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCallResponse:
    @pytest.mark.parametrize("stop", ["tool_use", "end_turn", "stop"])
    def test_normal_ends(self, stop: str) -> None:
        response = ModelReviewCallResponse(content="{}", stop_reason=stop)
        assert response.completed_normally

    @pytest.mark.parametrize("stop", ["max_tokens", "length", "refusal", None])
    def test_everything_else_is_not_a_normal_end(self, stop: str | None) -> None:
        response = ModelReviewCallResponse(content="{}", stop_reason=stop)
        assert not response.completed_normally

    def test_frozen_and_closed(self) -> None:
        response = ModelReviewCallResponse(content="x", stop_reason="stop")
        assert ModelReviewCallResponse.model_config["frozen"] is True
        with pytest.raises(ValidationError):
            response.__setattr__("content", "y")
        with pytest.raises(ValidationError):
            ModelReviewCallResponse.model_validate(
                {"content": "x", "stop_reason": "stop", "extra": 1}
            )


# ---------------------------------------------------------------------------
# Prompt 2.0.0 and version selection
# ---------------------------------------------------------------------------


_RULES = ModelReviewStandingRules(
    schema_version=1,
    version="7",
    rules=(
        ModelReviewStandingRule(
            id="never-skip-hooks", mandatory=True, text="No skips."
        ),
        ModelReviewStandingRule(id="no-hardcoded-topics", text="Topics in contracts."),
    ),
)


@pytest.mark.unit
class TestPromptV2:
    def test_version_constants(self) -> None:
        assert v1.PROMPT_VERSION_V2 == "2.0.0"
        assert v1.PROMPT_VERSION == "1.5.0"

    def test_v2_drops_persona_and_prose_format(self) -> None:
        for phrase in (
            "Reviewer Profile",
            "Tone and Style",
            "journal-style",
            "em dash",
        ):
            assert phrase.lower() not in v1.SYSTEM_PROMPT_V2.lower()
        assert '"title"' not in v1.SYSTEM_PROMPT_V2
        assert "proposed_fix" not in v1.SYSTEM_PROMPT_V2

    def test_v2_keeps_definitions_and_pinning_rule(self) -> None:
        text = v1.SYSTEM_PROMPT_V2
        assert "## Severity Definitions" in text
        assert "## Dependency Pinning" in text
        assert "Every finding states a defect" in text
        for field in ('"c"', '"p"', '"l"', '"s"', '"y"', '"n"', '"done"', '"more"'):
            assert field in text

    def test_select_prompt_returns_the_frozen_v1_text(self) -> None:
        selected = v1.select_prompt("1.5.0")
        assert selected.system_prompt == v1.SYSTEM_PROMPT
        assert selected.user_template_pr == v1.USER_PROMPT_TEMPLATE_PR
        assert selected.version == "1.5.0"
        assert v1.select_prompt("2.0.0").system_prompt == v1.SYSTEM_PROMPT_V2

    def test_select_prompt_refuses_unknown_version(self) -> None:
        with pytest.raises(ValueError, match=r"9\.9\.9"):
            v1.select_prompt("9.9.9")

    def test_build_review_prompt_default_is_byte_for_byte_v1(self) -> None:
        system, user = build_review_prompt("DIFF", review_type="pr")
        assert system == v1.SYSTEM_PROMPT
        assert user == v1.USER_PROMPT_TEMPLATE_PR.format(plan_content="DIFF")

    def test_build_review_prompt_selects_v2(self) -> None:
        system, user = build_review_prompt(
            "DIFF",
            review_type="pr",
            prompt_version="2.0.0",
            catalog_section="## Defect Catalog\n- T01 test-asserts-wrong-value",
            standing_rules=_RULES,
        )
        assert system.startswith(v1.SYSTEM_PROMPT_V2)
        assert "## Defect Catalog" in system
        assert "R:never-skip-hooks" in system
        assert "R:no-hardcoded-topics" in system
        assert "DIFF" in user
        assert "Reviewer Profile" not in system

    def test_v2_standing_rules_section_names_codes_and_mandatory(self) -> None:
        section = v1.render_standing_rules_section_v2(_RULES)
        assert "[R:never-skip-hooks] (mandatory)" in section
        assert "[R:no-hardcoded-topics] (standing)" in section
        assert _RULES.digest in section

    def test_verdict_schema_enumerates_codes_rules_and_x(self) -> None:
        schema = v1.build_verdict_schema(
            codes=["T01", "S02"], rule_ids=["never-skip-hooks"], max_findings=25
        )
        props = schema["properties"]
        assert props["done"] == {"const": True}
        assert props["f"]["maxItems"] == 25
        code_enum = props["f"]["items"]["properties"]["c"]["enum"]
        assert code_enum == ["T01", "S02", "R:never-skip-hooks", "X"]
        assert props["f"]["items"]["properties"]["n"]["maxLength"] == 120
        assert props["f"]["items"]["additionalProperties"] is False
        assert set(schema["required"]) == {"v", "f", "more", "done"}

    def test_verdict_schema_without_rules_has_no_r_code(self) -> None:
        schema = v1.build_verdict_schema(codes=["T01"], rule_ids=[], max_findings=5)
        assert schema["properties"]["f"]["items"]["properties"]["c"]["enum"] == [
            "T01",
            "X",
        ]

    def test_max_tokens_has_headroom_per_finding(self) -> None:
        assert v1.max_tokens_for(25) == 256 + 48 * 25
        assert v1.max_tokens_for(0) == 256


# ---------------------------------------------------------------------------
# Transport: the stop reason reaches the caller, v1 behaviour is unchanged
# ---------------------------------------------------------------------------


_CALL_ENV_NAME = "OMN20910_COMPACT_TEST_ENV"


def _config() -> ModelEndpointConfig:
    return ModelEndpointConfig(
        provider="anthropic",
        env_var="OMN20910_COMPACT_TEST_URL",
        kind="api_fallback",
        default_url="https://review-api.example",
        api_model_id="claude-sonnet-5-5",
        api_key_env=_CALL_ENV_NAME,
        timeout_seconds=5.0,
        max_retries=0,
        context_window_tokens=200000,
    )


def _message(stop_reason: str, text: str = '{"done":true}') -> dict[str, object]:
    return {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 100, "output_tokens": 7},
        "stop_reason": stop_reason,
        "model": "claude-sonnet-5-5",
    }


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch):
    original = httpx.AsyncClient
    monkeypatch.setenv(_CALL_ENV_NAME, "placeholder-value")

    def install(body: dict[str, object]) -> None:
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kwargs: original(
                transport=httpx.MockTransport(
                    lambda _request: httpx.Response(200, json=body)
                ),
                **kwargs,
            ),
        )

    return install


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setitem(
        adapter_ai_reviewer.MODEL_REGISTRY, "omn20910-compact", _config()
    )
    return "omn20910-compact"


@pytest.mark.unit
class TestTransportStopReason:
    def test_response_variant_carries_a_max_tokens_stop_reason(
        self, api, registered: str
    ) -> None:
        api(_message("max_tokens", text='{"v":"1","f":['))
        response = asyncio.run(
            adapter_ai_reviewer.call_model_response("sys", "user", registered)
        )
        assert isinstance(response, ModelReviewCallResponse)
        assert response.stop_reason == "max_tokens"
        assert not response.completed_normally
        assert response.content == '{"v":"1","f":['
        assert (response.input_tokens, response.output_tokens) == (100, 7)
        assert response.served_model == "claude-sonnet-5-5"

    def test_response_variant_carries_a_normal_stop_reason(
        self, api, registered: str
    ) -> None:
        api(_message("tool_use"))
        response = asyncio.run(
            adapter_ai_reviewer.call_model_response("sys", "user", registered)
        )
        assert response.completed_normally

    def test_v1_text_call_still_raises_on_max_tokens(
        self, api, registered: str
    ) -> None:
        api(_message("max_tokens"))
        with pytest.raises(RuntimeError, match="incomplete"):
            asyncio.run(adapter_ai_reviewer.call_model("sys", "user", registered))

    def test_v1_text_call_still_returns_text_on_end_turn(
        self, api, registered: str
    ) -> None:
        api(_message("end_turn", text="[]"))
        text = asyncio.run(adapter_ai_reviewer.call_model("sys", "user", registered))
        assert text == "[]"


@pytest.mark.unit
class TestOpenAiCompatibleStopReason:
    def test_finish_reason_usage_and_model_are_carried(self) -> None:
        class _Usage:
            tokens_input = 11
            tokens_output = 3

        class _Finish:
            value = "length"

        class _Reply:
            finish_reason = _Finish()
            usage = _Usage()
            model_used = "qwen-served"

        response = adapter_ai_reviewer._openai_call_response("[", _Reply())
        assert response.stop_reason == "length"
        assert not response.completed_normally
        assert (response.input_tokens, response.output_tokens) == (11, 3)
        assert response.served_model == "qwen-served"

    def test_a_missing_finish_reason_is_unreported_not_normal(self) -> None:
        response = adapter_ai_reviewer._openai_call_response("[]", object())
        assert response.stop_reason is None
        assert not response.completed_normally
        assert (response.input_tokens, response.output_tokens) == (0, 0)
