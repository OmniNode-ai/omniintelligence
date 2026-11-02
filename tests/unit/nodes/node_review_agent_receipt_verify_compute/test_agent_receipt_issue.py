# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The signer node issues the agent receipt variant (OMN-22175)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from omniintelligence.nodes.node_review_receipt_issue_compute.handlers.handler_issue_agent_receipt import (
    agent_receipt_signature,
    handle,
    render_agent_receipt_block,
)
from omniintelligence.nodes.node_review_receipt_issue_compute.models import (
    ModelAgentReviewReceipt,
    ModelIssueAgentReceiptRequest,
    ModelRosterSnapshot,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.handlers.handler_review_receipt_substitute import (
    receipt_signature,
    sign_receipt,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.models.model_review_receipt import (
    RECEIPT_FENCE,
)

from .helpers import HEAD, ISSUED_AT, KEY, PR, RECEIPT_ID, REPO, receipt, voter

pytestmark = pytest.mark.unit


def _request(**overrides: Any) -> ModelIssueAgentReceiptRequest:
    fields: dict[str, Any] = {
        "id": RECEIPT_ID,
        "repo": REPO,
        "pr": PR,
        "head_sha": HEAD,
        "reviewer_id": "agent-review-dispatch",
        "voters": (voter("voter-a"), voter("voter-b")),
        "roster_snapshot": ModelRosterSnapshot(
            voters=("voter-a", "voter-b"), overlay_revision="rev-1"
        ),
        "quorum_verdict": "passed",
        "blocking": (),
        "findings_count": 0,
        "issued_at": ISSUED_AT,
        "key": KEY,
    }
    fields.update(overrides)
    return ModelIssueAgentReceiptRequest(**fields)


def test_issued_receipt_carries_the_agent_fields_and_verifies_by_signature() -> None:
    issued = handle(_request())
    assert issued.schema_version == "hostile_review_agent_receipt.v1"
    assert issued.id == RECEIPT_ID
    assert [v.identity for v in issued.voters] == ["voter-a", "voter-b"]
    assert issued.roster_snapshot.overlay_revision == "rev-1"
    assert issued.quorum_verdict == "passed"
    assert issued.signature == agent_receipt_signature(issued, KEY)
    assert issued.signature != agent_receipt_signature(
        issued, b"another-key-0123456789abcdef0123"
    )


def test_signature_covers_every_field() -> None:
    base = receipt()
    for update in (
        {"head_sha": "c" * 40},
        {"pr": PR + 1},
        {"findings_count": 1},
        {"quorum_verdict": "blocked"},
        {"voters": (voter("voter-a"),)},
    ):
        assert (
            agent_receipt_signature(base.model_copy(update=update), KEY)
            != base.signature
        )


def test_agent_signature_is_domain_separated_from_the_base_receipt() -> None:
    """The same fields signed under the base schema produce another signature."""
    base = sign_receipt(
        repo=REPO,
        pr=PR,
        head_sha=HEAD,
        reviewer_id="agent-review-dispatch",
        findings_count=0,
        issued_at=ISSUED_AT,
        key=KEY,
    )
    assert base.signature != receipt().signature
    assert receipt_signature(base, KEY) == base.signature


def test_block_uses_the_receipt_fence_and_round_trips() -> None:
    block = render_agent_receipt_block(receipt())
    assert block.startswith(f"```{RECEIPT_FENCE}\n")
    assert block.endswith("\n```")
    body = block.split("\n", 1)[1].rsplit("\n", 1)[0]
    assert ModelAgentReviewReceipt.model_validate(json.loads(body)) == receipt()


def test_request_refuses_a_verdict_that_contradicts_its_blocking_findings() -> None:
    with pytest.raises(ValidationError):
        _request(quorum_verdict="passed", blocking=("finding-1",), findings_count=1)
    with pytest.raises(ValidationError):
        _request(quorum_verdict="blocked", blocking=(), findings_count=0)
    with pytest.raises(ValidationError):
        _request(quorum_verdict="blocked", blocking=("a", "b"), findings_count=1)
