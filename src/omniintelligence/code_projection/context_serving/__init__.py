# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Explicit tenant-authorized code search and context-pack application."""

from omniintelligence.code_projection.context_serving.codec import (
    parse_authorization_profile,
    parse_code_context_request,
    serialize_authorization_profile,
    serialize_code_context_request,
    serialize_code_context_response,
)
from omniintelligence.code_projection.context_serving.models import (
    ModelCodeContextAuthorizationGrant,
    ModelCodeContextAuthorizationProfile,
    ModelCodeContextEmbeddingContract,
    ModelCodeContextRepositoryScope,
    ModelCodeContextRequest,
    ModelCodeContextResponse,
    derive_projection_repository_id,
    derive_repository_policy_scope_ref,
)
from omniintelligence.code_projection.context_serving.resolver import (
    CodeProjectionContextArtifactResolver,
    authorize_code_context_request,
)
from omniintelligence.code_projection.context_serving.service import (
    CodeContextProcessor,
)

__all__ = [
    "CodeContextProcessor",
    "CodeProjectionContextArtifactResolver",
    "ModelCodeContextAuthorizationGrant",
    "ModelCodeContextAuthorizationProfile",
    "ModelCodeContextEmbeddingContract",
    "ModelCodeContextRequest",
    "ModelCodeContextRepositoryScope",
    "ModelCodeContextResponse",
    "derive_projection_repository_id",
    "derive_repository_policy_scope_ref",
    "authorize_code_context_request",
    "parse_authorization_profile",
    "parse_code_context_request",
    "serialize_authorization_profile",
    "serialize_code_context_request",
    "serialize_code_context_response",
]
