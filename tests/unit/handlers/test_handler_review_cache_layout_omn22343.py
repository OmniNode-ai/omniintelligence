# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""OMN-22343: a review request is laid out stable-prefix-first with cache breakpoints.

Provider rules asserted (Anthropic prompt-caching docs): render order tools,
system, messages; at most four ``cache_control`` breakpoints; a 1h entry precedes
any 5m entry; a prefix hit reports ``cache_read_input_tokens`` greater than 0.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal

import pytest

from omniintelligence.models.review.model_cached_endpoint_config import (
    ModelCachedEndpointConfig,
)
from omniintelligence.models.review.model_review_cache_layout_request import (
    ModelReviewCacheLayoutRequest,
)
from omniintelligence.models.review.model_review_prompt_cache import (
    ModelReviewPromptCache,
)
from omniintelligence.nodes.node_review_cache_layout_compute.handlers.handler_review_cache_layout import (
    BLOCK_BOUNDARY_MARKER,
    as_messages_blocks,
    handle,
    lay_out_openai,
    policy_of,
)
from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.model_registry_loader import load_review_voters
from omniintelligence.review_pairing.models_external_review import ModelEndpointConfig

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).parent / "fixtures"
_SYSTEM = "RUBRIC AND CATALOG\n\n## Standing Rules of the Reviewed Repository\nRULE R1"
_FOCUS = "Give extra scrutiny to security."
_CREDENTIAL_ENV = "TEST_REVIEW_CREDENTIAL"


def _request(
    *,
    wire: Literal["native_blocks", "gateway_markers"] = "native_blocks",
    user: str = "Review this diff:\nDIFF OF PR A",
    **cache: Any,
) -> ModelReviewCacheLayoutRequest:
    return ModelReviewCacheLayoutRequest(
        system_prompt=_SYSTEM,
        user_prompt=user,
        review_focus=_FOCUS,
        cache=ModelReviewPromptCache(enabled=True, **cache),
        wire=wire,
    )


def _native_body(request: ModelReviewCacheLayoutRequest) -> dict[str, Any]:
    result = handle(request)
    return {
        "system": as_messages_blocks(result.system_blocks),
        "messages": [
            {"role": "user", "content": as_messages_blocks(result.user_blocks)}
        ],
    }


def _ttls(body: dict[str, Any]) -> list[str]:
    blocks = [*body["system"], *body["messages"][0]["content"]]
    return [b["cache_control"]["ttl"] for b in blocks if "cache_control" in b]


def test_native_request_matches_golden_fixture() -> None:
    golden = json.loads(
        (_FIXTURES / "omn22343_native_request_golden.json").read_text("utf-8")
    )
    assert _native_body(_request()) == golden


def test_stable_blocks_first_diff_next_focus_last_uncached() -> None:
    body = _native_body(_request())
    texts = [b["text"] for b in body["system"]] + [
        b["text"] for b in body["messages"][0]["content"]
    ]
    assert texts[0].startswith("RUBRIC")
    assert texts[1].startswith("## Standing Rules")
    assert "DIFF OF PR A" in texts[2]
    assert texts[3].startswith("## Reviewer Focus")
    assert "cache_control" not in body["messages"][0]["content"][-1]


def test_breakpoints_at_most_four_longer_ttl_first() -> None:
    ttls = _ttls(_native_body(_request()))
    assert 0 < len(ttls) <= 4
    assert ttls == sorted(ttls, key=["1h", "5m"].index)


def test_ttl_comes_from_the_policy() -> None:
    body = _native_body(_request(system_ttl="5m", diff_ttl=None))
    assert _ttls(body) == ["5m", "5m"]


def test_max_breakpoints_is_honoured_and_capped_at_four() -> None:
    assert handle(_request(max_breakpoints=1)).breakpoints == 1
    with pytest.raises(ValueError):
        ModelReviewPromptCache(max_breakpoints=5)
    with pytest.raises(ValueError, match="longer TTLs"):
        ModelReviewPromptCache(system_ttl="5m", diff_ttl="1h")


def test_gateway_wire_puts_the_marker_before_rules_and_before_focus() -> None:
    result = handle(_request(wire="gateway_markers"))
    assert (
        result.system_prompt.split(BLOCK_BOUNDARY_MARKER)[0].strip()
        == "RUBRIC AND CATALOG"
    )
    assert (
        result.system_prompt.split(BLOCK_BOUNDARY_MARKER)[1]
        .lstrip()
        .startswith("## Standing")
    )
    assert "Reviewer Focus" not in result.system_prompt
    head, tail = result.user_prompt.split(BLOCK_BOUNDARY_MARKER)
    assert "DIFF OF PR A" in head
    assert tail.strip().startswith("## Reviewer Focus")


def test_the_marker_is_the_one_the_gateway_splits_on() -> None:
    assert BLOCK_BOUNDARY_MARKER == "<<onex-cache-boundary>>"


def test_two_voters_share_the_system_blocks_and_differ_only_in_focus() -> None:
    other = _request().model_copy(
        update={"review_focus": "Give extra scrutiny to correctness."}
    )
    first, second = _native_body(_request()), _native_body(other)
    assert first["system"] == second["system"]
    assert first["messages"][0]["content"][0] == second["messages"][0]["content"][0]
    assert first["messages"][0]["content"][-1] != second["messages"][0]["content"][-1]


def test_disabled_policy_keeps_the_legacy_request() -> None:
    assert ModelReviewPromptCache().enabled is False
    plain = ModelEndpointConfig(
        env_var="X", default_url="http://h", kind="code_review", timeout_seconds=1.0
    )
    assert policy_of(plain).enabled is False
    cached = ModelCachedEndpointConfig(
        env_var="X", default_url="http://h", kind="code_review", timeout_seconds=1.0
    )
    assert cached.prompt_cache.enabled is False
    system, user = lay_out_openai(plain, "SYS", "USER")
    assert (system, user) == ("SYS", "USER")


class _Resp:
    status_code = 200

    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def json(self) -> dict[str, Any]:
        return self._body


def test_second_pass_reports_cache_read_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """The direct builder reads cache usage; a second pass reads, the first wrote."""
    recorded = json.loads(
        (_FIXTURES / "omn22343_second_pass_usage.json").read_text("utf-8")
    )
    sent: list[dict[str, Any]] = []
    replies = iter([recorded["first_pass"], recorded["second_pass"]])

    class _Client:
        def __init__(self, **_: Any) -> None: ...
        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_: Any) -> None: ...
        async def post(self, _url: str, **kwargs: Any) -> _Resp:
            sent.append(kwargs["json"])
            reply = dict(next(replies))
            reply.update(
                content=[{"type": "text", "text": "[]"}], stop_reason="end_turn"
            )
            return _Resp(reply)

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    monkeypatch.setenv(_CREDENTIAL_ENV, "placeholder-value")
    config = ModelCachedEndpointConfig(
        env_var="",
        provider="anthropic",
        api_key_env=_CREDENTIAL_ENV,
        default_url="https://api.example.invalid",
        kind="code_review",
        timeout_seconds=5.0,
        api_model_id="claude-sonnet-5-5",
        model_id_source="declared",
        review_focus=_FOCUS,
        prompt_cache=ModelReviewPromptCache(enabled=True),
    )
    first = asyncio.run(
        adapter_ai_reviewer._call_claude_api_response(_SYSTEM, "diff A", config)
    )
    second = asyncio.run(
        adapter_ai_reviewer._call_claude_api_response(_SYSTEM, "diff A", config)
    )
    assert sent[0] == sent[1]
    assert _ttls(sent[0]) == ["1h", "1h", "5m"]
    assert first.cache_read_input_tokens == 0
    assert first.cache_creation_input_tokens > 0
    assert second.cache_read_input_tokens > 0
    assert second.cache_creation_input_tokens == 0


def test_overlay_voter_policy_reaches_the_endpoint_config(tmp_path: Path) -> None:
    """The overlay, not code, declares the policy a resolved voter sends with."""
    overlay = tmp_path / "voters.yaml"
    overlay.write_text(
        "\n".join(
            [
                'schema_version: "review_voters_overlay.v1"',
                "voters:",
                "  - voter_id: gw",
                '    endpoint_url: "http://gateway.example:8140/v1/chat/completions"',
                "    model_id_source: served",
                "    required: true",
                "    timeout_seconds: 60",
                '    review_focus: "Security first."',
                "    prompt_cache:",
                "      enabled: true",
                '      system_ttl: "1h"',
                '      diff_ttl: "5m"',
                "  - voter_id: plain",
                '    endpoint_url: "http://lab.example:8000/v1/chat/completions"',
                "    model_id_source: served",
                "    required: true",
                "    timeout_seconds: 60",
            ]
        ),
        encoding="utf-8",
    )
    roster = load_review_voters(overlay)
    gateway, plain = roster.get("gw"), roster.get("plain")
    assert gateway is not None
    assert plain is not None
    assert policy_of(gateway.endpoint_config()).enabled is True
    assert policy_of(gateway.endpoint_config()).diff_ttl == "5m"
    assert policy_of(plain.endpoint_config()).enabled is False
