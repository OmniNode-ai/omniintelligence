# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dependency-injected boundaries for fake and real context serving."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from omniintelligence.code_projection.context_serving.models import (
    ModelAuthorizedCodeContextCandidate,
    ModelCodeContextRequest,
)
from omniintelligence.code_projection.qdrant import ModelCodeProjectionSearchHit


@runtime_checkable
class ProtocolCodeContextSearch(Protocol):
    """Metadata-only semantic search scoped by explicit tenant coordinates."""

    async def search(
        self,
        *,
        query_text: str,
        tenant_id: str,
        repository_id: str | None = None,
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> tuple[ModelCodeProjectionSearchHit, ...]:
        """Return current-generation metadata hits without resolving content."""


@runtime_checkable
class ProtocolCodeContextArtifactResolver(Protocol):
    """Authorize and resolve semantic artifacts against projection truth."""

    @property
    def authorization_profile_id(self) -> str:
        """Return the immutable operator profile identity."""

    @property
    def authorization_profile_payload_sha256(self) -> str:
        """Return the canonical operator profile digest."""

    @property
    def selection_policy_version(self) -> Literal["code-context-selection-v1"]:
        """Return the selection policy bound by the authorization profile."""

    def authorize_request(self, request: ModelCodeContextRequest) -> None:
        """Reject an unauthorized request before its query reaches search."""

    async def resolve(
        self,
        *,
        request: ModelCodeContextRequest,
        hit: ModelCodeProjectionSearchHit,
        score_basis_points: int,
    ) -> ModelAuthorizedCodeContextCandidate:
        """Return verified content and complete promoted-batch provenance."""


__all__ = [
    "ProtocolCodeContextArtifactResolver",
    "ProtocolCodeContextSearch",
]
