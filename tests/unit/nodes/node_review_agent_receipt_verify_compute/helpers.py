# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Fixtures shared by the agent receipt verifier tests (OMN-22175).

Every value here is test data: documentation addresses (RFC 5737) and ``.test``
names stand in for deployment hosts, and the policy is built here, then injected.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from omniintelligence.nodes.node_review_agent_receipt_verify_compute.models import (
    ModelAgentReceiptContext,
    ModelAgentReceiptPolicy,
    ModelAgentReceiptVerifyRequest,
)
from omniintelligence.nodes.node_review_receipt_issue_compute.handlers.handler_issue_agent_receipt import (
    sign_agent_receipt,
)
from omniintelligence.nodes.node_review_receipt_issue_compute.models import (
    ModelAgentReceiptVoter,
    ModelAgentReviewReceipt,
    ModelRosterSnapshot,
)

KEY = b"agent-receipt-test-key-0123456789"
REPO = "example-org/example-repo"
PR = 7
HEAD = "a" * 40
OTHER_HEAD = "b" * 40
ISSUED_AT = datetime(2026, 11, 2, 21, 0, 0, tzinfo=UTC)
RECEIPT_ID = UUID("11111111-2222-4333-8444-555555555555")

CLASS_FORBIDDEN = "class-forbidden"
PROVIDER_FORBIDDEN = "provider-forbidden"
ENDPOINT_FORBIDDEN = "192.0.2.50:9000"
HOST_FORBIDDEN = "forbidden-host.test"


def voter(identity: str, /, **overrides: str) -> ModelAgentReceiptVoter:
    """One counted voter with every provenance field set."""
    fields: dict[str, str] = {
        "identity": identity,
        "provider": "lab-provider",
        "rung": "lab",
        "endpoint_class": "lab-direct",
        "endpoint": "192.0.2.10:8000",
        "model": f"model-{identity}",
        "delegation_event_id": f"event-{identity}",
    }
    fields.update(overrides)
    return ModelAgentReceiptVoter(**fields)


def policy(**overrides: Any) -> ModelAgentReceiptPolicy:
    """The injected policy: three approved identities and four forbidden values."""
    fields: dict[str, Any] = {
        "approved_identities": ("voter-a", "voter-b", "voter-c"),
        "forbidden_providers": (PROVIDER_FORBIDDEN,),
        "forbidden_endpoint_classes": (CLASS_FORBIDDEN,),
        "forbidden_endpoints": (ENDPOINT_FORBIDDEN,),
        "forbidden_hosts": (HOST_FORBIDDEN,),
    }
    fields.update(overrides)
    return ModelAgentReceiptPolicy(**fields)


def receipt(
    voters: tuple[ModelAgentReceiptVoter, ...] | None = None,
    *,
    sign: bool = True,
    **overrides: Any,
) -> ModelAgentReviewReceipt:
    """A signed agent receipt for ``HEAD`` with two clean voters, by default."""
    counted = voters if voters is not None else (voter("voter-a"), voter("voter-b"))
    fields: dict[str, Any] = {
        "id": RECEIPT_ID,
        "repo": REPO,
        "pr": PR,
        "head_sha": HEAD,
        "reviewer_id": "agent-review-dispatch",
        "voters": counted,
        "roster_snapshot": ModelRosterSnapshot(
            voters=("voter-a", "voter-b", "voter-c"), overlay_revision="rev-1"
        ),
        "quorum_verdict": "passed",
        "blocking": (),
        "findings_count": 0,
        "issued_at": ISSUED_AT,
        "key": KEY,
    }
    fields.update(overrides)
    fields["receipt_id"] = fields.pop("id")
    signed = sign_agent_receipt(**fields)
    return signed if sign else signed.model_copy(update={"signature": ""})


def request(
    signed: ModelAgentReviewReceipt | None = None,
    *,
    quorum_size: int = 2,
    injected_policy: ModelAgentReceiptPolicy | None = None,
    key: bytes = KEY,
    context: ModelAgentReceiptContext | None = None,
) -> ModelAgentReceiptVerifyRequest:
    """The verifier's whole input: receipt, key, policy, quorum size, context."""
    return ModelAgentReceiptVerifyRequest(
        receipt=signed if signed is not None else receipt(),
        key=key,
        policy=injected_policy if injected_policy is not None else policy(),
        quorum_size=quorum_size,
        context=context
        if context is not None
        else ModelAgentReceiptContext(repo=REPO, pr=PR, head_sha=HEAD),
    )
