# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Single exact-byte processor shared by unit fakes and live lab adapters."""

from __future__ import annotations

import asyncio
import math
from decimal import ROUND_HALF_EVEN, Decimal

from omniintelligence.code_projection._canonical import canonical_json_bytes, sha256_hex
from omniintelligence.code_projection.context_serving.codec import (
    parse_code_context_request,
    serialize_code_context_response,
    serialize_pack_body,
)
from omniintelligence.code_projection.context_serving.exceptions import (
    CodeContextCandidateBudgetError,
    CodeContextError,
    CodeContextIntegrityError,
    CodeContextSearchError,
    CodeContextTimeoutError,
)
from omniintelligence.code_projection.context_serving.models import (
    CODE_CONTEXT_SCHEMA_VERSION,
    ModelAuthorizedCodeContextCandidate,
    ModelCodeContextItem,
    ModelCodeContextPackBody,
    ModelCodeContextRequest,
    ModelCodeContextResponse,
    ModelGenerationContextArtifact,
    ModelGenerationContextBoundary,
)
from omniintelligence.code_projection.context_serving.protocols import (
    ProtocolCodeContextArtifactResolver,
    ProtocolCodeContextSearch,
)
from omniintelligence.code_projection.qdrant import ModelCodeProjectionSearchHit
from omniintelligence.utils.util_token_counter import count_tokens


class TiktokenCodeContextTokenCounter:
    """Canonical cl100k_base counter advertised in the v1 response contract."""

    def count(self, text: str) -> int:
        """Count the selected generation text deterministically."""

        return count_tokens(text)


def _score_basis_points(score: float) -> int:
    if not math.isfinite(score):
        raise CodeContextIntegrityError("search hit score is not finite")
    return int(
        (Decimal(str(score)) * Decimal(10_000)).to_integral_value(
            rounding=ROUND_HALF_EVEN
        )
    )


def _item(
    candidate: ModelAuthorizedCodeContextCandidate,
    *,
    rank: int,
    token_counter: TiktokenCodeContextTokenCounter,
) -> ModelCodeContextItem:
    return ModelCodeContextItem(
        rank=rank,
        score_basis_points=candidate.score_basis_points,
        tenant_id=candidate.tenant_id,
        repository_id=candidate.repository_id,
        repository_instance_id=candidate.repository_instance_id,
        projection_repository_id=candidate.projection_repository_id,
        policy_scope_ref=candidate.policy_scope_ref,
        relative_path=candidate.relative_path,
        source_id=candidate.source_id,
        source_hash_sha256=candidate.source_hash_sha256,
        source_artifact_ref=candidate.source_artifact_ref,
        batch_id=candidate.batch_id,
        batch_content_hash_sha256=candidate.batch_content_hash_sha256,
        cursor_sequence=candidate.cursor_sequence,
        document_id=candidate.document_id,
        content_ref=candidate.content_ref,
        sanitized_content_hash_sha256=candidate.sanitized_content_hash_sha256,
        chunk_key=candidate.chunk_key,
        chunk_kind=candidate.chunk_kind,
        anchor_node_id=candidate.anchor_node_id,
        source_span=candidate.source_span,
        labels=candidate.labels,
        embedding_model=candidate.embedding_model,
        embedding_model_version=candidate.embedding_model_version,
        policy=candidate.policy,
        policy_payload_sha256=candidate.policy_payload_sha256,
        provenance=candidate.provenance,
        provenance_payload_sha256=candidate.provenance_payload_sha256,
        content=candidate.content,
        content_byte_count=len(candidate.content.encode("utf-8")),
        token_estimate=token_counter.count(candidate.content),
    )


def _render_generation_context(
    *,
    request: ModelCodeContextRequest,
    request_payload_sha256: str,
    query_sha256: str,
    authorization_profile_id: str,
    authorization_profile_payload_sha256: str,
    selection_policy_version: str,
    items: tuple[ModelCodeContextItem, ...],
) -> str:
    payload = {
        "kind": "omninode_code_context",
        "schema_version": CODE_CONTEXT_SCHEMA_VERSION,
        "request_id": request.request_id,
        "request_payload_sha256": request_payload_sha256,
        "query_sha256": query_sha256,
        "authorization_profile_id": authorization_profile_id,
        "authorization_profile_payload_sha256": (authorization_profile_payload_sha256),
        "selection_policy_version": selection_policy_version,
        "repository_id": request.repository_id,
        "repository_instance_id": request.repository_instance_id,
        "projection_repository_id": request.projection_repository_id,
        "policy_scope_ref": request.policy_scope_ref,
        "tenant_id": request.tenant_id,
        "items": [item.model_dump(mode="json") for item in items],
    }
    return canonical_json_bytes(payload).decode("utf-8")


def _ranked_hits(
    hits: tuple[ModelCodeProjectionSearchHit, ...],
    *,
    request: ModelCodeContextRequest,
) -> tuple[tuple[int, ModelCodeProjectionSearchHit], ...]:
    if any(hit.tenant_id != request.tenant_id for hit in hits):
        raise CodeContextIntegrityError("search returned a cross-tenant candidate")
    if any(hit.repository_id != request.projection_repository_id for hit in hits):
        raise CodeContextIntegrityError(
            "search returned a cross-instance projection candidate"
        )
    scored = tuple((_score_basis_points(hit.score), hit) for hit in hits)
    point_ids = tuple(hit.point_id for _, hit in scored)
    document_ids = tuple(hit.document_id for _, hit in scored)
    if len(set(point_ids)) != len(point_ids):
        raise CodeContextIntegrityError("search returned duplicate point identities")
    if len(set(document_ids)) != len(document_ids):
        raise CodeContextIntegrityError("search returned duplicate document identities")
    return tuple(
        sorted(
            scored,
            key=lambda scored_hit: (
                -scored_hit[0],
                scored_hit[1].document_id,
                scored_hit[1].point_id,
            ),
        )
    )


def _require_candidate_matches_request(
    *,
    request: ModelCodeContextRequest,
    hit: ModelCodeProjectionSearchHit,
    candidate: ModelAuthorizedCodeContextCandidate,
    score_basis_points: int,
) -> None:
    if (
        candidate.tenant_id != request.tenant_id
        or candidate.repository_id != request.repository_id
        or candidate.repository_instance_id != request.repository_instance_id
        or candidate.projection_repository_id != request.projection_repository_id
        or candidate.policy_scope_ref != request.policy_scope_ref
        or candidate.policy.tenant_id != request.tenant_id
        or candidate.policy.scope_ref != request.policy_scope_ref
    ):
        raise CodeContextIntegrityError(
            "artifact resolver returned content outside the requested instance"
        )
    content_bytes = candidate.content.encode("utf-8")
    if (
        candidate.point_id != hit.point_id
        or candidate.score_basis_points != score_basis_points
        or candidate.projection_repository_id != hit.repository_id
        or candidate.relative_path != hit.relative_path
        or candidate.source_id != hit.source_id
        or candidate.batch_id != hit.batch_id
        or candidate.document_id != hit.document_id
        or candidate.content_ref != hit.content_ref
        or candidate.sanitized_content_hash_sha256 != hit.sanitized_content_hash_sha256
        or candidate.chunk_key != hit.chunk_key
        or candidate.chunk_kind != hit.chunk_kind
        or candidate.anchor_node_id != hit.anchor_node_id
        or candidate.source_span != hit.source_span
        or candidate.embedding_model != hit.embedding_model
        or candidate.embedding_model_version != hit.embedding_model_version
        or len(content_bytes) != hit.byte_count
    ):
        raise CodeContextIntegrityError(
            "artifact resolver result does not match its search candidate"
        )
    if (
        candidate.source_artifact_ref
        != f"artifact://sha256/{candidate.source_hash_sha256}"
        or candidate.content_ref
        != f"artifact://sha256/{candidate.sanitized_content_hash_sha256}"
        or sha256_hex(content_bytes) != candidate.sanitized_content_hash_sha256
        or sha256_hex(canonical_json_bytes(candidate.policy.model_dump(mode="json")))
        != candidate.policy_payload_sha256
        or sha256_hex(
            canonical_json_bytes(candidate.provenance.model_dump(mode="json"))
        )
        != candidate.provenance_payload_sha256
    ):
        raise CodeContextIntegrityError(
            "artifact resolver returned inconsistent content or provenance digests"
        )


class CodeContextProcessor:
    """Process canonical bytes through explicitly injected serving dependencies."""

    def __init__(
        self,
        *,
        search: ProtocolCodeContextSearch,
        artifact_resolver: ProtocolCodeContextArtifactResolver,
    ) -> None:
        self._search = search
        self._artifact_resolver = artifact_resolver
        self._token_counter = TiktokenCodeContextTokenCounter()

    async def process(self, request_payload: bytes) -> bytes:
        """Return a canonical bounded context response for exact request bytes."""

        request = parse_code_context_request(request_payload)
        request_payload_sha256 = sha256_hex(request_payload)
        query_sha256 = sha256_hex(request.query_text.encode("utf-8"))
        self._artifact_resolver.authorize_request(request)

        try:
            async with asyncio.timeout(request.timeout_ms / 1000):
                try:
                    hits = await self._search.search(
                        query_text=request.query_text,
                        tenant_id=request.tenant_id,
                        repository_id=request.projection_repository_id,
                        limit=request.candidate_limit,
                        score_threshold=request.min_score_basis_points / 10_000,
                    )
                except CodeContextError:
                    raise
                except Exception as exc:
                    raise CodeContextSearchError(
                        "context search dependency failed"
                    ) from exc
                if len(hits) > request.candidate_limit:
                    raise CodeContextIntegrityError(
                        "search returned more candidates than requested"
                    )

                ranked = _ranked_hits(hits, request=request)
                selected: list[ModelCodeContextItem] = []
                truncated = False
                for score_basis_points, hit in ranked:
                    if score_basis_points < request.min_score_basis_points:
                        truncated = True
                        continue
                    if len(selected) >= request.max_items:
                        truncated = True
                        continue
                    if hit.byte_count > request.max_context_bytes:
                        truncated = True
                        continue
                    try:
                        candidate = await self._artifact_resolver.resolve(
                            request=request,
                            hit=hit,
                            score_basis_points=score_basis_points,
                        )
                    except CodeContextCandidateBudgetError:
                        truncated = True
                        continue
                    _require_candidate_matches_request(
                        request=request,
                        hit=hit,
                        candidate=candidate,
                        score_basis_points=score_basis_points,
                    )
                    proposed = _item(
                        candidate,
                        rank=len(selected) + 1,
                        token_counter=self._token_counter,
                    )
                    proposed_items = (*selected, proposed)
                    proposed_context = _render_generation_context(
                        request=request,
                        request_payload_sha256=request_payload_sha256,
                        query_sha256=query_sha256,
                        authorization_profile_id=(
                            self._artifact_resolver.authorization_profile_id
                        ),
                        authorization_profile_payload_sha256=(
                            self._artifact_resolver.authorization_profile_payload_sha256
                        ),
                        selection_policy_version=(
                            self._artifact_resolver.selection_policy_version
                        ),
                        items=proposed_items,
                    )
                    if (
                        len(proposed_context.encode("utf-8"))
                        > request.max_context_bytes
                        or self._token_counter.count(proposed_context)
                        > request.max_context_tokens
                    ):
                        truncated = True
                        continue
                    selected.append(proposed)
        except TimeoutError as exc:
            raise CodeContextTimeoutError(
                "code-context request exceeded its hard timeout"
            ) from exc

        items = tuple(selected)
        generation_text = _render_generation_context(
            request=request,
            request_payload_sha256=request_payload_sha256,
            query_sha256=query_sha256,
            authorization_profile_id=(self._artifact_resolver.authorization_profile_id),
            authorization_profile_payload_sha256=(
                self._artifact_resolver.authorization_profile_payload_sha256
            ),
            selection_policy_version=(self._artifact_resolver.selection_policy_version),
            items=items,
        )
        generation_bytes = generation_text.encode("utf-8")
        generation_tokens = self._token_counter.count(generation_text)
        if (
            len(generation_bytes) > request.max_context_bytes
            or generation_tokens > request.max_context_tokens
        ):
            raise CodeContextIntegrityError(
                "empty context envelope exceeds the authorized budget"
            )

        pack = ModelCodeContextPackBody(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            request_payload_sha256=request_payload_sha256,
            query_sha256=query_sha256,
            tenant_id=request.tenant_id,
            repository_id=request.repository_id,
            repository_instance_id=request.repository_instance_id,
            projection_repository_id=request.projection_repository_id,
            policy_scope_ref=request.policy_scope_ref,
            principal_id=request.principal_id,
            authorization_profile_id=(self._artifact_resolver.authorization_profile_id),
            authorization_profile_payload_sha256=(
                self._artifact_resolver.authorization_profile_payload_sha256
            ),
            selection_policy_version=(self._artifact_resolver.selection_policy_version),
            candidates_considered=len(hits),
            truncated=truncated,
            items=items,
            total_content_bytes=sum(item.content_byte_count for item in items),
            total_context_bytes=len(generation_bytes),
            total_context_tokens=generation_tokens,
        )
        pack_digest = sha256_hex(serialize_pack_body(pack))
        generation_digest = sha256_hex(generation_bytes)
        generation = ModelGenerationContextBoundary(
            context_pack=generation_text,
            context_artifacts=tuple(
                ModelGenerationContextArtifact(
                    content=item.content,
                    source_ref=item.content_ref,
                    content_hash=f"sha256:{item.sanitized_content_hash_sha256}",
                )
                for item in items
            ),
            context_pack_hash=f"sha256:{generation_digest}",
        )
        response = ModelCodeContextResponse(
            pack=pack,
            pack_payload_sha256=f"sha256:{pack_digest}",
            generation=generation,
        )
        return serialize_code_context_response(response)


__all__ = ["CodeContextProcessor", "TiktokenCodeContextTokenCounter"]
