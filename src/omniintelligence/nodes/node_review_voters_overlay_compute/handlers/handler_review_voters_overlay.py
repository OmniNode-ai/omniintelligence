# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Resolve the Hostile Reviewer's voters from a contract overlay (OMN-20910).

Operator RULING 2026-10-10T18:17:37Z: "Changing the model for reviews should
be a contract overlay. We should be able to create a new parameter and pointed
directly at a different model so we don't get stuck in issues like this."

Before this node, the gate's second voter was a registry key plus an Actions
variable per repository plus a URL written into three workflow files. Retiring
one endpoint took a workflow pull request, variable edits on three
repositories and a branch update on every open pull request. The roster now
lives in ONE overlay file and the workflows pass nothing but its path:

* each voter names its endpoint by ``backend_id`` -- a backend of the lab's
  delegation overlay (``bifrost_lane_overlay.v3``), which already carries the
  lab's endpoint facts -- or by an explicit ``endpoint_url``;
* each voter carries its model selection (``served`` or a ``declared`` id),
  sampling (``temperature``, ``top_p``), focus prompt, timeout, retries and
  whether it is ``required``.

``handle`` is the pure compute: text in, a resolved roster or a refusal out.
A refusal names the voter it is about. Reading the two files is the caller's
edge (``model_registry_loader.load_review_voters``); this module does no I/O. The quorum policy is not part of the overlay: it stays in
``model_registry.yaml`` (``review_quorum``, bounded at >= 2), so an overlay can
change who votes and never how many must agree.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

import yaml
from pydantic import ValidationError

from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_bifrost_backend_view import (
    BIFROST_LANE_OVERLAY_SCHEMA_VERSION,
    ModelBifrostBackendView,
    ModelBifrostOverlayView,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_resolved_review_voter import (
    ModelResolvedReviewVoter,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voter_roster import (
    ModelReviewVoterRoster,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voters_overlay import (
    ModelReviewVotersOverlay,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voters_overlay_request import (
    ModelReviewVotersOverlayRequest,
)

_API_PATH_SUFFIXES: tuple[str, ...] = ("/v1/chat/completions", "/chat/completions")
_SCHEMES: frozenset[str] = frozenset({"http", "https"})


class _RefusalError(Exception):
    """Internal control flow only; ``handle`` turns it into roster data."""

    def __init__(self, message: str, voter_id: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.voter_id = voter_id


def _parse_mapping(text: str, what: str) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise _RefusalError(f"{what} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise _RefusalError(f"{what} must be a mapping, got {type(raw).__name__}")
    return raw


def _voter_id_at(loc: tuple[int | str, ...], raw: dict[str, Any]) -> str:
    """The voter a pydantic error location points into, when it points into one."""
    if len(loc) < 2 or loc[0] != "voters" or not isinstance(loc[1], int):
        return ""
    voters = raw.get("voters")
    index = loc[1]
    if not isinstance(voters, list) or index >= len(voters):
        return ""
    entry = voters[index]
    if isinstance(entry, dict) and isinstance(entry.get("voter_id"), str):
        return str(entry["voter_id"])
    return f"#{index}"


def _validate(raw: dict[str, Any], source: str) -> ModelReviewVotersOverlay:
    try:
        return ModelReviewVotersOverlay.model_validate(raw)
    except ValidationError as exc:
        errors = exc.errors()
        detail = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in errors
        )
        raise _RefusalError(
            f"overlay {source} failed validation: {detail}",
            _voter_id_at(tuple(errors[0]["loc"]), raw),
        ) from exc


def _backends(
    request: ModelReviewVotersOverlayRequest,
) -> dict[str, ModelBifrostBackendView]:
    source = request.backend_overlay_source
    if request.backend_overlay_yaml is None:
        raise _RefusalError(f"backend overlay {source} not found")
    raw = _parse_mapping(request.backend_overlay_yaml, f"backend overlay {source}")
    try:
        view = ModelBifrostOverlayView.model_validate(raw)
    except ValidationError as exc:
        raise _RefusalError(
            f"backend overlay {source} failed validation: {exc}"
        ) from exc
    if view.schema_version != BIFROST_LANE_OVERLAY_SCHEMA_VERSION:
        raise _RefusalError(
            f"backend overlay {source} has schema_version {view.schema_version!r}, "
            f"expected {BIFROST_LANE_OVERLAY_SCHEMA_VERSION!r}"
        )
    return {backend.backend_id: backend for backend in view.backends}


def _base_url(url: str, voter_id: str, what: str) -> str:
    """Normalise an endpoint to ``scheme://host[:port][/prefix]``, refusing junk."""
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in _SCHEMES or not parsed.hostname:
        raise _RefusalError(
            f"{what} {url!r} is not an http(s) URL with a host", voter_id
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise _RefusalError(f"{what} {url!r} has an invalid port", voter_id) from exc
    path = parsed.path.rstrip("/")
    for suffix in _API_PATH_SUFFIXES:
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    netloc = parsed.hostname if port is None else f"{parsed.hostname}:{port}"
    return f"{parsed.scheme}://{netloc}{path.rstrip('/')}"


def _resolve(
    request: ModelReviewVotersOverlayRequest,
) -> tuple[ModelResolvedReviewVoter, ...]:
    source = request.overlay_source
    overlay = _validate(
        _parse_mapping(request.overlay_yaml, f"overlay {source}"), source
    )
    needs_backends = any(v.backend_id is not None for v in overlay.voters)
    backends = _backends(request) if needs_backends else {}
    backend_name = request.backend_overlay_source.rsplit("/", 1)[-1]

    resolved: list[ModelResolvedReviewVoter] = []
    for voter in overlay.voters:
        if voter.backend_id is not None:
            backend = backends.get(voter.backend_id)
            if backend is None:
                raise _RefusalError(
                    f"backend_id {voter.backend_id!r} is not bound in "
                    f"{request.backend_overlay_source} (bound: {sorted(backends)})",
                    voter.voter_id,
                )
            if not backend.endpoint_url:
                raise _RefusalError(
                    f"backend {voter.backend_id!r} in {request.backend_overlay_source} "
                    "has no endpoint_url",
                    voter.voter_id,
                )
            base_url = _base_url(
                backend.endpoint_url,
                voter.voter_id,
                f"backend {voter.backend_id!r} endpoint_url",
            )
            resolved.append(
                ModelResolvedReviewVoter(
                    voter=voter,
                    base_url=base_url,
                    source=f"backend {voter.backend_id} in {backend_name}",
                    backend_served_model_id=backend.served_model_id,
                )
            )
        else:
            base_url = _base_url(
                voter.endpoint_url or "", voter.voter_id, "endpoint_url"
            )
            resolved.append(
                ModelResolvedReviewVoter(
                    voter=voter, base_url=base_url, source="endpoint_url"
                )
            )
    return tuple(resolved)


class HandlerReviewVotersOverlay:
    """The node's handler: overlay text in, a resolved roster or a refusal out."""

    def handle(
        self, request: ModelReviewVotersOverlayRequest
    ) -> ModelReviewVoterRoster:
        """Validate the overlay and resolve every voter, or say why not.

        Pure and deterministic: the same texts give the same roster. A refusal
        is returned as data with the voter it concerns, never raised.
        """
        try:
            voters = _resolve(request)
        except _RefusalError as refusal:
            return ModelReviewVoterRoster(
                overlay_source=request.overlay_source,
                error=refusal.message,
                error_voter_id=refusal.voter_id,
            )
        return ModelReviewVoterRoster(
            overlay_source=request.overlay_source, voters=voters
        )


def handle(request: ModelReviewVotersOverlayRequest) -> ModelReviewVoterRoster:
    """The contract's routed entry point; see ``HandlerReviewVotersOverlay``."""
    return HandlerReviewVotersOverlay().handle(request)


def probe_target_lines(roster: ModelReviewVoterRoster) -> list[str]:
    """``TARGET|voter|host|port|url`` per voter, for the workflows' TCP preflight."""
    lines: list[str] = []
    for voter in roster.voters:
        host, port = voter.host_port
        lines.append(f"TARGET|{voter.voter_id}|{host}|{port}|{voter.base_url}")
    return lines


__all__ = ["HandlerReviewVotersOverlay", "handle", "probe_target_lines"]
