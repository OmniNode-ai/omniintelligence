# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""One canonical scenario shared by fake and artifact-backed tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omniintelligence.code_projection import (
    ModelCodeProjectionCursor,
    ModelCodeProjectionLabel,
    ModelCodeProjectionPolicy,
    ModelCodeProjectionProvenance,
    ModelCodeProjectionSpan,
    build_code_projection_batch,
    make_code_chunk,
    make_code_node,
    make_code_source,
)
from omniintelligence.code_projection._canonical import canonical_json_bytes, sha256_hex
from omniintelligence.code_projection.artifacts import CodeProjectionArtifactStore
from omniintelligence.code_projection.context_serving.codec import (
    serialize_code_context_request,
)
from omniintelligence.code_projection.context_serving.models import (
    ModelCodeContextAuthorizationGrant,
    ModelCodeContextAuthorizationProfile,
    ModelCodeContextEmbeddingContract,
    ModelCodeContextRepositoryScope,
    ModelCodeContextRequest,
    derive_projection_repository_id,
    derive_repository_policy_scope_ref,
)
from omniintelligence.code_projection.context_serving.resolver import (
    CodeProjectionContextArtifactResolver,
)
from omniintelligence.code_projection.qdrant import ModelCodeProjectionSearchHit

TENANT_ID = "12345678-1234-4234-8234-123456789abc"
OTHER_TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REQUEST_ID = "23456789-2345-4345-8345-23456789abcd"
CORRELATION_ID = "3456789a-3456-4456-8456-3456789abcde"
REPOSITORY_ID = "lab/claude-hook-capture/omniintelligence"
REPOSITORY_INSTANCE_ID = "worktree/omn-16068"
PROJECTION_REPOSITORY_ID = derive_projection_repository_id(
    repository_id=REPOSITORY_ID,
    repository_instance_id=REPOSITORY_INSTANCE_ID,
)
PRINCIPAL_ID = "operator:jonah"
POLICY_VERSION = "source-artifact-change-v1-lab-house"
EMBEDDING_MODEL = "text-embedding-qwen3"
EMBEDDING_VERSION = "qwen3-embedding-0.6b-lab-2026-08-14"
QUERY_TEXT = "find the authorization-aware context resolver unique-query-42"
SEMANTIC_CONTENT = (
    b"class CodeProjectionContextArtifactResolver:\n"
    b"    def authorize_request(self, request): ...\n"
)
RAW_SOURCE = b"class CodeProjectionContextArtifactResolver:\n    pass\n"
TRANSFORM_MANIFEST = b'{"extractor":"fixture","version":"1.0.0"}'


@dataclass(frozen=True, slots=True)
class ContextScenario:
    request: ModelCodeContextRequest
    request_bytes: bytes
    profile: ModelCodeContextAuthorizationProfile
    store: CodeProjectionArtifactStore
    resolver: CodeProjectionContextArtifactResolver
    hit: ModelCodeProjectionSearchHit


def build_scenario(
    root: Path,
    *,
    semantic_content: bytes = SEMANTIC_CONTENT,
) -> ContextScenario:
    """Build one fully promoted source and its exact semantic search hit."""

    raw_digest = sha256_hex(RAW_SOURCE)
    semantic_digest = sha256_hex(semantic_content)
    manifest_digest = sha256_hex(TRANSFORM_MANIFEST)
    source = make_code_source(
        tenant_id=TENANT_ID,
        repository_id=PROJECTION_REPOSITORY_ID,
        relative_path=(
            "src/omniintelligence/code_projection/context_serving/resolver.py"
        ),
        source_version=f"sha256:{raw_digest}",
        raw_content_hash_sha256=raw_digest,
        byte_count=len(RAW_SOURCE),
        language="python",
    )
    label = ModelCodeProjectionLabel(
        namespace="responsibility",
        value="authorization",
        confidence_basis_points=10_000,
        producer="context-serving-fixture",
        producer_version="1.0.0",
    )
    span = ModelCodeProjectionSpan(start_line=1, end_line=2)
    node = make_code_node(
        source_id=source.source_id,
        entity_kind="class",
        qualified_name=(
            "omniintelligence.code_projection.context_serving."
            "CodeProjectionContextArtifactResolver"
        ),
        display_name="CodeProjectionContextArtifactResolver",
        symbol_visibility="public",
        source_span=span,
        labels=(label,),
    )
    document = make_code_chunk(
        source_id=source.source_id,
        source_hash_sha256=source.raw_content_hash_sha256,
        chunk_key="symbol:CodeProjectionContextArtifactResolver",
        chunk_kind="symbol",
        anchor_node_id=node.node_id,
        source_span=span,
        chunker_version="syntax-aware-v2",
        sanitized_content_hash_sha256=semantic_digest,
        byte_count=len(semantic_content),
    )
    policy = ModelCodeProjectionPolicy(
        tenant_id=TENANT_ID,
        scope_ref=derive_repository_policy_scope_ref(
            tenant_id=TENANT_ID,
            repository_id=REPOSITORY_ID,
            repository_instance_id=REPOSITORY_INSTANCE_ID,
        ),
        access_scope="repository",
        visibility="repository",
        redaction_state="not_required",
        trust_tier="verified_source",
        retention_class="policy_managed",
        policy_version=POLICY_VERSION,
        metadata_allowlist_version="code-projection-metadata-v2",
    )
    provenance = ModelCodeProjectionProvenance(
        producer="context-serving-fixture",
        producer_version="1.0.0",
        projection_builder_version="2.0.0",
        extractor_name="fixture-extractor",
        extractor_version="1.0.0",
        extractor_config_hash_sha256=sha256_hex(b"fixture-config"),
        transform_manifest_ref=f"artifact://sha256/{manifest_digest}",
        transform_manifest_hash_sha256=manifest_digest,
        labeler_version="fixture-labeler-v1",
        chunker_version="syntax-aware-v2",
    )
    batch = build_code_projection_batch(
        source=source,
        cursor=ModelCodeProjectionCursor(
            authority="context-serving-fixture",
            partition=source.source_id,
            sequence=1,
        ),
        policy=policy,
        provenance=provenance,
        nodes=(node,),
        semantic_documents=(document,),
    )

    store = CodeProjectionArtifactStore(root)
    assert (
        store.stage_content_artifact(TRANSFORM_MANIFEST).content_hash_sha256
        == manifest_digest
    )
    assert (
        store.stage_content_artifact(semantic_content).content_hash_sha256
        == semantic_digest
    )
    staged = store.stage(raw_source=RAW_SOURCE, batch=batch)
    with store.source_lock(source.source_id):
        current = store.mark_applied(staged)
    assert current.batch == batch

    request = ModelCodeContextRequest(
        request_id=REQUEST_ID,
        correlation_id=CORRELATION_ID,
        tenant_id=TENANT_ID,
        repository_id=REPOSITORY_ID,
        repository_instance_id=REPOSITORY_INSTANCE_ID,
        projection_repository_id=PROJECTION_REPOSITORY_ID,
        policy_scope_ref=policy.scope_ref,
        principal_id=PRINCIPAL_ID,
        query_text=QUERY_TEXT,
        candidate_limit=5,
        max_items=3,
        min_score_basis_points=7_000,
        max_context_bytes=24_000,
        max_context_tokens=8_000,
        timeout_ms=2_000,
    )
    profile = ModelCodeContextAuthorizationProfile(
        profile_id="lab-code-context-profile-v1",
        grants=(
            ModelCodeContextAuthorizationGrant(
                principal_id=PRINCIPAL_ID,
                tenant_id=TENANT_ID,
                repository_scopes=(
                    ModelCodeContextRepositoryScope(
                        repository_id=REPOSITORY_ID,
                        repository_instance_id=REPOSITORY_INSTANCE_ID,
                        projection_repository_id=PROJECTION_REPOSITORY_ID,
                        policy_scope_ref=policy.scope_ref,
                    ),
                ),
                allowed_policy_versions=(POLICY_VERSION,),
                allowed_retention_classes=("policy_managed",),
                allowed_embedding_contracts=(
                    ModelCodeContextEmbeddingContract(
                        model=EMBEDDING_MODEL,
                        version=EMBEDDING_VERSION,
                    ),
                ),
                maximum_items=5,
                maximum_context_bytes=32_000,
                maximum_context_tokens=10_000,
            ),
        ),
    )
    hit = ModelCodeProjectionSearchHit(
        point_id="456789ab-4567-4567-8567-456789abcdef",
        score=0.91234,
        tenant_id=TENANT_ID,
        repository_id=PROJECTION_REPOSITORY_ID,
        relative_path=source.relative_path,
        source_id=source.source_id,
        batch_id=batch.batch_id,
        document_id=document.document_id,
        byte_count=document.byte_count,
        content_ref=document.content_ref,
        sanitized_content_hash_sha256=document.sanitized_content_hash_sha256,
        chunk_key=document.chunk_key,
        chunk_kind=document.chunk_kind,
        anchor_node_id=document.anchor_node_id,
        source_span=document.source_span,
        embedding_model=EMBEDDING_MODEL,
        embedding_model_version=EMBEDDING_VERSION,
    )
    resolver = CodeProjectionContextArtifactResolver(
        artifact_store=store,
        authorization_profile=profile,
    )
    request_bytes = serialize_code_context_request(request)
    assert canonical_json_bytes(request.model_dump(mode="json")) == request_bytes
    return ContextScenario(
        request=request,
        request_bytes=request_bytes,
        profile=profile,
        store=store,
        resolver=resolver,
        hit=hit,
    )


__all__ = [
    "CORRELATION_ID",
    "ContextScenario",
    "EMBEDDING_MODEL",
    "EMBEDDING_VERSION",
    "OTHER_TENANT_ID",
    "POLICY_VERSION",
    "PRINCIPAL_ID",
    "PROJECTION_REPOSITORY_ID",
    "QUERY_TEXT",
    "REPOSITORY_ID",
    "REPOSITORY_INSTANCE_ID",
    "REQUEST_ID",
    "SEMANTIC_CONTENT",
    "TENANT_ID",
    "build_scenario",
]
