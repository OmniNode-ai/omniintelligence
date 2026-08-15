# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Authorization-aware resolver for promoted v2 semantic artifacts."""

from __future__ import annotations

from typing import Literal

from omniintelligence.code_projection._canonical import canonical_json_bytes, sha256_hex
from omniintelligence.code_projection.artifacts import CodeProjectionArtifactStore
from omniintelligence.code_projection.context_serving.exceptions import (
    CodeContextAuthorizationError,
    CodeContextCandidateBudgetError,
    CodeContextIntegrityError,
)
from omniintelligence.code_projection.context_serving.models import (
    ModelAuthorizedCodeContextCandidate,
    ModelCodeContextAuthorizationGrant,
    ModelCodeContextAuthorizationProfile,
    ModelCodeContextRequest,
)
from omniintelligence.code_projection.models import ModelCodeProjectionLabel
from omniintelligence.code_projection.qdrant import ModelCodeProjectionSearchHit


def _authorize_grant(
    grant: ModelCodeContextAuthorizationGrant,
    request: ModelCodeContextRequest,
) -> ModelCodeContextAuthorizationGrant:
    requested_scope = (
        request.repository_id,
        request.repository_instance_id,
        request.projection_repository_id,
        request.policy_scope_ref,
    )
    granted_scopes = {
        (
            scope.repository_id,
            scope.repository_instance_id,
            scope.projection_repository_id,
            scope.policy_scope_ref,
        )
        for scope in grant.repository_scopes
    }
    if requested_scope not in granted_scopes:
        raise CodeContextAuthorizationError(
            "principal has no grant for the requested repository instance"
        )
    if request.max_items > grant.maximum_items:
        raise CodeContextAuthorizationError(
            "requested item budget exceeds the principal grant"
        )
    if request.max_context_bytes > grant.maximum_context_bytes:
        raise CodeContextAuthorizationError(
            "requested byte budget exceeds the principal grant"
        )
    if request.max_context_tokens > grant.maximum_context_tokens:
        raise CodeContextAuthorizationError(
            "requested token budget exceeds the principal grant"
        )
    return grant


def authorize_code_context_request(
    *,
    authorization_profile: ModelCodeContextAuthorizationProfile,
    request: ModelCodeContextRequest,
) -> ModelCodeContextAuthorizationGrant:
    """Authorize from a trusted profile before opening any serving dependency."""

    grant = next(
        (
            candidate
            for candidate in authorization_profile.grants
            if candidate.principal_id == request.principal_id
            and candidate.tenant_id == request.tenant_id
        ),
        None,
    )
    if grant is None:
        raise CodeContextAuthorizationError(
            "principal has no grant for the requested tenant"
        )
    return _authorize_grant(grant, request)


class CodeProjectionContextArtifactResolver:
    """Resolve only artifacts admitted by operator authority and promoted truth."""

    def __init__(
        self,
        *,
        artifact_store: CodeProjectionArtifactStore,
        authorization_profile: ModelCodeContextAuthorizationProfile,
    ) -> None:
        self._artifact_store = artifact_store
        self._profile = authorization_profile
        self._authorization_profile_payload_sha256 = sha256_hex(
            canonical_json_bytes(authorization_profile.model_dump(mode="json"))
        )
        self._grants = {
            (grant.principal_id, grant.tenant_id): grant
            for grant in authorization_profile.grants
        }

    @property
    def authorization_profile_id(self) -> str:
        """Return the exact operator profile identity."""

        return self._profile.profile_id

    @property
    def authorization_profile_payload_sha256(self) -> str:
        """Return the exact canonical operator-profile digest."""

        return self._authorization_profile_payload_sha256

    @property
    def selection_policy_version(self) -> Literal["code-context-selection-v1"]:
        """Return the exact selection-policy identity."""

        return self._profile.selection_policy_version

    def _grant(
        self,
        request: ModelCodeContextRequest,
    ) -> ModelCodeContextAuthorizationGrant:
        grant = self._grants.get((request.principal_id, request.tenant_id))
        if grant is None:
            raise CodeContextAuthorizationError(
                "principal has no grant for the requested tenant"
            )
        return _authorize_grant(grant, request)

    def authorize_request(self, request: ModelCodeContextRequest) -> None:
        """Fail before search when no exact principal scope exists."""

        self._grant(request)

    async def resolve(
        self,
        *,
        request: ModelCodeContextRequest,
        hit: ModelCodeProjectionSearchHit,
        score_basis_points: int,
    ) -> ModelAuthorizedCodeContextCandidate:
        """Verify one Qdrant hit against its current canonical batch and content."""

        grant = self._grant(request)
        if hit.tenant_id != request.tenant_id:
            raise CodeContextIntegrityError("search hit crossed the tenant boundary")
        if hit.repository_id != request.projection_repository_id:
            raise CodeContextIntegrityError(
                "search hit crossed the projection repository boundary"
            )

        try:
            current = self._artifact_store.load_current(hit.source_id)
        except (OSError, RuntimeError, ValueError) as exc:
            raise CodeContextIntegrityError(
                "promoted source projection could not be validated"
            ) from exc
        if current is None:
            raise CodeContextIntegrityError(
                "search hit has no promoted source projection"
            )
        batch = current.batch
        source = batch.source
        if batch.operation != "snapshot":
            raise CodeContextIntegrityError(
                "search hit resolves to a tombstoned source"
            )
        if (
            source.tenant_id != request.tenant_id
            or source.repository_id != request.projection_repository_id
            or source.source_id != hit.source_id
            or source.relative_path != hit.relative_path
            or batch.batch_id != hit.batch_id
        ):
            raise CodeContextIntegrityError(
                "search hit source identity does not match promoted truth"
            )

        documents = {
            document.document_id: document for document in batch.semantic_documents
        }
        document = documents.get(hit.document_id)
        if document is None:
            raise CodeContextIntegrityError(
                "search hit document is not in the promoted batch"
            )
        if (
            document.source_id != source.source_id
            or document.byte_count != hit.byte_count
            or document.content_ref != hit.content_ref
            or document.sanitized_content_hash_sha256
            != hit.sanitized_content_hash_sha256
            or document.chunk_key != hit.chunk_key
            or document.chunk_kind != hit.chunk_kind
            or document.anchor_node_id != hit.anchor_node_id
            or document.source_span != hit.source_span
        ):
            raise CodeContextIntegrityError(
                "search hit document metadata does not match promoted truth"
            )
        if document.byte_count > request.max_context_bytes:
            raise CodeContextCandidateBudgetError(
                "semantic document exceeds the requested context byte budget"
            )

        embedding_key = (hit.embedding_model, hit.embedding_model_version)
        allowed_embedding_keys = {
            (contract.model, contract.version)
            for contract in grant.allowed_embedding_contracts
        }
        if embedding_key not in allowed_embedding_keys:
            raise CodeContextAuthorizationError(
                "search hit embedding contract is not admitted by the grant"
            )

        policy = batch.policy
        if (
            policy.tenant_id != request.tenant_id
            or policy.scope_ref != request.policy_scope_ref
            or policy.access_scope != "repository"
            or policy.visibility != "repository"
            or policy.trust_tier != "verified_source"
            or policy.redaction_state not in {"sanitized", "not_required"}
        ):
            raise CodeContextAuthorizationError(
                "promoted projection policy is outside the admitted repository scope"
            )
        if policy.policy_version not in grant.allowed_policy_versions:
            raise CodeContextAuthorizationError(
                "promoted projection policy version is not admitted by the grant"
            )
        if policy.retention_class not in grant.allowed_retention_classes:
            raise CodeContextAuthorizationError(
                "promoted projection retention class is not admitted by the grant"
            )

        try:
            content_bytes = self._artifact_store.read_content_artifact(
                document.sanitized_content_hash_sha256
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise CodeContextIntegrityError(
                "semantic content artifact could not be validated"
            ) from exc
        if len(content_bytes) != document.byte_count:
            raise CodeContextIntegrityError(
                "semantic content size does not match promoted truth"
            )
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CodeContextIntegrityError(
                "semantic content artifact is not valid UTF-8"
            ) from exc
        if "\x00" in content:
            raise CodeContextIntegrityError(
                "semantic content artifact contains a forbidden NUL"
            )

        labels: tuple[ModelCodeProjectionLabel, ...] = ()
        if document.anchor_node_id is not None:
            anchor = next(
                (
                    node
                    for node in batch.nodes
                    if node.node_id == document.anchor_node_id
                ),
                None,
            )
            if anchor is None or anchor.source_id != source.source_id:
                raise CodeContextIntegrityError(
                    "semantic document anchor is absent from promoted truth"
                )
            labels = anchor.labels

        return ModelAuthorizedCodeContextCandidate(
            point_id=hit.point_id,
            score_basis_points=score_basis_points,
            tenant_id=request.tenant_id,
            repository_id=request.repository_id,
            repository_instance_id=request.repository_instance_id,
            projection_repository_id=request.projection_repository_id,
            policy_scope_ref=request.policy_scope_ref,
            relative_path=source.relative_path,
            source_id=source.source_id,
            source_hash_sha256=source.raw_content_hash_sha256,
            source_artifact_ref=source.artifact_ref,
            batch_id=batch.batch_id,
            batch_content_hash_sha256=current.batch_content_hash_sha256,
            cursor_sequence=batch.cursor.sequence,
            document_id=document.document_id,
            content_ref=document.content_ref,
            sanitized_content_hash_sha256=document.sanitized_content_hash_sha256,
            chunk_key=document.chunk_key,
            chunk_kind=document.chunk_kind,
            anchor_node_id=document.anchor_node_id,
            source_span=document.source_span,
            labels=labels,
            embedding_model=hit.embedding_model,
            embedding_model_version=hit.embedding_model_version,
            policy=policy,
            policy_payload_sha256=sha256_hex(
                canonical_json_bytes(policy.model_dump(mode="json"))
            ),
            provenance=batch.provenance,
            provenance_payload_sha256=sha256_hex(
                canonical_json_bytes(batch.provenance.model_dump(mode="json"))
            ),
            content=content,
        )


__all__ = [
    "CodeProjectionContextArtifactResolver",
    "authorize_code_context_request",
]
