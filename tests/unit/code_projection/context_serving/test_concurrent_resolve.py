# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-16764: candidates resolve concurrently, with semantics preserved exactly.

`resolve()` is the dominant per-candidate cost -- 20 calls at ~26 ms each, 516 ms
of an 857 ms warm request on the dev lane. The calls are independent of one
another, but the *selection* that consumes them is not: it depends on the
accumulated item list and the running context budget, so selection stays
sequential and only resolution is parallelised.

That split is what makes exact preservation subtle. Today a candidate beyond
`max_items` is never resolved, so a fault inside it never surfaces. Resolving
ahead would surface it and fail a request that previously succeeded. The helper
under test therefore **captures** outcomes rather than raising, and the
sequential selector surfaces one only when it actually reaches that candidate.

`truncated` needs no such care: once the max-items check fires it is already
True, and every later candidate sets it too, so the final value cannot differ.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from omniintelligence.code_projection.context_serving import service as service_module
from omniintelligence.code_projection.context_serving.codec import (
    serialize_code_context_request,
)
from omniintelligence.code_projection.context_serving.exceptions import (
    CodeContextCandidateBudgetError,
    CodeContextIntegrityError,
)
from omniintelligence.code_projection.context_serving.models import (
    ModelAuthorizedCodeContextCandidate,
    ModelCodeContextRequest,
    ModelCodeContextResponse,
)
from omniintelligence.code_projection.context_serving.service import (
    RESOLVE_CONCURRENCY,
    CodeContextProcessor,
)
from omniintelligence.code_projection.qdrant import ModelCodeProjectionSearchHit
from tests.unit.code_projection.context_serving.fixtures import build_scenario
from tests.unit.code_projection.context_serving.test_service import (
    FakeSearch,
)

pytestmark = pytest.mark.unit


class _SlowResolver:
    """Resolver whose calls take real time, so concurrency is observable."""

    authorization_profile_id = "profile-1"
    authorization_profile_payload_sha256 = "0" * 64
    selection_policy_version = "code-context-selection-v1"

    def __init__(self, delay: float, *, fail_on: set[str] | None = None) -> None:
        self._delay = delay
        self._fail_on = fail_on or set()
        self.in_flight = 0
        self.peak_in_flight = 0

    def authorize_request(self, request: object) -> None:
        del request

    async def resolve(
        self,
        *,
        request: object,
        hit: object,
        score_basis_points: int,
    ) -> object:
        del request, score_basis_points
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self._delay)
            point_id = getattr(hit, "point_id", "")
            if point_id in self._fail_on:
                raise CodeContextIntegrityError(f"synthetic fault for {point_id}")
            return f"candidate-for-{point_id}"
        finally:
            self.in_flight -= 1


class _Hit:
    """Minimal stand-in carrying only what the resolve helper reads."""

    def __init__(self, point_id: str) -> None:
        self.point_id = point_id


def _processor(resolver: object) -> CodeContextProcessor:
    return CodeContextProcessor(search=object(), artifact_resolver=resolver)  # type: ignore[arg-type]


def test_resolution_runs_concurrently() -> None:
    """Twelve 50 ms resolves must not take 600 ms."""

    resolver = _SlowResolver(0.05)
    processor = _processor(resolver)
    ranked = tuple((9_000, _Hit(f"point-{n}")) for n in range(12))

    started = time.perf_counter()
    outcomes = asyncio.run(
        processor._resolve_candidates(request=object(), ranked=ranked)  # noqa: SLF001
    )
    elapsed = time.perf_counter() - started

    assert len(outcomes) == 12
    sequential = 12 * 0.05
    assert elapsed < sequential * 0.6, (
        f"{elapsed:.3f}s for 12 concurrent 50ms resolves suggests they ran "
        f"sequentially (sequential would be ~{sequential:.2f}s)"
    )


def test_concurrency_is_bounded() -> None:
    """Unbounded fan-out would hammer the artifact store; the cap must hold."""

    resolver = _SlowResolver(0.02)
    processor = _processor(resolver)
    ranked = tuple((9_000, _Hit(f"point-{n}")) for n in range(40))

    asyncio.run(
        processor._resolve_candidates(request=object(), ranked=ranked)  # noqa: SLF001
    )

    assert resolver.peak_in_flight <= RESOLVE_CONCURRENCY, (
        f"peak in-flight {resolver.peak_in_flight} exceeded the cap "
        f"{RESOLVE_CONCURRENCY}"
    )
    assert resolver.peak_in_flight > 1, "nothing ran concurrently at all"


def test_failures_are_captured_not_raised() -> None:
    """A fault must not escape here -- only the selector decides if it matters.

    This is the whole reason the helper returns outcomes instead of candidates.
    A candidate the selector never reaches must not be able to fail the request,
    which is the behaviour that holds today because it is never resolved.
    """

    resolver = _SlowResolver(0, fail_on={"point-3"})
    processor = _processor(resolver)
    ranked = tuple((9_000, _Hit(f"point-{n}")) for n in range(5))

    outcomes = asyncio.run(
        processor._resolve_candidates(request=object(), ranked=ranked)  # noqa: SLF001
    )

    assert isinstance(outcomes["point-3"], CodeContextIntegrityError)
    for n in (0, 1, 2, 4):
        assert outcomes[f"point-{n}"] == f"candidate-for-point-{n}"


def test_budget_errors_are_captured_distinctly() -> None:
    """`CodeContextCandidateBudgetError` means truncate, not fail."""

    class _BudgetResolver(_SlowResolver):
        async def resolve(self, **kwargs: object) -> object:
            raise CodeContextCandidateBudgetError("over budget")

    processor = _processor(_BudgetResolver(0))
    ranked = ((9_000, _Hit("point-0")),)

    outcomes = asyncio.run(
        processor._resolve_candidates(request=object(), ranked=ranked)  # noqa: SLF001
    )

    assert isinstance(outcomes["point-0"], CodeContextCandidateBudgetError)


def test_cancellation_is_not_swallowed() -> None:
    """The request-level timeout must still be able to cancel resolution."""

    class _HangingResolver(_SlowResolver):
        async def resolve(self, **kwargs: object) -> object:
            await asyncio.sleep(10)
            return "never"

    processor = _processor(_HangingResolver(0))
    ranked = tuple((9_000, _Hit(f"point-{n}")) for n in range(3))

    async def run_with_timeout() -> None:
        async with asyncio.timeout(0.05):
            await processor._resolve_candidates(  # noqa: SLF001
                request=object(), ranked=ranked
            )

    with pytest.raises(TimeoutError):
        asyncio.run(run_with_timeout())


class _PerHitResolver:
    """Resolver that answers each hit with a candidate matching *that* hit.

    `FakeResolver` in `test_service` returns one fixed candidate, which only
    satisfies `_require_candidate_matches_request` for a single hit. Varying
    `point_id` and `document_id` together on both sides keeps every identity
    and digest check satisfied while giving the ranker distinct candidates.
    """

    authorization_profile_id = "lab-code-context-profile-v1"
    selection_policy_version = "code-context-selection-v1"

    def __init__(
        self,
        candidate: ModelAuthorizedCodeContextCandidate,
        *,
        authorization_profile_payload_sha256: str,
    ) -> None:
        self._candidate = candidate
        self.authorization_profile_payload_sha256 = authorization_profile_payload_sha256
        self.resolve_calls = 0

    def authorize_request(self, request: ModelCodeContextRequest) -> None:
        del request

    async def resolve(
        self,
        *,
        request: ModelCodeContextRequest,
        hit: ModelCodeProjectionSearchHit,
        score_basis_points: int,
    ) -> ModelAuthorizedCodeContextCandidate:
        del request
        self.resolve_calls += 1
        return self._candidate.model_copy(
            update={
                "score_basis_points": score_basis_points,
                "point_id": hit.point_id,
                "document_id": hit.document_id,
            }
        )


async def _fanned_scenario(
    tmp_path: Path,
    *,
    hit_count: int,
) -> tuple[bytes, tuple[ModelCodeProjectionSearchHit, ...], _PerHitResolver]:
    """One fixture source fanned out into `hit_count` distinct ranked hits."""

    scenario = build_scenario(tmp_path)
    candidate = await scenario.resolver.resolve(
        request=scenario.request,
        hit=scenario.hit,
        score_basis_points=9_123,
    )
    hits = tuple(
        scenario.hit.model_copy(
            update={
                "point_id": f"{scenario.hit.point_id[:-2]}{n:02d}",
                "document_id": f"{scenario.hit.document_id[:-2]}{n:02d}",
                # Descending, so ranked order is the construction order.
                "score": 0.95 - (n / 1_000),
            }
        )
        for n in range(hit_count)
    )
    request_bytes = serialize_code_context_request(
        scenario.request.model_copy(
            update={"candidate_limit": hit_count, "max_items": 3}
        )
    )
    resolver = _PerHitResolver(
        candidate,
        authorization_profile_payload_sha256=(
            scenario.resolver.authorization_profile_payload_sha256
        ),
    )
    return request_bytes, hits, resolver


@pytest.mark.asyncio
async def test_resolution_does_not_run_ahead_of_what_selection_needs(
    tmp_path: Path,
) -> None:
    """Twelve candidates, three wanted: resolve three, not twelve.

    Resolving every eligible candidate up front would parallelise the latency
    but quadruple the artifact reads -- a real cost regression in the very
    subsystem this ticket is relieving. Resolution therefore proceeds in waves
    of `max_items`, and with no budget rejections one wave is enough.
    """

    request_bytes, hits, resolver = await _fanned_scenario(tmp_path, hit_count=12)
    processor = CodeContextProcessor(
        search=FakeSearch(hits), artifact_resolver=resolver
    )

    response_bytes = await processor.process(request_bytes)

    assert resolver.resolve_calls == 3, (
        f"resolved {resolver.resolve_calls} candidates to select 3; resolution "
        "ran ahead of selection"
    )
    response = ModelCodeContextResponse.model_validate_json(response_bytes, strict=True)
    assert len(response.pack.items) == 3
    assert response.pack.truncated is True


@pytest.mark.asyncio
async def test_concurrent_and_sequential_responses_are_byte_identical(
    tmp_path: Path,
) -> None:
    """The response bytes are the contract; concurrency must not perturb them.

    The sequential comparison is rebuilt here rather than trusted: the same
    processor is driven with the resolve concurrency pinned to 1, which makes
    the waves degenerate to the original one-at-a-time order.
    """

    request_bytes, hits, resolver = await _fanned_scenario(tmp_path, hit_count=8)
    concurrent = await CodeContextProcessor(
        search=FakeSearch(hits), artifact_resolver=resolver
    ).process(request_bytes)

    _, _, serial_resolver = await _fanned_scenario(tmp_path, hit_count=8)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(service_module, "RESOLVE_CONCURRENCY", 1)
        serial = await CodeContextProcessor(
            search=FakeSearch(hits), artifact_resolver=serial_resolver
        ).process(request_bytes)

    assert concurrent == serial
    assert resolver.resolve_calls == serial_resolver.resolve_calls
