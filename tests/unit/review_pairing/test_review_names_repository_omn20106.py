# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Every voter is told which repository the reviewed diff belongs to (OMN-20106).

A cloud voter's endpoint refuses a repository whose code never goes to a cloud
model, and refuses a review that names no repository at all, so the PR review
sends the repository it was given (``--repo``) in the signed request body as
``metadata.repository``. A review with no repository sends exactly what it sent
before.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from omnibase_infra.nodes.node_llm_inference_effect.models.model_llm_inference_request import (
    ModelLlmInferenceRequest,
)

from omniintelligence.review_pairing import cli_review
from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
)

pytestmark = [pytest.mark.unit]

_REPO = "acme/widgets"


async def _request_for(**kwargs: Any) -> ModelLlmInferenceRequest:
    """Run ``call_model`` for the default lab voter and return its request."""
    env = {"LOCAL_LLM_SHARED_SECRET": "x", "LLM_QWEN3_REVIEW_URL": "http://x:1"}
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
        await adapter_ai_reviewer.call_model(
            "sys", "usr", model_key="qwen3-review", **kwargs
        )
    request: ModelLlmInferenceRequest = handler_inst.handle.call_args[0][0]
    return request


@pytest.mark.asyncio
async def test_the_request_names_the_repository_in_its_metadata() -> None:
    request = await _request_for(repository=_REPO)
    assert request.extra_body["metadata"] == {"repository": _REPO}
    assert "chat_template_kwargs" in request.extra_body


@pytest.mark.asyncio
async def test_a_review_with_no_repository_sends_no_metadata() -> None:
    request = await _request_for()
    assert "metadata" not in request.extra_body


@pytest.mark.asyncio
async def test_the_review_transaction_passes_the_repository_to_the_call() -> None:
    call = AsyncMock(return_value="[]")
    with patch.object(adapter_ai_reviewer, "call_model", call):
        await adapter_ai_reviewer.async_parse_raw(
            "diff", model="qwen3-review", review_type="pr", repository=_REPO
        )
    assert call.await_args is not None
    assert call.await_args.kwargs["repository"] == _REPO


@pytest.mark.asyncio
async def test_the_pr_review_passes_its_repository_to_every_lab_voter() -> None:
    result = ModelExternalReviewResult(
        model="qwen3-review", prompt_version="v", success=True, findings=[]
    )
    voter = AsyncMock(return_value=result)
    with patch.object(cli_review, "llm_async_parse_raw", voter):
        await cli_review.run_review(
            "diff", ["qwen3-review"], review_type="pr", repository=_REPO
        )
    assert voter.await_args is not None
    assert voter.await_args.kwargs["repository"] == _REPO
