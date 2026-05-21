# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Fixtures for node_gmail_intent_evaluator_effect unit tests."""

from __future__ import annotations

import os

import pytest

_STUB_ENV_VARS = {
    "LLM_EMBEDDING_URL": "http://stub-embedding:8100",
    "LLM_DEEPSEEK_R1_URL": "http://stub-deepseek:8001",
    "QDRANT_URL": "http://stub-qdrant:6333",
}


@pytest.fixture(autouse=True)
def _stub_external_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub external service env vars so tests don't fail when vars are absent.

    The handler resolves these before calling mocked helper functions, so the
    stub values are never actually used in unit tests.
    """
    for key, value in _STUB_ENV_VARS.items():
        if key not in os.environ:
            monkeypatch.setenv(key, value)
