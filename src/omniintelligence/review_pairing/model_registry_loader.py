# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Contract-driven loader for the hostile-reviewer model registry.

Replaces the previously hardcoded ``MODEL_REGISTRY`` dict in
``adapter_ai_reviewer`` with a YAML-backed definition. The YAML is
validated via Pydantic at module import time so malformed contracts
fail fast with a clear error rather than surfacing as a KeyError
mid-review.

Reference: OMN-7213
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from omniintelligence.review_pairing.models_external_review import (
    ModelEndpointConfig,
)

_REGISTRY_PATH: Path = Path(__file__).parent / "model_registry.yaml"


class ModelRegistryContract(BaseModel):
    """Pydantic contract for ``model_registry.yaml``.

    Attributes:
        default_model_key: Fallback model key when callers omit one.
        local_model_keys: Keys eligible for TCP reachability probing.
        api_fallback_keys: Keys used when no local model is reachable.
        models: Mapping of model key to endpoint config. Must contain
            every key referenced by the three lists above.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    default_model_key: str = Field(description="Fallback model key for reviews.")
    local_model_keys: tuple[str, ...] = Field(
        description="Model keys that resolve to a local TCP endpoint."
    )
    api_fallback_keys: tuple[str, ...] = Field(
        description="Model keys used when local endpoints are unreachable."
    )
    models: dict[str, ModelEndpointConfig] = Field(
        description="Model key -> endpoint config."
    )


class ModelRegistryLoadError(RuntimeError):
    """Raised when ``model_registry.yaml`` is missing, malformed, or inconsistent."""


def _validate_cross_refs(contract: ModelRegistryContract) -> None:
    """Ensure every referenced key exists in ``models``."""
    missing: list[str] = []
    for key in (
        contract.default_model_key,
        *contract.local_model_keys,
        *contract.api_fallback_keys,
    ):
        if key not in contract.models:
            missing.append(key)
    if missing:
        raise ModelRegistryLoadError(
            f"model_registry.yaml references undefined model keys: {sorted(set(missing))}"
        )


def load_registry(path: Path | None = None) -> ModelRegistryContract:
    """Load and validate the model-registry contract from disk.

    Args:
        path: Optional override for the YAML path (tests only).

    Returns:
        A validated ``ModelRegistryContract``.

    Raises:
        ModelRegistryLoadError: If the file is missing, not a mapping,
            fails Pydantic validation, or references keys not present in
            the ``models`` mapping.
    """
    registry_path = path or _REGISTRY_PATH
    if not registry_path.is_file():
        raise ModelRegistryLoadError(
            f"model_registry.yaml not found at {registry_path}"
        )

    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ModelRegistryLoadError(
            f"model_registry.yaml is not valid YAML: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise ModelRegistryLoadError(
            f"model_registry.yaml must be a mapping, got {type(raw).__name__}"
        )

    try:
        contract = ModelRegistryContract.model_validate(raw)
    except ValidationError as exc:
        raise ModelRegistryLoadError(
            f"model_registry.yaml failed validation: {exc}"
        ) from exc

    _validate_cross_refs(contract)
    return contract


__all__ = [
    "ModelRegistryContract",
    "ModelRegistryLoadError",
    "load_registry",
]
