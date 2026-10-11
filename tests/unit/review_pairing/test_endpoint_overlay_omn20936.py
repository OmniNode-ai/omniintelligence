# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The review registry resolves an endpoint from env, then an overlay, else refuses (OMN-20936).

The shipped registry carries no endpoint. A deployment supplies one through the
key's environment variable or through a ``review_pairing`` overlay found under
``ONEX_SKILL_OVERLAY_ROOTS``; with neither, the key refuses naming both.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    MODEL_REGISTRY,
    _resolve_model_url,
    probe_local_reachability,
)
from omniintelligence.review_pairing.model_registry_loader import (
    ModelRegistryLoadError,
    endpoint_not_configured_message,
    resolve_endpoint_url,
)
from omniintelligence.review_pairing.reviewer_identity import reviewer_identity

pytestmark = pytest.mark.unit

_KEY = "qwen3-review"
_OVERLAY_URL = "http://192.0.2.21:8000"
_ENV_URL = "http://192.0.2.22:8000"


def _write_overlay(root: Path, body: str) -> None:
    directory = root / "review_pairing"
    directory.mkdir(parents=True)
    (directory / "overlay.yaml").write_text(body, encoding="utf-8")


@pytest.fixture
def overlay_root(tmp_path: Path) -> Path:
    _write_overlay(tmp_path, f'default_urls:\n  {_KEY}: "{_OVERLAY_URL}"\n')
    return tmp_path


def test_with_the_overlay_root_the_key_resolves_the_overlay_url(
    monkeypatch: pytest.MonkeyPatch, overlay_root: Path
) -> None:
    monkeypatch.delenv("LLM_QWEN3_REVIEW_URL", raising=False)
    monkeypatch.setenv("ONEX_SKILL_OVERLAY_ROOTS", str(overlay_root))
    assert _resolve_model_url(_KEY) == _OVERLAY_URL
    assert (
        reviewer_identity(
            _KEY, MODEL_REGISTRY[_KEY], {"ONEX_SKILL_OVERLAY_ROOTS": str(overlay_root)}
        )
        == "http://192.0.2.21:8000#served"
    )


def test_without_the_overlay_root_the_key_refuses_naming_how_to_supply_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LLM_QWEN3_REVIEW_URL", raising=False)
    monkeypatch.delenv("ONEX_SKILL_OVERLAY_ROOTS", raising=False)
    with pytest.raises(ValueError) as refusal:
        _resolve_model_url(_KEY)
    message = str(refusal.value)
    assert "LLM_QWEN3_REVIEW_URL" in message
    assert "ONEX_SKILL_OVERLAY_ROOTS" in message
    assert message == endpoint_not_configured_message(_KEY, MODEL_REGISTRY[_KEY])


def test_a_root_without_the_overlay_file_is_no_overlay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("LLM_QWEN3_REVIEW_URL", raising=False)
    monkeypatch.setenv("ONEX_SKILL_OVERLAY_ROOTS", str(tmp_path))
    with pytest.raises(ValueError, match="LLM_QWEN3_REVIEW_URL"):
        _resolve_model_url(_KEY)


def test_the_environment_variable_wins_over_the_overlay(
    monkeypatch: pytest.MonkeyPatch, overlay_root: Path
) -> None:
    monkeypatch.setenv("LLM_QWEN3_REVIEW_URL", _ENV_URL)
    monkeypatch.setenv("ONEX_SKILL_OVERLAY_ROOTS", str(overlay_root))
    assert _resolve_model_url(_KEY) == _ENV_URL


def test_the_first_root_that_holds_the_overlay_wins(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    first = tmp_path / "first"
    second = tmp_path / "second"
    empty.mkdir()
    _write_overlay(first, f'default_urls:\n  {_KEY}: "{_OVERLAY_URL}"\n')
    _write_overlay(second, f'default_urls:\n  {_KEY}: "{_ENV_URL}"\n')
    roots = os.pathsep.join(str(path) for path in (empty, first, second))
    assert (
        resolve_endpoint_url(
            _KEY, MODEL_REGISTRY[_KEY], {"ONEX_SKILL_OVERLAY_ROOTS": roots}
        )
        == _OVERLAY_URL
    )


def test_a_key_the_overlay_does_not_name_stays_unconfigured(
    monkeypatch: pytest.MonkeyPatch, overlay_root: Path
) -> None:
    monkeypatch.delenv("LLM_LOCAL_STUDIO_PLANNER_URL", raising=False)
    monkeypatch.setenv("ONEX_SKILL_OVERLAY_ROOTS", str(overlay_root))
    with pytest.raises(ValueError, match="LLM_LOCAL_STUDIO_PLANNER_URL"):
        _resolve_model_url("local-studio-planner")
    assert probe_local_reachability(["local-studio-planner"]) == {
        "local-studio-planner": False
    }


@pytest.mark.parametrize(
    "body",
    [
        "default_urls: [not, a, mapping]\n",
        "default_urls:\n  qwen3-review: 8000\n",
        'other: "x"\ndefault_urls: {}\n',
        "- just\n- a list\n",
        "default_urls: {unterminated\n",
    ],
)
def test_a_malformed_overlay_is_refused_not_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: str
) -> None:
    monkeypatch.delenv("LLM_QWEN3_REVIEW_URL", raising=False)
    _write_overlay(tmp_path, body)
    monkeypatch.setenv("ONEX_SKILL_OVERLAY_ROOTS", str(tmp_path))
    with pytest.raises(ModelRegistryLoadError, match="overlay"):
        _resolve_model_url(_KEY)
