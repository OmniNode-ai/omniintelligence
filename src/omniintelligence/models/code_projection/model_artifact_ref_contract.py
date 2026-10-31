# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Artifact reference prefix of the code projection (OMN-21623).

The prefix lives in ``code_projection/artifact_ref.yaml``; this model validates
that contract and is the one way code reads it. The field is required and unknown
fields are refused, so a file that omits or misspells it fails to load instead of
falling back to a value in code.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

_CONTRACT_PATH: Path = (
    Path(__file__).resolve().parents[2] / "code_projection" / "artifact_ref.yaml"
)

_SHA256_HEX_PATTERN = "[0-9a-f]{64}"


class ModelArtifactRefContractLoadError(RuntimeError):
    """Raised when ``artifact_ref.yaml`` is missing, malformed or incomplete."""


class ModelArtifactRefContract(BaseModel):
    """The artifact reference prefix of the code projection.

    Attributes:
        prefix: Text every artifact reference starts with; the SHA-256 hex digest
            of the artifact follows it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    prefix: str = Field(min_length=1)

    @classmethod
    def load(cls, path: Path | None = None) -> ModelArtifactRefContract:
        """Read and validate the artifact reference contract.

        Args:
            path: Optional override for the YAML path (tests only).

        Raises:
            ModelArtifactRefContractLoadError: If the file is missing, not a
                mapping, or fails validation.
        """
        source = path or _CONTRACT_PATH
        if not source.is_file():
            raise ModelArtifactRefContractLoadError(
                f"artifact_ref.yaml not found at {source}"
            )
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
            return cls.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as exc:
            raise ModelArtifactRefContractLoadError(
                f"artifact_ref.yaml failed to load: {exc}"
            ) from exc


@cache
def artifact_ref_contract() -> ModelArtifactRefContract:
    """The shipped ``artifact_ref.yaml``, loaded once per process."""
    return ModelArtifactRefContract.load()


def artifact_ref_for(digest: str) -> str:
    """The artifact reference of one SHA-256 hex digest."""
    return f"{artifact_ref_contract().prefix}{digest}"


def artifact_digest_or_none(reference: str) -> str | None:
    """The digest an artifact reference names, or ``None`` when it is not one."""
    prefix = artifact_ref_contract().prefix
    if not reference.startswith(prefix):
        return None
    return reference.removeprefix(prefix)


def artifact_digest(reference: str) -> str:
    """The digest an artifact reference names.

    Raises:
        ValueError: If ``reference`` is not an artifact reference.
    """
    digest = artifact_digest_or_none(reference)
    if digest is None:
        raise ValueError("semantic content_ref is not a SHA-256 artifact URI")
    return digest


def artifact_ref_pattern() -> str:
    """Regular expression matching exactly one well-formed artifact reference."""
    return f"^{re.escape(artifact_ref_contract().prefix)}{_SHA256_HEX_PATTERN}$"


ArtifactRef = Annotated[str, StringConstraints(pattern=artifact_ref_pattern())]
"""One well-formed artifact reference."""

__all__ = [
    "ArtifactRef",
    "ModelArtifactRefContract",
    "ModelArtifactRefContractLoadError",
    "artifact_ref_for",
    "artifact_digest",
    "artifact_digest_or_none",
    "artifact_ref_contract",
    "artifact_ref_pattern",
]
