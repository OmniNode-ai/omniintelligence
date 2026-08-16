# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Frozen request, authorization, and context-pack wire contracts."""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from omniintelligence.code_projection._canonical import (
    normalize_repository_id,
    normalize_text,
)
from omniintelligence.code_projection.models import (
    ModelCodeProjectionLabel,
    ModelCodeProjectionPolicy,
    ModelCodeProjectionProvenance,
    ModelCodeProjectionSpan,
)

CODE_CONTEXT_REQUEST_SCHEMA_ID: Final[Literal["com.omninode.code-context-request"]] = (
    "com.omninode.code-context-request"
)
CODE_CONTEXT_PACK_SCHEMA_ID: Final[Literal["com.omninode.code-context-pack"]] = (
    "com.omninode.code-context-pack"
)
CODE_CONTEXT_RESPONSE_SCHEMA_ID: Final[
    Literal["com.omninode.code-context-response"]
] = "com.omninode.code-context-response"
CODE_CONTEXT_AUTHORIZATION_SCHEMA_ID: Final[
    Literal["com.omninode.code-context-authorization"]
] = "com.omninode.code-context-authorization"
CODE_CONTEXT_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
CODE_CONTEXT_SELECTION_POLICY_VERSION: Final[Literal["code-context-selection-v1"]] = (
    "code-context-selection-v1"
)
CODE_CONTEXT_TOKEN_ESTIMATOR: Final[Literal["cl100k_base"]] = "cl100k_base"  # noqa: S105 - tokenizer identity
CODE_CONTEXT_TOKEN_ESTIMATOR_VERSION: Final[Literal["tiktoken-cl100k-base-v1"]] = (
    "tiktoken-cl100k-base-v1"  # noqa: S105 - tokenizer identity
)

Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Sha256Ref = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
ArtifactRef = Annotated[
    str, StringConstraints(pattern=r"^artifact://sha256/[0-9a-f]{64}$")
]
SourceId = Annotated[str, StringConstraints(pattern=r"^csrc_v2_[0-9a-f]{64}$")]
BatchId = Annotated[str, StringConstraints(pattern=r"^cbatch_v2_[0-9a-f]{64}$")]
DocumentId = Annotated[str, StringConstraints(pattern=r"^cdoc_v2_[0-9a-f]{64}$")]
PointId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
CanonicalUuid = Annotated[
    str,
    StringConstraints(
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            r"[0-9a-f]{4}-[0-9a-f]{12}$"
        )
    ),
]
BoundedIdentifier = Annotated[
    str,
    StringConstraints(min_length=1, max_length=256, pattern=r"^[^\s\x00]+$"),
]
BoundedVersion = Annotated[str, StringConstraints(min_length=1, max_length=128)]
LogicalRepositoryId = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._/-]{2,127}$",
    ),
]
RepositoryInstanceId = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._/-]{2,127}$",
    ),
]
ProjectionRepositoryId = Annotated[
    str,
    StringConstraints(min_length=3, max_length=512),
]
PolicyScopeRef = Annotated[str, StringConstraints(min_length=1, max_length=1024)]

_LOGICAL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._/-]{2,127}$")


class _FrozenModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        from_attributes=True,
    )


def _require_uuid(value: str, *, field_name: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a canonical UUID") from exc
    if str(parsed) != value:
        raise ValueError(f"{field_name} must be a lowercase canonical UUID")
    return value


def _require_identifier(value: str) -> str:
    if normalize_text(value) != value or value != value.strip():
        raise ValueError("identifier must be canonical NFC without surrounding space")
    return value


def _require_repository_id(value: str, *, field_name: str) -> str:
    normalized = normalize_repository_id(value)
    if value != normalized or any(
        segment in {"", ".", ".."} for segment in value.split("/")
    ):
        raise ValueError(f"{field_name} must already be canonical")
    return value


def _require_logical_repository_id(value: str, *, field_name: str) -> str:
    _require_repository_id(value, field_name=field_name)
    if _LOGICAL_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(
            f"{field_name} must be 3-128 characters of canonical lowercase text"
        )
    return value


def _require_repository_instance_id(value: str) -> str:
    canonical = _require_logical_repository_id(
        value,
        field_name="repository_instance_id",
    )
    if "instances" in canonical.split("/"):
        raise ValueError("repository_instance_id uses the reserved instances namespace")
    return canonical


def _require_source_repository_id(value: str) -> str:
    canonical = _require_logical_repository_id(value, field_name="repository_id")
    if "instances" in canonical.split("/"):
        raise ValueError("repository_id uses the reserved instances namespace")
    return canonical


def derive_projection_repository_id(
    *,
    repository_id: str,
    repository_instance_id: str,
) -> str:
    """Derive the exact v2 repository identity used by source-artifact drain."""

    logical_repository_id = _require_source_repository_id(repository_id)
    canonical_instance_id = _require_repository_instance_id(repository_instance_id)
    if canonical_instance_id == "canonical":
        return logical_repository_id
    return normalize_repository_id(
        f"{logical_repository_id}/instances/{canonical_instance_id}"
    )


def derive_repository_policy_scope_ref(
    *,
    tenant_id: str,
    repository_id: str,
    repository_instance_id: str,
) -> str:
    """Derive the trusted event policy scope for one checkout instance."""

    canonical_tenant_id = _require_uuid(tenant_id, field_name="tenant_id")
    logical_repository_id = _require_source_repository_id(repository_id)
    canonical_instance_id = _require_repository_instance_id(repository_instance_id)
    return (
        f"tenant:{canonical_tenant_id}:repository:{logical_repository_id}:"
        f"instance:{canonical_instance_id}"
    )


class ModelCodeContextRepositoryScope(_FrozenModel):
    """One exact logical-repository and checkout-instance authorization scope."""

    repository_id: LogicalRepositoryId
    repository_instance_id: RepositoryInstanceId
    projection_repository_id: ProjectionRepositoryId
    policy_scope_ref: PolicyScopeRef

    @field_validator("repository_id")
    @classmethod
    def _canonical_logical_repository(cls, value: str) -> str:
        return _require_source_repository_id(value)

    @field_validator("projection_repository_id")
    @classmethod
    def _canonical_projection_repository(cls, value: str) -> str:
        return _require_repository_id(value, field_name="projection_repository_id")

    @field_validator("repository_instance_id")
    @classmethod
    def _canonical_repository_instance(cls, value: str) -> str:
        return _require_repository_instance_id(value)

    @model_validator(mode="after")
    def _derived_projection_identity(self) -> Self:
        expected = derive_projection_repository_id(
            repository_id=self.repository_id,
            repository_instance_id=self.repository_instance_id,
        )
        if self.projection_repository_id != expected:
            raise ValueError(
                "projection_repository_id does not match the repository instance"
            )
        return self


class ModelCodeContextRequest(_FrozenModel):
    """Canonical explicit request consumed unchanged by fake and live adapters."""

    kind: Literal["code_context_request"] = "code_context_request"
    schema_id: Literal["com.omninode.code-context-request"] = (
        CODE_CONTEXT_REQUEST_SCHEMA_ID
    )
    schema_version: Literal["1.0.0"] = CODE_CONTEXT_SCHEMA_VERSION
    request_id: CanonicalUuid
    correlation_id: CanonicalUuid
    tenant_id: CanonicalUuid
    repository_id: LogicalRepositoryId
    repository_instance_id: RepositoryInstanceId
    projection_repository_id: ProjectionRepositoryId
    policy_scope_ref: PolicyScopeRef
    principal_id: BoundedIdentifier
    query_text: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    candidate_limit: int = Field(ge=1, le=100)
    max_items: int = Field(ge=1, le=20)
    min_score_basis_points: int = Field(ge=0, le=10_000)
    max_context_bytes: int = Field(ge=512, le=131_072)
    max_context_tokens: int = Field(ge=64, le=32_768)
    timeout_ms: int = Field(ge=50, le=30_000)

    @field_validator("request_id", "correlation_id", "tenant_id")
    @classmethod
    def _canonical_uuid(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "uuid")
        return _require_uuid(value, field_name=field_name)

    @field_validator("repository_id")
    @classmethod
    def _canonical_logical_repository(cls, value: str) -> str:
        return _require_source_repository_id(value)

    @field_validator("projection_repository_id")
    @classmethod
    def _canonical_projection_repository(cls, value: str) -> str:
        return _require_repository_id(value, field_name="projection_repository_id")

    @field_validator("repository_instance_id")
    @classmethod
    def _canonical_repository_instance(cls, value: str) -> str:
        return _require_repository_instance_id(value)

    @field_validator("principal_id")
    @classmethod
    def _canonical_principal(cls, value: str) -> str:
        return _require_identifier(value)

    @field_validator("query_text")
    @classmethod
    def _canonical_query(cls, value: str) -> str:
        if (
            normalize_text(value) != value
            or not value.strip()
            or value != value.strip()
        ):
            raise ValueError(
                "query_text must be non-empty canonical NFC without edge whitespace"
            )
        forbidden = [
            character
            for character in value
            if ord(character) < 32 and character not in {"\n", "\t"}
        ]
        if forbidden:
            raise ValueError("query_text contains forbidden control characters")
        return value

    @model_validator(mode="after")
    def _bounded_selection(self) -> Self:
        if self.max_items > self.candidate_limit:
            raise ValueError("max_items must not exceed candidate_limit")
        expected_projection_id = derive_projection_repository_id(
            repository_id=self.repository_id,
            repository_instance_id=self.repository_instance_id,
        )
        if self.projection_repository_id != expected_projection_id:
            raise ValueError(
                "projection_repository_id does not match the repository instance"
            )
        expected_scope_ref = derive_repository_policy_scope_ref(
            tenant_id=self.tenant_id,
            repository_id=self.repository_id,
            repository_instance_id=self.repository_instance_id,
        )
        if self.policy_scope_ref != expected_scope_ref:
            raise ValueError("policy_scope_ref does not match the repository instance")
        return self


class ModelCodeContextEmbeddingContract(_FrozenModel):
    """One embedding identity admitted by an operator authorization profile."""

    model: BoundedIdentifier
    version: BoundedVersion

    @field_validator("model", "version")
    @classmethod
    def _canonical_text(cls, value: str) -> str:
        return _require_identifier(value)


class ModelCodeContextAuthorizationGrant(_FrozenModel):
    """Closed principal-to-tenant/repository serving authority."""

    principal_id: BoundedIdentifier
    tenant_id: CanonicalUuid
    repository_scopes: tuple[ModelCodeContextRepositoryScope, ...] = Field(
        min_length=1,
        max_length=128,
    )
    allowed_policy_versions: tuple[BoundedVersion, ...] = Field(
        min_length=1, max_length=32
    )
    allowed_retention_classes: tuple[
        Literal["ephemeral", "policy_managed", "source_controlled"], ...
    ] = Field(min_length=1, max_length=3)
    allowed_embedding_contracts: tuple[ModelCodeContextEmbeddingContract, ...] = Field(
        min_length=1, max_length=32
    )
    maximum_items: int = Field(ge=1, le=20)
    maximum_context_bytes: int = Field(ge=512, le=131_072)
    maximum_context_tokens: int = Field(ge=64, le=32_768)

    @field_validator("principal_id")
    @classmethod
    def _canonical_principal(cls, value: str) -> str:
        return _require_identifier(value)

    @field_validator("tenant_id")
    @classmethod
    def _canonical_tenant(cls, value: str) -> str:
        return _require_uuid(value, field_name="tenant_id")

    @field_validator("repository_scopes")
    @classmethod
    def _canonical_repositories(
        cls,
        values: tuple[ModelCodeContextRepositoryScope, ...],
    ) -> tuple[ModelCodeContextRepositoryScope, ...]:
        keys = tuple(
            (
                value.repository_id,
                value.repository_instance_id,
                value.projection_repository_id,
                value.policy_scope_ref,
            )
            for value in values
        )
        if keys != tuple(sorted(set(keys))):
            raise ValueError("repository_scopes must be unique and canonically sorted")
        return values

    @model_validator(mode="after")
    def _instance_bound_policy_scopes(self) -> Self:
        for scope in self.repository_scopes:
            expected = derive_repository_policy_scope_ref(
                tenant_id=self.tenant_id,
                repository_id=scope.repository_id,
                repository_instance_id=scope.repository_instance_id,
            )
            if scope.policy_scope_ref != expected:
                raise ValueError(
                    "repository policy scope does not match its tenant and instance"
                )
        return self

    @field_validator("allowed_policy_versions")
    @classmethod
    def _canonical_policy_versions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(_require_identifier(value) != value for value in values):
            raise ValueError("policy versions must be canonical")
        if values != tuple(sorted(set(values))):
            raise ValueError("allowed_policy_versions must be unique and sorted")
        return values

    @field_validator("allowed_retention_classes")
    @classmethod
    def _canonical_retention_classes(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        if values != tuple(sorted(set(values))):
            raise ValueError("allowed_retention_classes must be unique and sorted")
        return values

    @field_validator("allowed_embedding_contracts")
    @classmethod
    def _canonical_embedding_contracts(
        cls,
        values: tuple[ModelCodeContextEmbeddingContract, ...],
    ) -> tuple[ModelCodeContextEmbeddingContract, ...]:
        keys = tuple((value.model, value.version) for value in values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError(
                "allowed_embedding_contracts must be unique and canonically sorted"
            )
        return values


class ModelCodeContextAuthorizationProfile(_FrozenModel):
    """Versioned operator-owned authorization registry for explicit serving."""

    kind: Literal["code_context_authorization"] = "code_context_authorization"
    schema_id: Literal["com.omninode.code-context-authorization"] = (
        CODE_CONTEXT_AUTHORIZATION_SCHEMA_ID
    )
    schema_version: Literal["1.0.0"] = CODE_CONTEXT_SCHEMA_VERSION
    profile_id: BoundedIdentifier
    selection_policy_version: Literal["code-context-selection-v1"] = (
        CODE_CONTEXT_SELECTION_POLICY_VERSION
    )
    grants: tuple[ModelCodeContextAuthorizationGrant, ...] = Field(
        min_length=1, max_length=256
    )

    @field_validator("profile_id")
    @classmethod
    def _canonical_profile(cls, value: str) -> str:
        return _require_identifier(value)

    @field_validator("grants")
    @classmethod
    def _canonical_grants(
        cls,
        values: tuple[ModelCodeContextAuthorizationGrant, ...],
    ) -> tuple[ModelCodeContextAuthorizationGrant, ...]:
        keys = tuple((value.principal_id, value.tenant_id) for value in values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("authorization grants must be unique and sorted")
        return values


class ModelAuthorizedCodeContextCandidate(_FrozenModel):
    """Internally resolved content bound to one promoted projection record."""

    point_id: PointId
    score_basis_points: int
    tenant_id: CanonicalUuid
    repository_id: LogicalRepositoryId
    repository_instance_id: RepositoryInstanceId
    projection_repository_id: ProjectionRepositoryId
    policy_scope_ref: PolicyScopeRef
    relative_path: str
    source_id: SourceId
    source_hash_sha256: Sha256Hex
    source_artifact_ref: ArtifactRef
    batch_id: BatchId
    batch_content_hash_sha256: Sha256Hex
    cursor_sequence: int = Field(ge=1)
    document_id: DocumentId
    content_ref: ArtifactRef
    sanitized_content_hash_sha256: Sha256Hex
    chunk_key: str
    chunk_kind: str
    anchor_node_id: str | None
    source_span: ModelCodeProjectionSpan | None
    labels: tuple[ModelCodeProjectionLabel, ...]
    embedding_model: str
    embedding_model_version: str
    policy: ModelCodeProjectionPolicy
    policy_payload_sha256: Sha256Hex
    provenance: ModelCodeProjectionProvenance
    provenance_payload_sha256: Sha256Hex
    content: str


class ModelCodeContextItem(_FrozenModel):
    """One ranked authorized item included in a bounded context pack."""

    rank: int = Field(ge=1, le=20)
    score_basis_points: int
    tenant_id: CanonicalUuid
    repository_id: LogicalRepositoryId
    repository_instance_id: RepositoryInstanceId
    projection_repository_id: ProjectionRepositoryId
    policy_scope_ref: PolicyScopeRef
    relative_path: str
    source_id: SourceId
    source_hash_sha256: Sha256Hex
    source_artifact_ref: ArtifactRef
    batch_id: BatchId
    batch_content_hash_sha256: Sha256Hex
    cursor_sequence: int = Field(ge=1)
    document_id: DocumentId
    content_ref: ArtifactRef
    sanitized_content_hash_sha256: Sha256Hex
    chunk_key: str
    chunk_kind: str
    anchor_node_id: str | None
    source_span: ModelCodeProjectionSpan | None
    labels: tuple[ModelCodeProjectionLabel, ...]
    embedding_model: str
    embedding_model_version: str
    policy: ModelCodeProjectionPolicy
    policy_payload_sha256: Sha256Hex
    provenance: ModelCodeProjectionProvenance
    provenance_payload_sha256: Sha256Hex
    content: str
    content_byte_count: int = Field(ge=0)
    token_estimate: int = Field(ge=0)


class ModelCodeContextPackBody(_FrozenModel):
    """Digest input for the authoritative explicit context pack."""

    kind: Literal["code_context_pack"] = "code_context_pack"
    schema_id: Literal["com.omninode.code-context-pack"] = CODE_CONTEXT_PACK_SCHEMA_ID
    schema_version: Literal["1.0.0"] = CODE_CONTEXT_SCHEMA_VERSION
    request_id: CanonicalUuid
    correlation_id: CanonicalUuid
    request_payload_sha256: Sha256Hex
    query_sha256: Sha256Hex
    tenant_id: CanonicalUuid
    repository_id: LogicalRepositoryId
    repository_instance_id: RepositoryInstanceId
    projection_repository_id: ProjectionRepositoryId
    policy_scope_ref: PolicyScopeRef
    principal_id: str
    authorization_profile_id: str
    authorization_profile_payload_sha256: Sha256Hex
    selection_policy_version: Literal["code-context-selection-v1"] = (
        CODE_CONTEXT_SELECTION_POLICY_VERSION
    )
    token_estimator: Literal["cl100k_base"] = CODE_CONTEXT_TOKEN_ESTIMATOR
    token_estimator_version: Literal["tiktoken-cl100k-base-v1"] = (
        CODE_CONTEXT_TOKEN_ESTIMATOR_VERSION
    )
    candidates_considered: int = Field(ge=0, le=100)
    truncated: bool
    items: tuple[ModelCodeContextItem, ...] = Field(max_length=20)
    total_content_bytes: int = Field(ge=0)
    total_context_bytes: int = Field(ge=0)
    total_context_tokens: int = Field(ge=0)


class ModelGenerationContextArtifact(_FrozenModel):
    """Generation-consumer-compatible per-artifact provenance shape."""

    factor: Literal["code"] = "code"
    content: str
    source_ref: ArtifactRef
    content_hash: Sha256Ref


class ModelGenerationContextBoundary(_FrozenModel):
    """Typed handoff matching the existing generation consumer context seam."""

    context_pack: str
    context_artifacts: tuple[ModelGenerationContextArtifact, ...]
    context_pack_hash: Sha256Ref


class ModelCodeContextResponse(_FrozenModel):
    """Canonical result containing pack proof and generation handoff."""

    kind: Literal["code_context_response"] = "code_context_response"
    schema_id: Literal["com.omninode.code-context-response"] = (
        CODE_CONTEXT_RESPONSE_SCHEMA_ID
    )
    schema_version: Literal["1.0.0"] = CODE_CONTEXT_SCHEMA_VERSION
    pack: ModelCodeContextPackBody
    pack_payload_sha256: Sha256Ref
    generation: ModelGenerationContextBoundary


__all__ = [
    "CODE_CONTEXT_AUTHORIZATION_SCHEMA_ID",
    "CODE_CONTEXT_PACK_SCHEMA_ID",
    "CODE_CONTEXT_REQUEST_SCHEMA_ID",
    "CODE_CONTEXT_RESPONSE_SCHEMA_ID",
    "CODE_CONTEXT_SCHEMA_VERSION",
    "CODE_CONTEXT_SELECTION_POLICY_VERSION",
    "CODE_CONTEXT_TOKEN_ESTIMATOR",
    "CODE_CONTEXT_TOKEN_ESTIMATOR_VERSION",
    "ModelAuthorizedCodeContextCandidate",
    "ModelCodeContextAuthorizationGrant",
    "ModelCodeContextAuthorizationProfile",
    "ModelCodeContextEmbeddingContract",
    "ModelCodeContextItem",
    "ModelCodeContextPackBody",
    "ModelCodeContextRequest",
    "ModelCodeContextRepositoryScope",
    "ModelCodeContextResponse",
    "ModelGenerationContextArtifact",
    "ModelGenerationContextBoundary",
    "derive_projection_repository_id",
    "derive_repository_policy_scope_ref",
]
