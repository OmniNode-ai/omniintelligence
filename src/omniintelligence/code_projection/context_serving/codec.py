# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Exact canonical codecs for context-serving requests and results."""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from omniintelligence.code_projection._canonical import (
    canonical_json_bytes,
    decode_json_no_duplicates,
)
from omniintelligence.code_projection.context_serving.exceptions import (
    CodeContextRequestError,
)
from omniintelligence.code_projection.context_serving.models import (
    ModelCodeContextAuthorizationProfile,
    ModelCodeContextPackBody,
    ModelCodeContextRequest,
    ModelCodeContextResponse,
)


def _raw_bytes(payload: bytes | str) -> bytes:
    return payload if isinstance(payload, bytes) else payload.encode("utf-8")


def _parse_canonical_model[ModelT: BaseModel](
    payload: bytes | str,
    *,
    model: type[ModelT],
    description: str,
) -> ModelT:
    raw = _raw_bytes(payload)
    try:
        decode_json_no_duplicates(raw)
        validated = model.model_validate_json(raw)
    except (TypeError, ValueError, ValidationError) as exc:
        raise CodeContextRequestError(f"{description} is invalid") from exc
    canonical = canonical_json_bytes(validated.model_dump(mode="json"))
    if raw != canonical:
        raise CodeContextRequestError(f"{description} is not canonical JSON")
    return validated


def serialize_code_context_request(request: ModelCodeContextRequest) -> bytes:
    """Return the exact canonical request bytes used by every adapter."""

    return canonical_json_bytes(request.model_dump(mode="json"))


def parse_code_context_request(payload: bytes | str) -> ModelCodeContextRequest:
    """Parse strict canonical request bytes without ambiguous JSON keys."""

    return _parse_canonical_model(
        payload,
        model=ModelCodeContextRequest,
        description="code-context request",
    )


def serialize_authorization_profile(
    profile: ModelCodeContextAuthorizationProfile,
) -> bytes:
    """Return canonical operator authorization bytes."""

    return canonical_json_bytes(profile.model_dump(mode="json"))


def parse_authorization_profile(
    payload: bytes | str,
) -> ModelCodeContextAuthorizationProfile:
    """Parse a strict canonical authorization profile."""

    return _parse_canonical_model(
        payload,
        model=ModelCodeContextAuthorizationProfile,
        description="code-context authorization profile",
    )


def serialize_pack_body(pack: ModelCodeContextPackBody) -> bytes:
    """Return canonical pack digest input."""

    return canonical_json_bytes(pack.model_dump(mode="json"))


def serialize_code_context_response(response: ModelCodeContextResponse) -> bytes:
    """Return canonical response bytes."""

    return canonical_json_bytes(response.model_dump(mode="json"))


__all__ = [
    "parse_authorization_profile",
    "parse_code_context_request",
    "serialize_authorization_profile",
    "serialize_code_context_request",
    "serialize_code_context_response",
    "serialize_pack_body",
]
