# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-16764: the generation-context render must not re-dump selected items.

`_render_generation_context` is called once per candidate inside the selection
loop, and each call serialised *every* already-selected item again. Selecting n
items therefore performed n(n+1)/2 model dumps where n would do. Measured on the
dev lane, sweeping `max_items` 1 -> 10 grew assembly 17x where linear would be
10x.

The fix builds each item's canonical payload once, when the item is built, and
passes payloads to the render instead of models.

Scope note: this addresses the *serialisation* half only. The budget check also
tokenises the whole accumulated context each iteration, and BPE merges can span
item boundaries, so token counts do not decompose into per-item sums. That cost
stays quadratic and is deliberately left alone -- a decomposed approximation
would make the token budget wrong, which is a correctness cost paid for latency.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from omniintelligence.code_projection.context_serving import service as service_module
from omniintelligence.code_projection.context_serving.models import (
    ModelCodeContextRequest,
)
from tests.unit.code_projection.context_serving.fixtures import build_scenario

pytestmark = pytest.mark.unit


@pytest.fixture
def request_model(tmp_path: Path) -> ModelCodeContextRequest:
    """One canonical request from the shared context-serving fixtures."""

    return build_scenario(tmp_path).request


def test_render_takes_prebuilt_payloads_not_models() -> None:
    """Taking models here is what re-introduces the per-candidate re-dump."""

    signature = inspect.signature(service_module._render_generation_context)  # noqa: SLF001
    assert "item_payloads" in signature.parameters, (
        "_render_generation_context must accept pre-serialised item payloads so "
        "the selection loop does not re-dump every selected item per candidate"
    )
    assert "items" not in signature.parameters


def test_render_performs_no_model_dumps(request_model: ModelCodeContextRequest) -> None:
    """Given payloads, the render serialises nothing -- that is the whole point."""

    dumps = 0
    original = service_module.ModelCodeContextItem.model_dump

    def counting_dump(self: object, *args: object, **kwargs: object) -> object:
        nonlocal dumps
        dumps += 1
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    service_module.ModelCodeContextItem.model_dump = counting_dump  # type: ignore[method-assign]
    try:
        for count in (1, 5, 20):
            dumps = 0
            service_module._render_generation_context(  # noqa: SLF001
                request=request_model,
                request_payload_sha256="a" * 64,
                query_sha256="b" * 64,
                authorization_profile_id="profile-1",
                authorization_profile_payload_sha256="c" * 64,
                selection_policy_version="code-context-selection-v1",
                item_payloads=tuple({"rank": n} for n in range(count)),
            )
            assert dumps == 0, (
                f"rendering {count} items performed {dumps} model dumps; the "
                "payloads should already be built"
            )
    finally:
        service_module.ModelCodeContextItem.model_dump = original  # type: ignore[method-assign]


def test_rendered_bytes_are_unchanged_by_the_refactor(
    request_model: ModelCodeContextRequest,
) -> None:
    """The payload shape the render emits must be byte-identical to before.

    Reconstructed here rather than trusted: the same envelope, built the old way
    with an inline list comprehension over item dumps, must equal what the new
    signature produces from those same dumps.
    """

    from omniintelligence.code_projection._canonical import canonical_json_bytes
    from omniintelligence.code_projection.context_serving.models import (
        CODE_CONTEXT_SCHEMA_VERSION,
    )

    request = request_model
    payloads = tuple({"rank": n, "content": f"item-{n}"} for n in range(3))

    expected = canonical_json_bytes(
        {
            "kind": "omninode_code_context",
            "schema_version": CODE_CONTEXT_SCHEMA_VERSION,
            "request_id": request.request_id,
            "request_payload_sha256": "a" * 64,
            "query_sha256": "b" * 64,
            "authorization_profile_id": "profile-1",
            "authorization_profile_payload_sha256": "c" * 64,
            "selection_policy_version": "code-context-selection-v1",
            "repository_id": request.repository_id,
            "repository_instance_id": request.repository_instance_id,
            "projection_repository_id": request.projection_repository_id,
            "policy_scope_ref": request.policy_scope_ref,
            "tenant_id": request.tenant_id,
            "items": list(payloads),
        }
    ).decode("utf-8")

    actual = service_module._render_generation_context(  # noqa: SLF001
        request=request,
        request_payload_sha256="a" * 64,
        query_sha256="b" * 64,
        authorization_profile_id="profile-1",
        authorization_profile_payload_sha256="c" * 64,
        selection_policy_version="code-context-selection-v1",
        item_payloads=payloads,
    )

    assert actual == expected
