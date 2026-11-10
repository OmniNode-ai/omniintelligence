# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Loads the ``review_agent_receipt_verify`` overlay: policy, quorum size and bus binding (OMN-22175).

This is the I/O edge of the verifier node, kept out of the node package (node purity):
it reads the packaged overlay, the contract and the deployment overlay, and hands the
values to a caller, which injects them into each verify request.

The packaged ``overlay.yaml`` carries the defaults. A deployment replaces any of its
keys in ``<root>/review_agent_receipt_verify/overlay.yaml``, found under the first root
of ``ONEX_SKILL_OVERLAY_ROOTS`` (an ``os.pathsep`` separated list) that holds one. An
overlay that is present and unreadable, not a mapping, or invalid is refused: a broken
overlay must never read as an absent one, because a half-read policy would accept what
it should refuse.

The topics are the contract's, under ``options.review_agent_receipt_verify.topics``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from omniintelligence.nodes.node_review_agent_receipt_verify_compute.models import (
    EnumAgentReceiptVerifyTransport,
    ModelAgentReceiptPolicy,
    ModelAgentReceiptVerifierSettings,
    ModelAgentReceiptVerifierTopics,
)

OVERLAY_ID = "review_agent_receipt_verify"
OVERLAY_ROOTS_ENV = "ONEX_SKILL_OVERLAY_ROOTS"
_PACKAGE = "omniintelligence.nodes.node_review_agent_receipt_verify_compute"


class NodeOverlayError(ValueError):
    """The overlay or the contract is unreadable or invalid."""


class _ModelOverlay(BaseModel):
    """``<root>/review_agent_receipt_verify/overlay.yaml``; every key is optional."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    transport: EnumAgentReceiptVerifyTransport | None = None
    quorum_size: int | None = None
    policy: ModelAgentReceiptPolicy | None = None


def _read_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise NodeOverlayError(
            f"{path} is not readable ({type(exc).__name__})"
        ) from None
    if not isinstance(raw, dict):
        raise NodeOverlayError(f"{path} must be a mapping")
    return raw


def load_contract() -> dict[str, Any]:
    """The packaged contract as a mapping."""
    return _read_mapping(Path(str(files(_PACKAGE).joinpath("contract.yaml"))))


def find_deployment_overlay(environ: Mapping[str, str] | None = None) -> Path | None:
    """The first deployment overlay on the roots, or None."""
    env = os.environ if environ is None else environ
    for root in env.get(OVERLAY_ROOTS_ENV, "").split(os.pathsep):
        if not root:
            continue
        candidate = Path(root) / OVERLAY_ID / "overlay.yaml"
        if candidate.is_file():
            return candidate
    return None


def load_verifier_settings(
    environ: Mapping[str, str] | None = None,
) -> ModelAgentReceiptVerifierSettings:
    """The packaged defaults with the deployment overlay's keys laid over them."""
    fields = _read_mapping(Path(str(files(_PACKAGE).joinpath("overlay.yaml"))))
    deployment = find_deployment_overlay(environ)
    if deployment is not None:
        try:
            overlay = _ModelOverlay.model_validate(_read_mapping(deployment))
        except ValidationError as exc:
            raise NodeOverlayError(
                f"{deployment} is not a valid {OVERLAY_ID} overlay: "
                f"{exc.error_count()} error(s)"
            ) from None
        fields.update(overlay.model_dump(exclude_none=True))
    try:
        return ModelAgentReceiptVerifierSettings.model_validate(fields)
    except ValidationError as exc:
        source = deployment if deployment is not None else "the packaged overlay"
        raise NodeOverlayError(
            f"{source} yields invalid settings: {exc.error_count()} error(s)"
        ) from None


def load_topics() -> ModelAgentReceiptVerifierTopics:
    """The command topic and the decided topic, as the contract declares them."""
    topics = load_contract()["options"][OVERLAY_ID]["topics"]
    return ModelAgentReceiptVerifierTopics(
        command=topics["command"], decided=topics["decided"]
    )


class ModelAgentReceiptSettingsRequest(BaseModel):
    """Which environment to read the overlay roots from; None reads the process's."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    environ: dict[str, str] | None = None


def handle(
    request: ModelAgentReceiptSettingsRequest,
) -> ModelAgentReceiptVerifierSettings:
    """The contract's routed entry point for ``resolve_verifier_settings``."""
    return load_verifier_settings(request.environ)


class HandlerReviewAgentReceiptOverlay:
    """Contract-bound handler for ``handle``."""

    def __init__(self, **dependencies: Any) -> None:
        self._dependencies = dependencies

    def handle(
        self, request: ModelAgentReceiptSettingsRequest
    ) -> ModelAgentReceiptVerifierSettings:
        return handle(request, **self._dependencies)


__all__ = [
    "OVERLAY_ID",
    "ModelAgentReceiptSettingsRequest",
    "NodeOverlayError",
    "HandlerReviewAgentReceiptOverlay",
    "find_deployment_overlay",
    "load_contract",
    "load_topics",
    "handle",
    "load_verifier_settings",
]
