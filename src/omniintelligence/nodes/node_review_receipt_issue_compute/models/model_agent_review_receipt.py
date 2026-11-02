# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The agent review receipt variant, ``hostile_review_agent_receipt.v1`` (OMN-22175).

An agent review is a review the orchestrator dispatches to lab models outside CI.
Its receipt is the base receipt's shape (repository, pull request, exact head, a
reviewer, an HMAC signature) plus a nonce ``id``, the counted ``voters`` with the
provenance of each lab call, the ``roster_snapshot`` the review was configured
under, the ``quorum_verdict``, the ``blocking`` findings (raised by at least two
voters) and the ``findings_count``.

The model is permissive on purpose: an empty provenance field or an empty signature
parses, so that the verifier can refuse it for its own typed reason instead of the
document failing to load. The issuer is the strict side (``ModelIssueAgentReceiptRequest``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AGENT_RECEIPT_SCHEMA_VERSION: Final = "hostile_review_agent_receipt.v1"


class ModelAgentReceiptVoter(BaseModel):
    """One counted voter and the provenance of its lab call.

    A field that is empty is a missing provenance field: the verifier refuses it.
    ``delegation_event_id`` exists only after the call was made.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    identity: str = ""
    provider: str = ""
    rung: str = ""
    endpoint_class: str = ""
    endpoint: str = Field(default="", description="host[:port] the call went to.")
    model: str = ""
    delegation_event_id: str = ""


class ModelRosterSnapshot(BaseModel):
    """The voters the review was configured with and the roster overlay revision."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    voters: tuple[str, ...]
    overlay_revision: str = Field(min_length=1)


class ModelAgentReviewReceipt(BaseModel):
    """A signed agent review receipt as it travels in an ``onex-review-receipt`` block."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    schema_version: Literal["hostile_review_agent_receipt.v1"] = (
        "hostile_review_agent_receipt.v1"
    )
    id: UUID = Field(description="Nonce: one id per issued receipt.")
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    pr: int = Field(gt=0)
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    reviewer_id: str = Field(min_length=1, max_length=63)
    voters: tuple[ModelAgentReceiptVoter, ...]
    roster_snapshot: ModelRosterSnapshot
    quorum_verdict: Literal["passed", "blocked"]
    blocking: tuple[str, ...] = ()
    findings_count: int = Field(ge=0)
    issued_at: datetime
    signature: str = Field(
        default="",
        pattern=r"^([0-9a-f]{64})?$",
        description="Empty when the receipt is unsigned; the verifier refuses it.",
    )

    @model_validator(mode="after")
    def _validate_receipt(self) -> Self:
        if self.issued_at.tzinfo is None:
            raise ValueError("issued_at must carry a timezone")
        return self


__all__ = [
    "AGENT_RECEIPT_SCHEMA_VERSION",
    "ModelAgentReceiptVoter",
    "ModelAgentReviewReceipt",
    "ModelRosterSnapshot",
]
