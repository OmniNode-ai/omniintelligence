# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The review-bot client holds no API endpoint of its own (OMN-21623).

The caller injects the base URL from the service endpoint authority; constructing
the client without one is an error rather than a fallback to a literal in code.
"""

from __future__ import annotations

import inspect

import pytest

from omniintelligence.review_bot.github.client_github import GitHubClient

pytestmark = pytest.mark.unit


def test_the_base_url_has_no_default() -> None:
    parameter = inspect.signature(GitHubClient).parameters["base_url"]
    assert parameter.default is inspect.Parameter.empty


def test_the_injected_base_url_loses_its_trailing_slash() -> None:
    client = GitHubClient("t", "owner/repo", base_url="http://injected/")
    assert client._base_url == "http://injected"
