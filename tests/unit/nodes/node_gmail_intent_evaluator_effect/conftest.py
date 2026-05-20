# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Fixtures for node_gmail_intent_evaluator_effect unit tests."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _stub_llm_embedding_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a stub LLM_EMBEDDING_URL so tests don't fail on missing env var.

    The handler resolves this before calling _query_omnimemory; tests mock
    _query_omnimemory itself, so the URL value is never used.
    """
    if "LLM_EMBEDDING_URL" not in os.environ:
        monkeypatch.setenv("LLM_EMBEDDING_URL", "http://stub-embedding:8100")
