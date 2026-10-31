# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Timeout and poll budgets of the runtime and its callers (OMN-21623).

The values live in ``runtime/runtime_timeouts.yaml``; this model validates that
contract and is the one way code reads it. Every field is required and unknown
fields are refused, so a file that omits or misspells one fails to load instead
of falling back to a value in code.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_TIMEOUTS_PATH: Path = (
    Path(__file__).resolve().parents[2] / "runtime" / "runtime_timeouts.yaml"
)


class ModelRuntimeTimeoutsLoadError(RuntimeError):
    """Raised when ``runtime_timeouts.yaml`` is missing, malformed or incomplete."""


class ModelRuntimeTimeouts(BaseModel):
    """The runtime's timeout and poll budgets, in seconds.

    Attributes:
        qdrant_request_s: Code projection Qdrant client request timeout.
        embedding_request_s: Code projection embedding client request timeout.
        projection_pg_command_s: Code projection asyncpg command timeout.
        navigation_retrieve_s: Navigation retrieval wait default.
        pattern_assembly_workflow_s: Pattern assembly workflow timeout default.
        regex_match_s: Pattern matching regex execution budget.
        watchdog_poll_s: Watchdog fallback observer polling interval.
        session_query_s: Session enrichment DB query budget.
        contract_linter_watch_poll_s: Contract linter ``--watch`` poll interval.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    qdrant_request_s: float = Field(gt=0)
    embedding_request_s: float = Field(gt=0)
    projection_pg_command_s: float = Field(gt=0)
    navigation_retrieve_s: float = Field(gt=0)
    pattern_assembly_workflow_s: float = Field(gt=0)
    regex_match_s: float = Field(gt=0)
    watchdog_poll_s: float = Field(gt=0)
    session_query_s: float = Field(gt=0)
    contract_linter_watch_poll_s: float = Field(gt=0)

    @classmethod
    def load(cls, path: Path | None = None) -> ModelRuntimeTimeouts:
        """Read and validate the runtime timeouts contract.

        Args:
            path: Optional override for the YAML path (tests only).

        Raises:
            ModelRuntimeTimeoutsLoadError: If the file is missing, not a mapping,
                or fails validation.
        """
        source = path or _TIMEOUTS_PATH
        if not source.is_file():
            raise ModelRuntimeTimeoutsLoadError(
                f"runtime_timeouts.yaml not found at {source}"
            )
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
            return cls.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as exc:
            raise ModelRuntimeTimeoutsLoadError(
                f"runtime_timeouts.yaml failed to load: {exc}"
            ) from exc


@cache
def runtime_timeouts() -> ModelRuntimeTimeouts:
    """The shipped ``runtime_timeouts.yaml``, loaded once per process."""
    return ModelRuntimeTimeouts.load()


__all__ = [
    "ModelRuntimeTimeouts",
    "ModelRuntimeTimeoutsLoadError",
    "runtime_timeouts",
]
