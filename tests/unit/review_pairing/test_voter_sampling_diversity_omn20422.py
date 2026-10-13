# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The two lab voters are sent distinct sampling and a distinct focus (OMN-20422).

qwen3-review and local-studio-planner both serve the same Qwen3.8-27B
weights, so identical requests would make the two-voter quorum one
model agreeing with itself. The registry now declares per-model ``temperature``,
``top_p`` and ``review_focus``; ``call_model`` sends them. These tests read the
request each voter actually receives, not the registry text alone.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from omnibase_infra.nodes.node_llm_inference_effect.models.model_llm_inference_request import (
    ModelLlmInferenceRequest,
)
from pydantic import ValidationError

from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.model_registry_loader import load_registry
from omniintelligence.review_pairing.models_external_review import (
    ModelEndpointConfig,
)

pytestmark = [pytest.mark.unit]

_VOTERS = ("qwen3-review", "local-studio-planner")
_SYSTEM = "SYSTEM-PROMPT-UNDER-TEST"
_URL_ENV = {
    "qwen3-review": "LLM_QWEN3_REVIEW_URL",
    "local-studio-planner": "LLM_LOCAL_STUDIO_PLANNER_URL",
}


async def _request_for(
    model_key: str, *, system: str = _SYSTEM
) -> ModelLlmInferenceRequest:
    """Run ``call_model`` for ``model_key`` and return the request it built."""
    env = dict.fromkeys(("LOCAL_LLM_SHARED_SECRET",), "x")
    env[_URL_ENV[model_key]] = "http://x:1"
    with (
        patch.dict("os.environ", env, clear=False),
        patch(
            "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
        ) as handler_cls,
        patch(
            "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.resolve_served_model_id",
            return_value="Qwen3.8-27B",
        ),
    ):
        handler_inst = AsyncMock()
        handler_inst.handle.return_value = AsyncMock(generated_text="[]")
        handler_cls.return_value = handler_inst
        await adapter_ai_reviewer.call_model(system, "usr", model_key=model_key)
    request: ModelLlmInferenceRequest = handler_inst.handle.call_args[0][0]
    return request


class TestRegistryDeclaresDistinctVoters:
    def test_sampling_differs_between_the_two_voters(self) -> None:
        models = load_registry().models
        a, b = (models[k] for k in _VOTERS)
        assert (a.temperature, a.top_p) != (b.temperature, b.top_p)
        assert a.temperature != b.temperature

    def test_focus_differs_and_is_declared_for_both(self) -> None:
        models = load_registry().models
        a, b = (models[k].review_focus for k in _VOTERS)
        assert a and b
        assert a != b

    @pytest.mark.parametrize("key", _VOTERS)
    def test_focus_adds_emphasis_and_never_narrows_the_remit(self, key: str) -> None:
        focus = load_registry().models[key].review_focus
        assert "whole change" in focus
        assert "not a narrower remit" in focus

    def test_the_quorum_floor_is_untouched(self) -> None:
        assert load_registry().review_quorum.min_agreeing_models == 2

    def test_both_voters_are_still_in_the_local_roster(self) -> None:
        assert set(_VOTERS) <= set(load_registry().local_model_keys)


class TestEachVoterReceivesItsOwnSettings:
    @pytest.mark.asyncio
    async def test_the_two_voters_get_distinct_requests(self) -> None:
        first = await _request_for("qwen3-review")
        second = await _request_for("local-studio-planner")
        assert first.temperature != second.temperature
        assert first.top_p != second.top_p
        assert first.system_prompt != second.system_prompt

    @pytest.mark.asyncio
    @pytest.mark.parametrize("key", _VOTERS)
    async def test_the_request_carries_the_registry_values(self, key: str) -> None:
        cfg = load_registry().models[key]
        request = await _request_for(key)
        assert request.temperature == cfg.temperature
        assert request.top_p == cfg.top_p
        assert request.system_prompt == (
            f"{_SYSTEM}\n\n## Reviewer Focus\n\n{cfg.review_focus}"
        )

    @pytest.mark.asyncio
    async def test_the_voter_that_kept_its_sampling_still_sends_zero_point_three(
        self,
    ) -> None:
        request = await _request_for("qwen3-review")
        assert request.temperature == 0.3
        assert request.top_p is None

    @pytest.mark.asyncio
    async def test_the_shared_prompt_is_the_prefix_of_both_voters(self) -> None:
        for key in _VOTERS:
            request = await _request_for(key)
            assert request.system_prompt.startswith(_SYSTEM)


class TestAnEntryThatDeclaresNothingIsUnchanged:
    """Positive control: no declared sampling means the previous request."""

    @pytest.mark.asyncio
    async def test_no_declared_sampling_sends_the_adapter_default(self) -> None:
        bare = ModelEndpointConfig(
            env_var="LLM_QWEN3_REVIEW_URL",
            default_url="http://x:1",
            kind="code_review",
            timeout_seconds=10.0,
            model_id_source="served",
        )
        with patch.dict(
            adapter_ai_reviewer.MODEL_REGISTRY, {"qwen3-review": bare}, clear=False
        ):
            request = await _request_for("qwen3-review")
        assert request.temperature == adapter_ai_reviewer._DEFAULT_TEMPERATURE
        assert request.top_p is None
        assert request.system_prompt == _SYSTEM


class TestTheFieldsAreBounded:
    @pytest.mark.parametrize("temperature", [-0.1, 2.1])
    def test_temperature_out_of_range_is_refused(self, temperature: float) -> None:
        with pytest.raises(ValidationError):
            ModelEndpointConfig(
                env_var="E",
                default_url="",
                kind="code_review",
                timeout_seconds=1.0,
                temperature=temperature,
            )

    @pytest.mark.parametrize("top_p", [0.0, 1.1])
    def test_top_p_out_of_range_is_refused(self, top_p: float) -> None:
        with pytest.raises(ValidationError):
            ModelEndpointConfig(
                env_var="E",
                default_url="",
                kind="code_review",
                timeout_seconds=1.0,
                top_p=top_p,
            )
