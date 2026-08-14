# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Deterministic primitives for the proof-local code projection seam."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import cast

type JsonScalar = None | bool | int | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")


class DuplicateJsonKeyError(ValueError):
    """Raised when serialized input contains an ambiguous duplicate object key."""


def normalize_text(value: str) -> str:
    """Return the NFC-normalized representation used by canonical artifacts."""

    return unicodedata.normalize("NFC", value)


def normalize_repository_id(value: str) -> str:
    """Normalize a logical repository ID and reject local-path identities."""

    normalized = normalize_text(value)
    if not normalized or normalized != normalized.strip():
        msg = "repository_id must be non-empty with no surrounding whitespace"
        raise ValueError(msg)
    if "\x00" in normalized or "\\" in normalized:
        msg = "repository_id must not contain NUL or backslashes"
        raise ValueError(msg)
    if (
        normalized.startswith(("/", "~"))
        or normalized.casefold().startswith("file:")
        or _WINDOWS_DRIVE_PATTERN.match(normalized)
        or ".." in normalized.split("/")
    ):
        msg = "repository_id must be logical rather than a local filesystem path"
        raise ValueError(msg)
    return normalized


def normalize_relative_path(value: str) -> str:
    """Normalize a repository-relative path and reject authority ambiguity.

    Backslashes are accepted as producer-side separators so fixtures created on
    Windows and POSIX hosts resolve to the same logical path. Absolute paths,
    UNC paths, drive-prefixed paths, traversal, NUL bytes, and empty paths fail
    closed.
    """

    normalized = normalize_text(value)
    if "\x00" in normalized:
        msg = "repository-relative path must not contain NUL"
        raise ValueError(msg)

    normalized = normalized.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("//"):
        msg = "repository-relative path must not be absolute"
        raise ValueError(msg)
    if _WINDOWS_DRIVE_PATTERN.match(normalized):
        msg = "repository-relative path must not contain a drive prefix"
        raise ValueError(msg)

    parts: list[str] = []
    for part in normalized.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            msg = "repository-relative path must not traverse parents"
            raise ValueError(msg)
        parts.append(part)

    if not parts:
        msg = "repository-relative path must identify a file"
        raise ValueError(msg)
    if parts[0].startswith("~"):
        msg = "repository-relative path must not use a home-like prefix"
        raise ValueError(msg)
    return "/".join(parts)


def validate_sha256(value: str, *, field_name: str) -> str:
    """Validate and return a lowercase SHA-256 hexadecimal digest."""

    if not _SHA256_PATTERN.fullmatch(value):
        msg = f"{field_name} must be a lowercase 64-character SHA-256 digest"
        raise ValueError(msg)
    return value


def sha256_hex(value: bytes) -> str:
    """Return the lowercase SHA-256 hexadecimal digest for ``value``."""

    return hashlib.sha256(value).hexdigest()


def _canonical_value(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, float):
        msg = "floating-point values are forbidden in canonical projection JSON"
        raise TypeError(msg)
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        normalized: dict[str, JsonValue] = {}
        for key, item in mapping.items():
            if not isinstance(key, str):
                msg = "canonical projection JSON object keys must be strings"
                raise TypeError(msg)
            normalized_key = normalize_text(key)
            if normalized_key in normalized:
                msg = f"duplicate canonical object key: {normalized_key!r}"
                raise DuplicateJsonKeyError(msg)
            normalized[normalized_key] = _canonical_value(item)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        sequence = cast(Sequence[object], value)
        return [_canonical_value(item) for item in sequence]

    msg = f"unsupported canonical JSON value: {type(value).__name__}"
    raise TypeError(msg)


def canonical_json_bytes(value: object) -> bytes:
    """Serialize supported data as compact, byte-stable UTF-8 JSON."""

    normalized = _canonical_value(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        normalized_key = normalize_text(key)
        if normalized_key in result:
            msg = f"duplicate canonical JSON object key: {normalized_key!r}"
            raise DuplicateJsonKeyError(msg)
        result[normalized_key] = value
    return result


def decode_json_no_duplicates(value: bytes | str) -> object:
    """Decode UTF-8 JSON while rejecting duplicate object keys."""

    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            msg = "projection payload must be valid UTF-8"
            raise ValueError(msg) from exc
    else:
        text = value

    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        msg = "projection payload must be valid JSON"
        raise ValueError(msg) from exc


def stable_id(*, prefix: str, domain: str, payload: object) -> str:
    """Create a domain-separated deterministic identifier."""

    if not prefix.endswith("_"):
        msg = "stable ID prefix must end with an underscore"
        raise ValueError(msg)
    if not domain or "\x00" in domain:
        msg = "stable ID domain must be non-empty and contain no NUL"
        raise ValueError(msg)
    material = domain.encode("utf-8") + b"\x00" + canonical_json_bytes(payload)
    return f"{prefix}{sha256_hex(material)}"
