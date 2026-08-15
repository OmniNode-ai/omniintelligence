# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Shared-request fake/real dependency and serving-integrity proofs."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Literal

import pytest

from omniintelligence.code_projection._canonical import canonical_json_bytes, sha256_hex
from omniintelligence.code_projection.context_serving.codec import serialize_pack_body
from omniintelligence.code_projection.context_serving.exceptions import (
    CodeContextAuthorizationError,
    CodeContextIntegrityError,
    CodeContextTimeoutError,
)
from omniintelligence.code_projection.context_serving.models import (
    ModelAuthorizedCodeContextCandidate,
    ModelCodeContextRequest,
    ModelCodeContextResponse,
    derive_projection_repository_id,
    derive_repository_policy_scope_ref,
)
from omniintelligence.code_projection.context_serving.resolver import (
    CodeProjectionContextArtifactResolver,
)
from omniintelligence.code_projection.context_serving.service import (
    CodeContextProcessor,
)
from omniintelligence.code_projection.qdrant import ModelCodeProjectionSearchHit
from tests.unit.code_projection.context_serving.fixtures import (
    OTHER_TENANT_ID,
    QUERY_TEXT,
    REPOSITORY_ID,
    SEMANTIC_CONTENT,
    TENANT_ID,
    ContextScenario,
    build_scenario,
)

pytestmark = pytest.mark.unit


class FakeSearch:
    def __init__(
        self,
        hits: tuple[ModelCodeProjectionSearchHit, ...],
        *,
        delay_seconds: float = 0,
    ) -> None:
        self.hits = hits
        self.delay_seconds = delay_seconds
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        *,
        query_text: str,
        tenant_id: str,
        repository_id: str | None = None,
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> tuple[ModelCodeProjectionSearchHit, ...]:
        self.calls.append(
            {
                "limit": limit,
                "query_text": query_text,
                "repository_id": repository_id,
                "score_threshold": score_threshold,
                "tenant_id": tenant_id,
            }
        )
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return self.hits


class FakeResolver:
    authorization_profile_id: str = "lab-code-context-profile-v1"
    authorization_profile_payload_sha256: str = "0" * 64
    selection_policy_version: Literal["code-context-selection-v1"] = (
        "code-context-selection-v1"
    )

    def __init__(
        self,
        candidate: ModelAuthorizedCodeContextCandidate,
        *,
        tenant_id: str = TENANT_ID,
        authorization_profile_payload_sha256: str | None = None,
    ) -> None:
        self.candidate = candidate
        self.tenant_id = tenant_id
        if authorization_profile_payload_sha256 is not None:
            self.authorization_profile_payload_sha256 = (
                authorization_profile_payload_sha256
            )
        self.authorize_calls = 0
        self.resolve_calls = 0

    def authorize_request(self, request: ModelCodeContextRequest) -> None:
        self.authorize_calls += 1
        if request.tenant_id != self.tenant_id:
            raise CodeContextAuthorizationError("fake request is unauthorized")

    async def resolve(
        self,
        *,
        request: ModelCodeContextRequest,
        hit: ModelCodeProjectionSearchHit,
        score_basis_points: int,
    ) -> ModelAuthorizedCodeContextCandidate:
        del request, hit
        self.resolve_calls += 1
        return self.candidate.model_copy(
            update={"score_basis_points": score_basis_points}
        )


async def _resolved_candidate(
    tmp_path: Path,
) -> tuple[ContextScenario, ModelAuthorizedCodeContextCandidate]:
    scenario = build_scenario(tmp_path)
    candidate = await scenario.resolver.resolve(
        request=scenario.request,
        hit=scenario.hit,
        score_basis_points=9_123,
    )
    return scenario, candidate


@pytest.mark.asyncio
async def test_exact_request_bytes_produce_identical_fake_and_real_resolver_output(
    tmp_path: Path,
) -> None:
    scenario, candidate = await _resolved_candidate(tmp_path)
    fake_search = FakeSearch((scenario.hit,))
    fake_resolver = FakeResolver(
        candidate,
        authorization_profile_payload_sha256=(
            scenario.resolver.authorization_profile_payload_sha256
        ),
    )
    fake_processor = CodeContextProcessor(
        search=fake_search,
        artifact_resolver=fake_resolver,
    )
    real_processor = CodeContextProcessor(
        search=FakeSearch((scenario.hit,)),
        artifact_resolver=scenario.resolver,
    )

    fake_response = await fake_processor.process(scenario.request_bytes)
    real_response = await real_processor.process(scenario.request_bytes)

    assert fake_response == real_response
    assert fake_search.calls == [
        {
            "limit": 5,
            "query_text": QUERY_TEXT,
            "repository_id": scenario.request.projection_repository_id,
            "score_threshold": 0.7,
            "tenant_id": TENANT_ID,
        }
    ]
    assert fake_resolver.authorize_calls == 1
    assert fake_resolver.resolve_calls == 1

    response = ModelCodeContextResponse.model_validate_json(fake_response, strict=True)
    assert response.pack.query_sha256 == sha256_hex(QUERY_TEXT.encode())
    assert response.pack.request_payload_sha256 == sha256_hex(scenario.request_bytes)
    assert response.pack.authorization_profile_payload_sha256 == (
        scenario.resolver.authorization_profile_payload_sha256
    )
    assert response.pack.items[0].content.encode() == SEMANTIC_CONTENT
    assert response.pack.items[0].labels[0].value == "authorization"
    assert response.pack.items[0].policy.retention_class == "policy_managed"
    assert response.pack.repository_id == scenario.request.repository_id
    assert (
        response.pack.repository_instance_id == scenario.request.repository_instance_id
    )
    assert (
        response.pack.projection_repository_id
        == scenario.request.projection_repository_id
    )
    assert response.pack.items[0].policy_scope_ref == scenario.request.policy_scope_ref
    assert response.pack_payload_sha256 == (
        f"sha256:{sha256_hex(serialize_pack_body(response.pack))}"
    )
    generation_bytes = response.generation.context_pack.encode()
    assert response.generation.context_pack_hash == (
        f"sha256:{sha256_hex(generation_bytes)}"
    )
    assert QUERY_TEXT.encode() not in fake_response
    assert json.loads(generation_bytes)["query_sha256"] == response.pack.query_sha256


@pytest.mark.asyncio
async def test_authorization_rejects_before_query_reaches_search(
    tmp_path: Path,
) -> None:
    scenario = build_scenario(tmp_path)
    request = scenario.request.model_copy(
        update={
            "tenant_id": OTHER_TENANT_ID,
            "policy_scope_ref": derive_repository_policy_scope_ref(
                tenant_id=OTHER_TENANT_ID,
                repository_id=scenario.request.repository_id,
                repository_instance_id=scenario.request.repository_instance_id,
            ),
        }
    )
    payload = canonical_json_bytes(request.model_dump(mode="json"))
    search = FakeSearch((scenario.hit,))
    processor = CodeContextProcessor(
        search=search,
        artifact_resolver=scenario.resolver,
    )

    with pytest.raises(CodeContextAuthorizationError):
        await processor.process(payload)

    assert search.calls == []


@pytest.mark.asyncio
async def test_logical_repository_grant_cannot_mix_checkout_instances(
    tmp_path: Path,
) -> None:
    scenario = build_scenario(tmp_path)
    canonical_instance = "canonical"
    request = scenario.request.model_copy(
        update={
            "repository_instance_id": canonical_instance,
            "projection_repository_id": derive_projection_repository_id(
                repository_id=REPOSITORY_ID,
                repository_instance_id=canonical_instance,
            ),
            "policy_scope_ref": derive_repository_policy_scope_ref(
                tenant_id=TENANT_ID,
                repository_id=REPOSITORY_ID,
                repository_instance_id=canonical_instance,
            ),
        }
    )
    payload = canonical_json_bytes(request.model_dump(mode="json"))
    search = FakeSearch((scenario.hit,))
    processor = CodeContextProcessor(
        search=search,
        artifact_resolver=scenario.resolver,
    )

    with pytest.raises(CodeContextAuthorizationError):
        await processor.process(payload)

    assert request.repository_id == scenario.request.repository_id
    assert request.projection_repository_id != scenario.request.projection_repository_id
    assert search.calls == []


@pytest.mark.asyncio
async def test_cross_tenant_or_tampered_hit_fails_closed(tmp_path: Path) -> None:
    scenario = build_scenario(tmp_path)
    cross_tenant = scenario.hit.model_copy(update={"tenant_id": OTHER_TENANT_ID})
    tampered = scenario.hit.model_copy(
        update={
            "sanitized_content_hash_sha256": "0" * 64,
            "content_ref": f"artifact://sha256/{'0' * 64}",
        }
    )
    wrong_instance = scenario.hit.model_copy(update={"repository_id": REPOSITORY_ID})

    for hit in (cross_tenant, tampered, wrong_instance):
        processor = CodeContextProcessor(
            search=FakeSearch((hit,)),
            artifact_resolver=scenario.resolver,
        )
        with pytest.raises(CodeContextIntegrityError):
            await processor.process(scenario.request_bytes)


@pytest.mark.asyncio
async def test_injected_resolver_cannot_return_another_checkout_instance(
    tmp_path: Path,
) -> None:
    scenario, candidate = await _resolved_candidate(tmp_path)
    canonical_instance = "canonical"
    wrong_instance_candidate = candidate.model_copy(
        update={
            "repository_instance_id": canonical_instance,
            "projection_repository_id": derive_projection_repository_id(
                repository_id=REPOSITORY_ID,
                repository_instance_id=canonical_instance,
            ),
            "policy_scope_ref": derive_repository_policy_scope_ref(
                tenant_id=TENANT_ID,
                repository_id=REPOSITORY_ID,
                repository_instance_id=canonical_instance,
            ),
        }
    )
    processor = CodeContextProcessor(
        search=FakeSearch((scenario.hit,)),
        artifact_resolver=FakeResolver(wrong_instance_candidate),
    )

    with pytest.raises(CodeContextIntegrityError):
        await processor.process(scenario.request_bytes)


@pytest.mark.asyncio
async def test_injected_resolver_cannot_hide_mismatched_embedded_policy(
    tmp_path: Path,
) -> None:
    scenario, candidate = await _resolved_candidate(tmp_path)
    mismatched_policy = candidate.policy.model_copy(
        update={
            "scope_ref": derive_repository_policy_scope_ref(
                tenant_id=TENANT_ID,
                repository_id=REPOSITORY_ID,
                repository_instance_id="canonical",
            )
        }
    )
    mismatched_candidate = candidate.model_copy(update={"policy": mismatched_policy})
    processor = CodeContextProcessor(
        search=FakeSearch((scenario.hit,)),
        artifact_resolver=FakeResolver(mismatched_candidate),
    )

    with pytest.raises(CodeContextIntegrityError):
        await processor.process(scenario.request_bytes)


@pytest.mark.asyncio
async def test_injected_resolver_cannot_forge_content_under_an_artifact_digest(
    tmp_path: Path,
) -> None:
    scenario, candidate = await _resolved_candidate(tmp_path)
    forged_candidate = candidate.model_copy(update={"content": "forged source text"})
    processor = CodeContextProcessor(
        search=FakeSearch((scenario.hit,)),
        artifact_resolver=FakeResolver(forged_candidate),
    )

    with pytest.raises(CodeContextIntegrityError):
        await processor.process(scenario.request_bytes)


@pytest.mark.asyncio
async def test_ticket_retention_requires_an_explicit_policy_managed_grant(
    tmp_path: Path,
) -> None:
    scenario = build_scenario(tmp_path)
    grant = scenario.profile.grants[0].model_copy(
        update={"allowed_retention_classes": ("source_controlled",)}
    )
    profile = scenario.profile.model_copy(update={"grants": (grant,)})
    resolver = CodeProjectionContextArtifactResolver(
        artifact_store=scenario.store,
        authorization_profile=profile,
    )
    processor = CodeContextProcessor(
        search=FakeSearch((scenario.hit,)),
        artifact_resolver=resolver,
    )

    with pytest.raises(CodeContextAuthorizationError):
        await processor.process(scenario.request_bytes)


@pytest.mark.asyncio
async def test_budget_excludes_oversized_item_without_partial_content(
    tmp_path: Path,
) -> None:
    scenario, candidate = await _resolved_candidate(tmp_path)
    request = scenario.request.model_copy(
        update={"max_context_bytes": 1_024, "max_context_tokens": 512}
    )
    payload = canonical_json_bytes(request.model_dump(mode="json"))
    processor = CodeContextProcessor(
        search=FakeSearch((scenario.hit,)),
        artifact_resolver=FakeResolver(candidate),
    )

    response_bytes = await processor.process(payload)
    response = ModelCodeContextResponse.model_validate_json(
        response_bytes,
        strict=True,
    )

    assert response.pack.items == ()
    assert response.pack.truncated is True
    assert response.generation.context_artifacts == ()
    assert response.pack.total_context_bytes <= request.max_context_bytes
    assert response.pack.total_context_tokens <= request.max_context_tokens


@pytest.mark.asyncio
async def test_request_byte_budget_excludes_hit_before_resolver_read(
    tmp_path: Path,
) -> None:
    scenario = build_scenario(tmp_path, semantic_content=b"x" * 2_048)
    candidate = await scenario.resolver.resolve(
        request=scenario.request,
        hit=scenario.hit,
        score_basis_points=9_123,
    )
    request = scenario.request.model_copy(
        update={"max_context_bytes": 1_024, "max_context_tokens": 512}
    )
    payload = canonical_json_bytes(request.model_dump(mode="json"))
    resolver = FakeResolver(candidate)
    processor = CodeContextProcessor(
        search=FakeSearch((scenario.hit,)),
        artifact_resolver=resolver,
    )

    response = ModelCodeContextResponse.model_validate_json(
        await processor.process(payload),
        strict=True,
    )

    assert response.pack.items == ()
    assert response.pack.truncated is True
    assert resolver.resolve_calls == 0


@pytest.mark.asyncio
async def test_hard_timeout_never_echoes_query(tmp_path: Path) -> None:
    scenario = build_scenario(tmp_path)
    request = scenario.request.model_copy(update={"timeout_ms": 50})
    payload = canonical_json_bytes(request.model_dump(mode="json"))
    processor = CodeContextProcessor(
        search=FakeSearch((scenario.hit,), delay_seconds=0.2),
        artifact_resolver=scenario.resolver,
    )

    with pytest.raises(CodeContextTimeoutError) as raised:
        await processor.process(payload)

    assert QUERY_TEXT not in str(raised.value)
