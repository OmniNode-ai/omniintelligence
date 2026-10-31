# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Code projection models: the contract-loaded artifact reference prefix (OMN-21623)."""

from omniintelligence.models.code_projection.model_artifact_ref_contract import (
    ArtifactRef,
    ModelArtifactRefContract,
    ModelArtifactRefContractLoadError,
    artifact_digest,
    artifact_digest_or_none,
    artifact_ref_contract,
    artifact_ref_for,
    artifact_ref_pattern,
)

__all__ = [
    "ArtifactRef",
    "ModelArtifactRefContract",
    "ModelArtifactRefContractLoadError",
    "artifact_ref_for",
    "artifact_ref_contract",
    "artifact_digest",
    "artifact_digest_or_none",
    "artifact_ref_pattern",
]
