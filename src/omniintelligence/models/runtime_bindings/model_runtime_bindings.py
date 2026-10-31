# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Bind address and listener ports of the runtime's HTTP endpoints (OMN-21680).

The values live in ``runtime/runtime_bindings.yaml``; this model validates that
contract and is the one way code reads it. Every field is required and unknown
fields are refused, so a file that omits or misspells one fails to load instead
of falling back to a value in code.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_BINDINGS_PATH: Path = (
    Path(__file__).resolve().parents[2] / "runtime" / "runtime_bindings.yaml"
)


class ModelRuntimeBindingsLoadError(RuntimeError):
    """Raised when ``runtime_bindings.yaml`` is missing, malformed or incomplete."""


class ModelRuntimeBindings(BaseModel):
    """The interface and ports the runtime's health and metrics listeners bind.

    Attributes:
        bind_host: Interface every health listener binds.
        runtime_health_port: ``ModelIntelligenceRuntimeConfig`` health check port.
        runtime_metrics_port: ``ModelIntelligenceRuntimeConfig`` metrics port.
        stub_health_port: ``stub_launcher`` health check port.
        decision_store_health_port: ``decision_store`` entrypoint health check port.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    bind_host: str = Field(min_length=1)
    runtime_health_port: int = Field(ge=1, le=65535)
    runtime_metrics_port: int = Field(ge=1, le=65535)
    stub_health_port: int = Field(ge=1, le=65535)
    decision_store_health_port: int = Field(ge=1, le=65535)

    @classmethod
    def load(cls, path: Path | None = None) -> ModelRuntimeBindings:
        """Read and validate the runtime bindings contract.

        Args:
            path: Optional override for the YAML path (tests only).

        Raises:
            ModelRuntimeBindingsLoadError: If the file is missing, not a mapping,
                or fails validation.
        """
        source = path or _BINDINGS_PATH
        if not source.is_file():
            raise ModelRuntimeBindingsLoadError(
                f"runtime_bindings.yaml not found at {source}"
            )
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
            return cls.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as exc:
            raise ModelRuntimeBindingsLoadError(
                f"runtime_bindings.yaml failed to load: {exc}"
            ) from exc


@cache
def runtime_bindings() -> ModelRuntimeBindings:
    """The shipped ``runtime_bindings.yaml``, loaded once per process."""
    return ModelRuntimeBindings.load()


__all__ = [
    "ModelRuntimeBindings",
    "ModelRuntimeBindingsLoadError",
    "runtime_bindings",
]
