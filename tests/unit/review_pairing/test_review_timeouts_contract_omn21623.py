# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Review-pipeline time budgets and the codex search dirs come from a contract (OMN-21623).

``review_pairing/review_budgets.yaml`` declares them; ``ModelReviewBudgets`` is the one
reader. The code holds no literal for either: each module constant is read from the
contract, and a file that omits a field, or names an unknown one, fails to load rather
than falling back to a value in code.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from omniintelligence.models.review.model_review_budgets import (
    ModelReviewBudgets,
    ModelReviewBudgetsLoadError,
    shipped_review_budgets,
)
from omniintelligence.review_pairing import served_model_resolver
from omniintelligence.review_pairing.adapters import (
    adapter_ai_reviewer,
    adapter_codex_reviewer,
)

pytestmark = pytest.mark.unit

_FLOAT_FIELDS = (
    "model_probe_seconds",
    "tcp_probe_seconds",
    "tcp_retry_delay_seconds",
    "codex_exec_seconds",
    "git_show_seconds",
    "gh_api_seconds",
    "gh_pr_diff_seconds",
)
_ALL_FIELDS = (*_FLOAT_FIELDS, "codex_fallback_dirs")


def _body(skip: str | None = None) -> str:
    lines = [f"{name}: 1.0" for name in _FLOAT_FIELDS if name != skip]
    if skip != "codex_fallback_dirs":
        lines.append('codex_fallback_dirs: ["/usr/local/bin", "~/bin"]')
    return "\n".join(lines) + "\n"


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "budgets.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_shipped_budgets_are_positive_and_name_a_search_path() -> None:
    budgets = shipped_review_budgets()
    for name in _FLOAT_FIELDS:
        assert getattr(budgets, name) > 0, name
    assert budgets.codex_fallback_dirs


@pytest.mark.parametrize("missing", _ALL_FIELDS)
def test_a_file_missing_one_field_fails_to_load(tmp_path: Path, missing: str) -> None:
    with pytest.raises(ModelReviewBudgetsLoadError, match=missing):
        ModelReviewBudgets.load(_write(tmp_path, _body(skip=missing)))


def test_a_file_with_an_unknown_field_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelReviewBudgetsLoadError, match="surprise"):
        ModelReviewBudgets.load(_write(tmp_path, _body() + "surprise: 1.0\n"))


def test_a_missing_file_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(ModelReviewBudgetsLoadError, match="not found"):
        ModelReviewBudgets.load(tmp_path / "absent.yaml")


def test_a_non_positive_budget_fails_to_load(tmp_path: Path) -> None:
    body = _body().replace("gh_api_seconds: 1.0", "gh_api_seconds: 0")
    with pytest.raises(ModelReviewBudgetsLoadError, match="gh_api_seconds"):
        ModelReviewBudgets.load(_write(tmp_path, body))


def test_a_complete_file_loads_and_expands_the_home_directory(tmp_path: Path) -> None:
    budgets = ModelReviewBudgets.load(_write(tmp_path, _body()))
    assert budgets.gh_api_seconds == 1.0
    assert budgets.codex_fallback_dirs[0] == "/usr/local/bin"
    assert budgets.codex_fallback_dirs[1] == str(Path("~/bin").expanduser())


def test_modules_read_their_budgets_from_the_contract() -> None:
    budgets = shipped_review_budgets()
    assert budgets.tcp_probe_seconds == adapter_ai_reviewer._PROBE_TIMEOUT_SECONDS
    assert (
        budgets.tcp_retry_delay_seconds
        == adapter_ai_reviewer._PROBE_RETRY_DELAY_SECONDS
    )
    assert budgets.codex_exec_seconds == adapter_codex_reviewer._CODEX_TIMEOUT_SECONDS
    assert budgets.codex_fallback_dirs == adapter_codex_reviewer._CODEX_FALLBACK_DIRS
    probe = inspect.signature(served_model_resolver.resolve_served_model_id)
    assert probe.parameters["timeout_seconds"].default == budgets.model_probe_seconds
