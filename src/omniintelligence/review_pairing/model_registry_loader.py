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

import os
from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from omniintelligence.nodes.node_review_voters_overlay_compute.handlers.handler_review_voters_overlay import (
    handle as handle_review_voters_overlay,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voter_roster import (
    ModelReviewVoterRoster,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voters_overlay_request import (
    ModelReviewVotersOverlayRequest,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelEndpointConfig,
    ModelReviewQuorumPolicy,
)

_REGISTRY_PATH: Path = Path(__file__).parent / "model_registry.yaml"

OVERLAY_ROOTS_ENV = "ONEX_SKILL_OVERLAY_ROOTS"
OVERLAY_NODE = "review_pairing"


class ModelRegistryContract(BaseModel):
    """Pydantic contract for ``model_registry.yaml``.

    Attributes:
        default_model_key: Fallback model key when callers omit one.
        local_model_keys: Keys eligible for TCP reachability probing.
        api_fallback_keys: Keys used when no local model is reachable.
        review_quorum: Cross-model agreement policy (OMN-18479). Declared
            here so the blocking threshold is a contract edit rather than a
            code change or a caller flag. Its ``ge=2`` bound is what makes
            "never below two agreeing models" mechanical: a registry
            declaring 1 fails to load.
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
    review_quorum: ModelReviewQuorumPolicy = Field(
        default_factory=ModelReviewQuorumPolicy,
        description="Cross-model agreement policy for review verdicts.",
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


def _overlay_default_urls(environ: Mapping[str, str]) -> dict[str, str]:
    """Read ``default_urls`` from the first review_pairing overlay on the roots.

    Each root named in ``ONEX_SKILL_OVERLAY_ROOTS`` is searched in order for
    ``review_pairing/overlay.yaml``. No root, or no file under any root, is no
    overlay and returns an empty mapping; a file that is there and unreadable or
    malformed is refused, never skipped, because a half-read overlay would send
    a review to the wrong endpoint.
    """
    for root in environ.get(OVERLAY_ROOTS_ENV, "").split(os.pathsep):
        if not root:
            continue
        candidate = Path(root) / OVERLAY_NODE / "overlay.yaml"
        if not candidate.is_file():
            continue
        try:
            raw = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ModelRegistryLoadError(
                f"{candidate} is not a readable review_pairing overlay "
                f"({type(exc).__name__})"
            ) from None
        urls = raw.get("default_urls") if isinstance(raw, dict) else None
        if (
            not isinstance(raw, dict)
            or set(raw) != {"default_urls"}
            or not isinstance(urls, dict)
            or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in urls.items()
            )
        ):
            raise ModelRegistryLoadError(
                f"{candidate} must be a mapping holding exactly default_urls, "
                "a mapping of model key to endpoint URL"
            )
        return dict(urls)
    return {}


def resolve_endpoint_url(
    model_key: str,
    config: ModelEndpointConfig,
    environ: Mapping[str, str] | None = None,
) -> str:
    """The endpoint URL ``model_key`` resolves to, or ``""`` when none is configured.

    In order: the key's own environment variable, then the ``default_urls``
    entry of a review_pairing overlay on ``ONEX_SKILL_OVERLAY_ROOTS``, then the
    registry's ``default_url`` (empty in the shipped registry). Read at call
    time, so a changed environment is seen without a reload.
    """
    env = os.environ if environ is None else environ
    from_env = env.get(config.env_var)
    if from_env:
        return from_env
    return _overlay_default_urls(env).get(model_key) or config.default_url


def endpoint_not_configured_message(model_key: str, config: ModelEndpointConfig) -> str:
    """The refusal for a key with no resolved endpoint, naming how to supply one."""
    return (
        f"LLM endpoint not configured for '{model_key}'. Set the "
        f"{config.env_var} environment variable, or supply a {OVERLAY_NODE} "
        f"overlay whose default_urls names '{model_key}' under a root listed in "
        f"{OVERLAY_ROOTS_ENV}."
    )


def load_review_voters(path: Path) -> ModelReviewVoterRoster:
    """Read a review voters overlay and the delegation overlay it names (OMN-20910).

    The file edge of ``node_review_voters_overlay_compute``: this reads the two
    documents and the node's pure handler validates and resolves them. A
    missing or unreadable file comes back as a refused roster like any other
    refusal, so every caller fails the same way. Imports nothing heavier than
    pydantic and yaml, so the workflows' pre-install preflight can call it from
    a bare source checkout.
    """
    overlay_path = Path(path)
    if not overlay_path.is_file():
        return ModelReviewVoterRoster(
            overlay_source=str(overlay_path),
            error=f"review voters overlay not found at {overlay_path}",
        )
    overlay_yaml = overlay_path.read_text(encoding="utf-8")

    backend_yaml: str | None = None
    backend_source = ""
    try:
        raw = yaml.safe_load(overlay_yaml)
    except yaml.YAMLError:
        raw = None  # the handler reports the YAML error itself
    name = raw.get("backend_overlay") if isinstance(raw, dict) else None
    if isinstance(name, str) and name and "/" not in name and "\\" not in name:
        backend_path = overlay_path.parent / name
        backend_source = str(backend_path)
        if backend_path.is_file():
            backend_yaml = backend_path.read_text(encoding="utf-8")

    return handle_review_voters_overlay(
        ModelReviewVotersOverlayRequest(
            overlay_yaml=overlay_yaml,
            overlay_source=str(overlay_path),
            backend_overlay_yaml=backend_yaml,
            backend_overlay_source=backend_source,
        )
    )


__all__ = [
    "OVERLAY_NODE",
    "OVERLAY_ROOTS_ENV",
    "ModelRegistryContract",
    "ModelRegistryLoadError",
    "endpoint_not_configured_message",
    "load_registry",
    "load_review_voters",
    "resolve_endpoint_url",
]
