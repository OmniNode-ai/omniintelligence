# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Lay a review prompt out so the provider can cache its stable prefix (OMN-22343).

Pure, ``handle(request) -> result``. The render order is tools, system, messages;
the stable parts come first and the per-PR diff last but for the voter's own
focus text, which differs per voter and is never cached:

    system:  rubric and catalog | standing rules      (system_ttl breakpoints)
    user:    the diff prompt    | reviewer focus      (diff_ttl breakpoint on the diff)

On a gateway wire the same split is expressed with the boundary marker the
Claude review gateway splits on; the gateway's contract decides the TTLs. On a
native wire the blocks carry ``cache_ttl`` from the voter's policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from omniintelligence.models.review.model_review_cache_block import (
    ModelReviewCacheBlock,
)
from omniintelligence.models.review.model_review_cache_layout_request import (
    ModelReviewCacheLayoutRequest,
)
from omniintelligence.models.review.model_review_cache_layout_result import (
    ModelReviewCacheLayoutResult,
)
from omniintelligence.models.review.model_review_prompt_cache import (
    ModelReviewPromptCache,
)

#: Must equal omnimarket's BLOCK_BOUNDARY_MARKER, the line the gateway splits on.
BLOCK_BOUNDARY_MARKER = "<<onex-cache-boundary>>"
_FOCUS_HEADING = "## Reviewer Focus"
_RULES_HEADING = "## Standing Rules of the Reviewed Repository"


def _split_rules(system_prompt: str) -> tuple[str, str]:
    """(instructions, standing rules) of a system prompt; rules may be empty."""
    head, sep, tail = system_prompt.partition(f"\n\n{_RULES_HEADING}")
    return head, (f"{_RULES_HEADING}{tail}" if sep else "")


def _focus(review_focus: str) -> str:
    return f"{_FOCUS_HEADING}\n\n{review_focus}" if review_focus else ""


def as_messages_blocks(
    blocks: tuple[ModelReviewCacheBlock, ...],
) -> list[dict[str, object]]:
    """Text blocks in the Messages API shape, ``cache_control`` where a TTL is set."""
    return [
        {"type": "text", "text": block.text}
        if block.cache_ttl is None
        else {
            "type": "text",
            "text": block.text,
            "cache_control": {"type": "ephemeral", "ttl": block.cache_ttl},
        }
        for block in blocks
    ]


_DISABLED = ModelReviewPromptCache()


def policy_of(config: Any) -> ModelReviewPromptCache:
    """The voter's policy; a registry entry that declares none is disabled."""
    policy = getattr(config, "prompt_cache", _DISABLED)
    return policy if isinstance(policy, ModelReviewPromptCache) else _DISABLED


def uses_system_focus(config: Any) -> bool:
    """Whether the voter's focus still rides at the end of the system prompt."""
    cached_native = policy_of(config).enabled and config.provider == "anthropic"
    return bool(config.review_focus) and not cached_native


def lay_out_openai(
    config: Any, system_prompt: str, user_prompt: str
) -> tuple[str, str]:
    """System and user text for an OpenAI-compatible call (gateway or lab endpoint).

    Disabled policy: the focus is appended to the system prompt, as it always was.
    """
    policy = policy_of(config)
    if not policy.enabled:
        if config.review_focus:
            system_prompt = f"{system_prompt}\n\n{_focus(config.review_focus)}"
        return system_prompt, user_prompt
    laid_out = handle(
        ModelReviewCacheLayoutRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            review_focus=config.review_focus,
            cache=policy,
            wire="gateway_markers",
        )
    )
    return laid_out.system_prompt, laid_out.user_prompt


def anthropic_payload(
    config: Any, system_prompt: str, user_prompt: str, max_tokens: int
) -> dict[str, Any]:
    """The ``/v1/messages`` body of a direct Claude voter call."""
    payload: dict[str, Any] = {
        "model": config.api_model_id,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    policy = policy_of(config)
    if policy.enabled:
        laid_out = handle(
            ModelReviewCacheLayoutRequest(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                review_focus=config.review_focus,
                cache=policy,
                wire="native_blocks",
            )
        )
        payload["system"] = as_messages_blocks(laid_out.system_blocks)
        payload["messages"] = [
            {"role": "user", "content": as_messages_blocks(laid_out.user_blocks)}
        ]
    for name in ("temperature", "top_p"):
        if getattr(config, name) is not None:
            payload[name] = getattr(config, name)
    return payload


def anthropic_usage(usage: Mapping[str, Any]) -> tuple[int, int, int, int]:
    """(input, output, cache written, cache read) tokens of a Messages reply.

    ``input_tokens`` is the uncached remainder once a prefix is cached; the
    returned input is the whole prompt (remainder + written + read).

    Raises:
        ValueError: A count is missing, not an integer, or negative.
    """
    counts = (
        usage["input_tokens"],
        usage["output_tokens"],
        usage.get("cache_creation_input_tokens", 0),
        usage.get("cache_read_input_tokens", 0),
    )
    if any(type(n) is not int or n < 0 for n in counts):
        raise ValueError("invalid usage")
    return counts[0] + counts[2] + counts[3], counts[1], counts[2], counts[3]


def handle(request: ModelReviewCacheLayoutRequest) -> ModelReviewCacheLayoutResult:
    """Return the request's prompt laid out stable-first for the prompt cache."""
    instructions, rules = _split_rules(request.system_prompt)
    focus = _focus(request.review_focus)
    if request.wire == "gateway_markers":
        system = (
            f"{instructions}\n\n{BLOCK_BOUNDARY_MARKER}\n\n{rules}"
            if rules
            else instructions
        )
        user = (
            f"{request.user_prompt}\n\n{BLOCK_BOUNDARY_MARKER}\n\n{focus}"
            if focus
            else request.user_prompt
        )
        return ModelReviewCacheLayoutResult(system_prompt=system, user_prompt=user)

    cache = request.cache
    system_parts = [part for part in (instructions, rules) if part]
    diff_slot = 1 if cache.diff_ttl is not None and focus else 0
    keep = max(1, min(len(system_parts), cache.max_breakpoints - diff_slot))
    if len(system_parts) > keep:
        system_parts = [
            *system_parts[: keep - 1],
            "\n\n".join(system_parts[keep - 1 :]),
        ]
    system_blocks = tuple(
        ModelReviewCacheBlock(text=part, cache_ttl=cache.system_ttl)
        for part in system_parts
    )
    marked = len(system_blocks) if cache.system_ttl is not None else 0
    diff_ttl = (
        cache.diff_ttl if diff_slot and marked + 1 <= cache.max_breakpoints else None
    )
    user_blocks = (ModelReviewCacheBlock(text=request.user_prompt, cache_ttl=diff_ttl),)
    if focus:
        user_blocks = (*user_blocks, ModelReviewCacheBlock(text=focus))
    return ModelReviewCacheLayoutResult(
        system_blocks=system_blocks,
        user_blocks=user_blocks,
        breakpoints=marked + (1 if diff_ttl is not None else 0),
    )


__all__ = [
    "BLOCK_BOUNDARY_MARKER",
    "anthropic_payload",
    "anthropic_usage",
    "as_messages_blocks",
    "handle",
    "lay_out_openai",
    "policy_of",
    "uses_system_focus",
]
