# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Verify a signed agent review receipt against the exact pull request head (OMN-22175).

The checks run in a fixed order and the first that fails decides, each with its own
typed reason:

1. the signature: absent, or not the HMAC of the receipt under the key;
2. the verification context: repository, pull request and head commit;
3. the quorum verdict, and any blocking finding the receipt lists;
4. each voter, in receipt order: provenance fields, provider, endpoint class,
   endpoint and host, approved identity;
5. the voters together: distinct identities, then the injected quorum size.

Every value that decides a refusal is read from the request's policy; nothing here
names a class, provider, endpoint or host. Pure: no network, no clock, no file.
"""

from __future__ import annotations

import hmac
from urllib.parse import urlsplit

from omniintelligence.nodes.node_review_agent_receipt_verify_compute.models import (
    EnumAgentReceiptDecision,
    EnumAgentReceiptRefusal,
    ModelAgentReceiptPolicy,
    ModelAgentReceiptVerdict,
    ModelAgentReceiptVerifyRequest,
)
from omniintelligence.nodes.node_review_receipt_issue_compute.handlers.handler_issue_agent_receipt import (
    agent_receipt_signature,
)
from omniintelligence.nodes.node_review_receipt_issue_compute.models.model_agent_review_receipt import (
    ModelAgentReceiptVoter,
)

_PROVENANCE_FIELDS = (
    "identity",
    "provider",
    "rung",
    "endpoint_class",
    "endpoint",
    "model",
    "delegation_event_id",
)


def _refuse(reason: EnumAgentReceiptRefusal, detail: str) -> ModelAgentReceiptVerdict:
    return ModelAgentReceiptVerdict(
        decision=EnumAgentReceiptDecision.REFUSED, reason=reason, detail=detail
    )


def _host_of(endpoint: str) -> str:
    """The host part of ``host``, ``host:port`` or ``scheme://host:port/path``."""
    spelled = endpoint if "://" in endpoint else f"//{endpoint}"
    return (urlsplit(spelled).hostname or "").lower()


def _endpoint_of(endpoint: str) -> str:
    """``host[:port]`` of the endpoint, lowercased, with no scheme or path."""
    spelled = endpoint if "://" in endpoint else f"//{endpoint}"
    return urlsplit(spelled).netloc.lower()


def _check_voter(
    voter: ModelAgentReceiptVoter, policy: ModelAgentReceiptPolicy
) -> ModelAgentReceiptVerdict | None:
    """The refusal for one voter, or None when the voter stands."""
    who = voter.identity or "(no identity)"
    for field in _PROVENANCE_FIELDS:
        if not getattr(voter, field):
            return _refuse(
                EnumAgentReceiptRefusal.MISSING_PROVENANCE,
                f"voter {who} has no {field}",
            )
    if voter.provider in policy.forbidden_providers:
        return _refuse(
            EnumAgentReceiptRefusal.FORBIDDEN_PROVIDER,
            f"voter {who} names provider {voter.provider!r}, which the policy forbids",
        )
    if voter.endpoint_class in policy.forbidden_endpoint_classes:
        return _refuse(
            EnumAgentReceiptRefusal.FORBIDDEN_ENDPOINT_CLASS,
            f"voter {who} names endpoint class {voter.endpoint_class!r}, "
            "which the policy forbids",
        )
    forbidden_endpoints = {_endpoint_of(value) for value in policy.forbidden_endpoints}
    forbidden_hosts = {value.lower() for value in policy.forbidden_hosts}
    if (
        _endpoint_of(voter.endpoint) in forbidden_endpoints
        or _host_of(voter.endpoint) in forbidden_hosts
    ):
        return _refuse(
            EnumAgentReceiptRefusal.FORBIDDEN_ENDPOINT,
            f"voter {who} names endpoint {voter.endpoint!r}, which the policy forbids",
        )
    if voter.identity not in policy.approved_identities:
        return _refuse(
            EnumAgentReceiptRefusal.UNKNOWN_VOTER,
            f"voter {who} is not an approved identity",
        )
    return None


class HandlerReviewAgentReceiptVerify:
    """The node's handler: a receipt and its injected inputs in, a verdict out."""

    def handle(
        self, request: ModelAgentReceiptVerifyRequest
    ) -> ModelAgentReceiptVerdict:
        """Accept the receipt for the exact head in hand, or refuse it for one reason."""
        receipt = request.receipt
        context = request.context
        policy = request.policy

        if not receipt.signature:
            return _refuse(
                EnumAgentReceiptRefusal.MISSING_SIGNATURE, "the receipt is unsigned"
            )
        expected = agent_receipt_signature(receipt, request.key)
        if not hmac.compare_digest(receipt.signature, expected):
            return _refuse(
                EnumAgentReceiptRefusal.FORGED_SIGNATURE,
                "the signature does not verify under the key",
            )
        if receipt.repo.lower() != context.repo.lower():
            return _refuse(
                EnumAgentReceiptRefusal.REPOSITORY_DIFFERS,
                f"the receipt is for {receipt.repo}, not {context.repo}",
            )
        if receipt.pr != context.pr:
            return _refuse(
                EnumAgentReceiptRefusal.PULL_REQUEST_DIFFERS,
                f"the receipt is for pull request {receipt.pr}, not {context.pr}",
            )
        if receipt.head_sha != context.head_sha:
            return _refuse(
                EnumAgentReceiptRefusal.HEAD_DIFFERS,
                f"the receipt is bound to {receipt.head_sha[:12]}, "
                f"not head {context.head_sha[:12]}",
            )
        if receipt.quorum_verdict != "passed" or receipt.blocking:
            return _refuse(
                EnumAgentReceiptRefusal.BLOCKED_VERDICT,
                f"the receipt's verdict is {receipt.quorum_verdict!r} with "
                f"{len(receipt.blocking)} blocking finding(s)",
            )

        for voter in receipt.voters:
            refusal = _check_voter(voter, policy)
            if refusal is not None:
                return refusal

        identities = tuple(voter.identity for voter in receipt.voters)
        if len(set(identities)) != len(identities):
            return _refuse(
                EnumAgentReceiptRefusal.DUPLICATE_IDENTITY,
                "two voters share one identity",
            )
        if len(identities) < request.quorum_size:
            return _refuse(
                EnumAgentReceiptRefusal.BELOW_QUORUM,
                f"{len(identities)} distinct voter(s); the quorum is {request.quorum_size}",
            )
        return ModelAgentReceiptVerdict(
            decision=EnumAgentReceiptDecision.ACCEPTED,
            voter_identities=identities,
            receipt_id=receipt.id,
        )


def handle(request: ModelAgentReceiptVerifyRequest) -> ModelAgentReceiptVerdict:
    """The contract's routed entry point; see ``HandlerReviewAgentReceiptVerify``."""
    return HandlerReviewAgentReceiptVerify().handle(request)


__all__ = ["HandlerReviewAgentReceiptVerify", "handle"]
