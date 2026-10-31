# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Model names come from the deployment overlay through settings (OMN-21678).

``ModelLlmRoutingSettings`` is the one reader of the model names the gmail intent
evaluator, the utilization scorer, the pattern compliance evaluator, the eval cost
table and the RL policy exporter address. The consumers hold no literal of any, and
a name the overlay does not supply is unset rather than a default in code.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from omniintelligence.adapters import eval_llm_client, gmail_intent_http_client
from omniintelligence.adapters.utilization_llm_client import UtilizationLLMClient
from omniintelligence.models.llm_routing import (
    DEFAULT_MODEL_NAME,
    ModelLlmRoutingSettings,
    llm_routing,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers import (
    handler_compute,
)
from omniintelligence.runtime import dispatch_handler_utilization_scoring

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[3] / "src" / "omniintelligence"

# The model families core's literal_model_name rule refuses, so one reappearing in a
# consumer fails here.
_MODEL_FAMILY = re.compile(r"(?i)^(?:[\w.@-]+/)*(?:qwen|deepseek|glm|gemini)")

_CONSUMERS = (
    "adapters/eval_llm_client.py",
    "adapters/gmail_intent_http_client.py",
    "adapters/utilization_llm_client.py",
    "nodes/node_embedding_generation_effect/models/enum_embedding_provider.py",
    "nodes/node_pattern_compliance_effect/handlers/handler_compute.py",
    "rl/export.py",
    "runtime/dispatch_handler_utilization_scoring.py",
)

_ENV = {
    "OMNIINTELLIGENCE_GMAIL_INTENT_EMBEDDING_MODEL": "embed-from-overlay",
    "OMNIINTELLIGENCE_GMAIL_INTENT_CHAT_MODEL": "chat-from-overlay",
    "OMNIINTELLIGENCE_UTILIZATION_SCORING_MODEL": "util-from-overlay",
    "OMNIINTELLIGENCE_PATTERN_COMPLIANCE_MODEL": "compliance-from-overlay",
    "OMNIINTELLIGENCE_RL_EXPORT_MODELS": '{"backend-a": "served-a"}',
    "OMNIINTELLIGENCE_EVAL_COST_RATES": '{"acme": [2.0, 3.0]}',
}


def test_the_overlay_environment_supplies_every_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in _ENV.items():
        monkeypatch.setenv(name, value)
    settings = ModelLlmRoutingSettings()
    assert settings.gmail_embed_model == "embed-from-overlay"
    assert settings.gmail_chat_model == "chat-from-overlay"
    assert settings.utilization_model == "util-from-overlay"
    assert settings.compliance_model == "compliance-from-overlay"
    assert settings.rl_export_models == {"backend-a": "served-a"}
    assert settings.eval_cost_rates == {"acme": (2.0, 3.0)}


def test_a_name_the_overlay_does_not_supply_is_the_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)
    settings = ModelLlmRoutingSettings()
    assert settings.gmail_embed_model == DEFAULT_MODEL_NAME
    assert settings.gmail_chat_model == DEFAULT_MODEL_NAME
    assert settings.utilization_model == DEFAULT_MODEL_NAME
    assert settings.compliance_model == DEFAULT_MODEL_NAME
    assert settings.rl_export_models == {}
    assert settings.eval_cost_rates == {}


def test_the_settings_are_frozen() -> None:
    settings = ModelLlmRoutingSettings()
    with pytest.raises(ValueError, match="frozen"):
        settings.__setattr__("gmail_chat_model", "other")


def test_cost_estimate_follows_the_overlay_rates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in _ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(eval_llm_client, "llm_routing", ModelLlmRoutingSettings)
    assert eval_llm_client._compute_cost_usd("ACME-1", 10, 100) == 320.0
    assert eval_llm_client._compute_cost_usd("other", 10, 100) == 0.0


def test_cost_estimate_without_rates_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OMNIINTELLIGENCE_EVAL_COST_RATES", raising=False)
    monkeypatch.setattr(eval_llm_client, "llm_routing", ModelLlmRoutingSettings)
    assert eval_llm_client._compute_cost_usd("anything", 1000, 1000) == 0.0


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "data": [{"embedding": [0.5]}],
            "choices": [{"message": {"content": "ok"}}],
        }


def _recording_client(sent: list[dict[str, object]]) -> type:
    class _Client:
        def __init__(self, **_: object) -> None:
            return None

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, _url: str, *, json: dict[str, object]) -> _Response:
            sent.append(json)
            return _Response()

    return _Client


@pytest.mark.asyncio
@pytest.mark.parametrize("supplied", [True, False])
async def test_gmail_requests_name_the_overlay_models(
    monkeypatch: pytest.MonkeyPatch, supplied: bool
) -> None:
    for name, value in _ENV.items():
        if supplied:
            monkeypatch.setenv(name, value)
        else:
            monkeypatch.delenv(name, raising=False)
    sent: list[dict[str, object]] = []
    monkeypatch.setattr(
        gmail_intent_http_client, "llm_routing", ModelLlmRoutingSettings
    )
    monkeypatch.setattr(
        gmail_intent_http_client.httpx, "AsyncClient", _recording_client(sent)
    )
    await gmail_intent_http_client.fetch_embedding("q", "http://embed.invalid")
    await gmail_intent_http_client.call_deepseek_r1("s", "u", "http://llm.invalid")
    assert sent[0]["model"] == (
        "embed-from-overlay" if supplied else DEFAULT_MODEL_NAME
    )
    assert sent[1]["model"] == ("chat-from-overlay" if supplied else DEFAULT_MODEL_NAME)


@pytest.mark.asyncio
async def test_the_utilization_client_defaults_to_the_overlay_model() -> None:
    sent: list[dict[str, object]] = []
    client = UtilizationLLMClient(base_url="http://llm.invalid")
    client._client = _recording_client(sent)()
    await client.chat_completion(messages=[])
    await client.chat_completion(messages=[], model="explicit")
    assert [body["model"] for body in sent] == [
        llm_routing().utilization_model,
        "explicit",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("supplied", [True, False])
async def test_the_utilization_dispatch_handler_asks_for_the_overlay_model(
    monkeypatch: pytest.MonkeyPatch, supplied: bool
) -> None:
    name = "OMNIINTELLIGENCE_UTILIZATION_SCORING_MODEL"
    if supplied:
        monkeypatch.setenv(name, "util-from-overlay")
    else:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        dispatch_handler_utilization_scoring, "llm_routing", ModelLlmRoutingSettings
    )
    repository = AsyncMock()
    repository.fetch.return_value = [{"id": str(uuid4()), "pattern_signature": "p"}]
    llm_client = AsyncMock()
    llm_client.chat_completion.return_value = '{"utilization_score": 0.5}'
    handler = dispatch_handler_utilization_scoring.create_utilization_scoring_dispatch_handler(
        repository=repository, publisher=AsyncMock(), llm_client=llm_client
    )
    await handler(
        {
            "session_id": str(uuid4()),
            "correlation_id": str(uuid4()),
            "session_outcome": "success",
            "injected_pattern_ids": [str(uuid4())],
        }
    )
    expected = "util-from-overlay" if supplied else DEFAULT_MODEL_NAME
    assert llm_client.chat_completion.call_args.kwargs["model"] == expected


def test_the_compliance_default_is_the_overlay_model() -> None:
    expected = llm_routing().compliance_model
    assert expected == handler_compute.DEFAULT_MODEL


@pytest.mark.parametrize("relative", _CONSUMERS)
def test_consumers_hold_no_model_family_literal(relative: str) -> None:
    tree = ast.parse((_SRC / relative).read_text(encoding="utf-8"))
    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and " " not in node.value
        and _MODEL_FAMILY.match(node.value)
    ]
    assert literals == []
