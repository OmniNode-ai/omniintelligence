# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Time budgets and the codex search path of the review pipeline (OMN-21623).

The values live in ``review_pairing/review_budgets.yaml``; this model validates
that contract and is the one way code reads it. Every field is required, so a
file that omits one fails to load instead of falling back to a number in code.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_BUDGETS_PATH: Path = (
    Path(__file__).resolve().parents[2] / "review_pairing" / "review_budgets.yaml"
)


class ModelReviewBudgetsLoadError(RuntimeError):
    """Raised when ``review_budgets.yaml`` is missing, malformed or incomplete."""


class ModelReviewBudgets(BaseModel):
    """The review pipeline's time budgets and codex search directories.

    Attributes:
        model_probe_seconds: Budget of the ``/v1/models`` served-model probe.
        tcp_probe_seconds: Budget of one TCP reachability attempt.
        tcp_retry_delay_seconds: Delay between reachability attempts.
        codex_exec_seconds: Budget of one ``codex exec`` subprocess.
        git_show_seconds: Budget of one ``git show`` read.
        gh_api_seconds: Budget of one paginated ``gh api`` read.
        gh_pr_diff_seconds: Budget of one ``gh pr diff`` read.
        codemod_sandbox_seconds: Budget of one codemod replay run.
        codex_fallback_dirs: Directories searched for the codex binary when it
            is not on PATH, with a leading ``~`` expanded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    model_probe_seconds: float = Field(gt=0)
    tcp_probe_seconds: float = Field(gt=0)
    tcp_retry_delay_seconds: float = Field(gt=0)
    codex_exec_seconds: float = Field(gt=0)
    git_show_seconds: float = Field(gt=0)
    gh_api_seconds: float = Field(gt=0)
    gh_pr_diff_seconds: float = Field(gt=0)
    codemod_sandbox_seconds: float = Field(gt=0)
    codex_fallback_dirs: tuple[str, ...]

    @field_validator("codex_fallback_dirs")
    @classmethod
    def _expand_home(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(os.path.expanduser(directory) for directory in value)

    @classmethod
    def load(cls, path: Path | None = None) -> ModelReviewBudgets:
        """Read and validate the budgets contract.

        Args:
            path: Optional override for the YAML path (tests only).

        Raises:
            ModelReviewBudgetsLoadError: If the file is missing, not a mapping,
                or fails validation.
        """
        source = path or _BUDGETS_PATH
        if not source.is_file():
            raise ModelReviewBudgetsLoadError(
                f"review_budgets.yaml not found at {source}"
            )
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
            return cls.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as exc:
            raise ModelReviewBudgetsLoadError(
                f"review_budgets.yaml failed to load: {exc}"
            ) from exc


@cache
def shipped_review_budgets() -> ModelReviewBudgets:
    """The shipped ``review_budgets.yaml``, loaded once per process."""
    return ModelReviewBudgets.load()


__all__ = [
    "ModelReviewBudgets",
    "ModelReviewBudgetsLoadError",
    "shipped_review_budgets",
]
