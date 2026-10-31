# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Timeouts of the utilization client, GitHub client, embed graph, introspection,
promotion scheduler and stub launcher come from a contract (OMN-21746)."""

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest

from omniintelligence.adapters.utilization_llm_client import UtilizationLLMClient
from omniintelligence.models.adapters import adapter_settings
from omniintelligence.models.runtime_timeouts import runtime_timeouts
from omniintelligence.review_bot.github.client_github import GitHubClient
from omniintelligence.runtime import (
    dispatch_handler_code_embed_graph,
    introspection,
    promotion_scheduler,
)

pytestmark = pytest.mark.unit


def _default(func: Callable[..., object], name: str) -> object:
    return inspect.signature(func).parameters[name].default


def test_defaults_are_the_contract_values() -> None:
    timeouts = runtime_timeouts()
    assert (
        _default(UtilizationLLMClient.__init__, "timeout_s")
        == adapter_settings().utilization_timeout_s
    )
    assert _default(GitHubClient.__init__, "timeout_s") == timeouts.github_request_s
    assert (
        _default(dispatch_handler_code_embed_graph._get_embedding, "timeout_s")
        == timeouts.code_embed_request_s
    )
    assert (
        _default(
            introspection.publish_intelligence_introspection,
            "heartbeat_interval_seconds",
        )
        == timeouts.introspection_heartbeat_s
    )
    assert timeouts.promotion_interval_s == promotion_scheduler.DEFAULT_INTERVAL_SECONDS


def test_github_client_uses_the_injected_timeout() -> None:
    client = GitHubClient("t", "o/r", "https://example.invalid", timeout_s=3.5)
    assert client._timeout_s == 3.5


def test_utilization_client_uses_the_injected_timeout() -> None:
    client = UtilizationLLMClient("http://example.invalid", timeout_s=4.5)
    assert client._client.timeout.read == 4.5
