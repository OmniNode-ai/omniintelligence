# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The verifier refuses an agent receipt for a typed reason, or accepts it (OMN-22175).

Plain unit tests of the verifier's rules: each of the twelve refusals asserts its own
typed reason, then the accept case and the two tests that show the quorum size and the
policy values are input data. The pure handler reads no network and no clock.
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_review_agent_receipt_verify_compute.handlers.handler_review_agent_receipt_verify import (
    handle,
)
from omniintelligence.nodes.node_review_agent_receipt_verify_compute.models import (
    EnumAgentReceiptDecision,
    EnumAgentReceiptRefusal,
    ModelAgentReceiptContext,
    ModelAgentReceiptVerifyRequest,
)

from .helpers import (
    CLASS_FORBIDDEN,
    ENDPOINT_FORBIDDEN,
    HEAD,
    HOST_FORBIDDEN,
    OTHER_HEAD,
    PR,
    PROVIDER_FORBIDDEN,
    REPO,
    policy,
    receipt,
    request,
    voter,
)

pytestmark = pytest.mark.unit

_REFUSED = EnumAgentReceiptDecision.REFUSED
_ACCEPTED = EnumAgentReceiptDecision.ACCEPTED


def _refuses(
    verify_request: ModelAgentReceiptVerifyRequest, reason: EnumAgentReceiptRefusal
) -> None:
    result = handle(verify_request)
    assert result.decision is _REFUSED
    assert result.reason is reason
    assert result.detail, "a refusal names what it refused"
    assert result.voter_identities == ()


def test_refuses_missing_signature() -> None:
    _refuses(request(receipt(sign=False)), EnumAgentReceiptRefusal.MISSING_SIGNATURE)


def test_refuses_forged_signature() -> None:
    altered = receipt().model_copy(update={"reviewer_id": "someone-else"})
    _refuses(request(altered), EnumAgentReceiptRefusal.FORGED_SIGNATURE)
    wrong_key = request(receipt(), key=b"another-key-0123456789abcdef0123")
    _refuses(wrong_key, EnumAgentReceiptRefusal.FORGED_SIGNATURE)


def test_refuses_head_differs() -> None:
    context = ModelAgentReceiptContext(repo=REPO, pr=PR, head_sha=OTHER_HEAD)
    _refuses(request(context=context), EnumAgentReceiptRefusal.HEAD_DIFFERS)


def test_refuses_repository_differs() -> None:
    context = ModelAgentReceiptContext(
        repo="example-org/other-repo", pr=PR, head_sha=HEAD
    )
    _refuses(request(context=context), EnumAgentReceiptRefusal.REPOSITORY_DIFFERS)


def test_refuses_pull_request_differs() -> None:
    context = ModelAgentReceiptContext(repo=REPO, pr=PR + 1, head_sha=HEAD)
    _refuses(request(context=context), EnumAgentReceiptRefusal.PULL_REQUEST_DIFFERS)


def test_refuses_single_voter_below_quorum() -> None:
    one = receipt((voter("voter-a"),))
    _refuses(request(one), EnumAgentReceiptRefusal.BELOW_QUORUM)


def test_refuses_two_voters_one_identity() -> None:
    same = receipt((voter("voter-a"), voter("voter-a", model="another-model")))
    _refuses(request(same), EnumAgentReceiptRefusal.DUPLICATE_IDENTITY)


def test_refuses_provider_anthropic() -> None:
    forbidden = receipt(
        (voter("voter-a"), voter("voter-b", provider=PROVIDER_FORBIDDEN))
    )
    _refuses(request(forbidden), EnumAgentReceiptRefusal.FORBIDDEN_PROVIDER)


def test_refuses_review_gateway_endpoint() -> None:
    gateway = receipt(
        (voter("voter-a"), voter("voter-b", endpoint_class=CLASS_FORBIDDEN))
    )
    _refuses(request(gateway), EnumAgentReceiptRefusal.FORBIDDEN_ENDPOINT_CLASS)


def test_refuses_unknown_voter() -> None:
    unknown = receipt((voter("voter-a"), voter("voter-unlisted")))
    _refuses(request(unknown), EnumAgentReceiptRefusal.UNKNOWN_VOTER)


def test_refuses_missing_provenance_field() -> None:
    for field in (
        "identity",
        "provider",
        "rung",
        "endpoint_class",
        "endpoint",
        "model",
        "delegation_event_id",
    ):
        bare = receipt((voter("voter-a"), voter("voter-b", **{field: ""})))
        result = handle(request(bare))
        assert result.decision is _REFUSED, field
        assert result.reason is EnumAgentReceiptRefusal.MISSING_PROVENANCE, field
        assert field in result.detail, "the refusal names the missing field"


def test_refuses_blocked_verdict() -> None:
    blocked = receipt(
        quorum_verdict="blocked", blocking=("finding-1",), findings_count=1
    )
    _refuses(request(blocked), EnumAgentReceiptRefusal.BLOCKED_VERDICT)
    # a passing verdict that still lists a blocking finding is no pass either
    contradictory = receipt(blocking=("finding-1",), findings_count=1)
    _refuses(request(contradictory), EnumAgentReceiptRefusal.BLOCKED_VERDICT)


def test_accepts_valid_receipt() -> None:
    result = handle(request())
    assert result.decision is _ACCEPTED
    assert result.reason is None
    assert result.voter_identities == ("voter-a", "voter-b")
    assert result.receipt_id == receipt().id


def test_quorum_follows_injected_size() -> None:
    same_receipt = receipt()
    assert handle(request(same_receipt, quorum_size=2)).decision is _ACCEPTED
    third = handle(request(same_receipt, quorum_size=3))
    assert third.decision is _REFUSED
    assert third.reason is EnumAgentReceiptRefusal.BELOW_QUORUM
    three = receipt((voter("voter-a"), voter("voter-b"), voter("voter-c")))
    assert handle(request(three, quorum_size=3)).decision is _ACCEPTED


def test_policy_values_are_data() -> None:
    """Each injected value decides the outcome; nothing else in the node does."""
    # provider
    by_provider = receipt((voter("voter-a"), voter("voter-b", provider="renamed")))
    assert handle(request(by_provider)).decision is _ACCEPTED
    changed = policy(forbidden_providers=("renamed",))
    result = handle(request(by_provider, injected_policy=changed))
    assert result.reason is EnumAgentReceiptRefusal.FORBIDDEN_PROVIDER
    # endpoint class
    by_class = receipt((voter("voter-a"), voter("voter-b", endpoint_class="renamed")))
    assert handle(request(by_class)).decision is _ACCEPTED
    changed = policy(forbidden_endpoint_classes=("renamed",))
    result = handle(request(by_class, injected_policy=changed))
    assert result.reason is EnumAgentReceiptRefusal.FORBIDDEN_ENDPOINT_CLASS
    # endpoint (host and port), with and without a scheme
    for spelled in (ENDPOINT_FORBIDDEN, f"http://{ENDPOINT_FORBIDDEN}/v1"):
        by_endpoint = receipt((voter("voter-a"), voter("voter-b", endpoint=spelled)))
        result = handle(request(by_endpoint))
        assert result.reason is EnumAgentReceiptRefusal.FORBIDDEN_ENDPOINT, spelled
        assert (
            handle(
                request(by_endpoint, injected_policy=policy(forbidden_endpoints=()))
            ).decision
            is _ACCEPTED
        )
    # host: any port of a forbidden host
    by_host = receipt(
        (voter("voter-a"), voter("voter-b", endpoint=f"{HOST_FORBIDDEN}:1234"))
    )
    result = handle(request(by_host))
    assert result.reason is EnumAgentReceiptRefusal.FORBIDDEN_ENDPOINT
    assert (
        handle(request(by_host, injected_policy=policy(forbidden_hosts=()))).decision
        is _ACCEPTED
    )
    # approved identities
    assert (
        handle(request(injected_policy=policy(approved_identities=("voter-a",)))).reason
        is EnumAgentReceiptRefusal.UNKNOWN_VOTER
    )
