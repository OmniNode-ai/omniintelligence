# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""One off-CI reviewer's signed verdict on one head commit (OMN-20947)."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

RECEIPT_SCHEMA_VERSION: Final = "hostile_review_receipt.v1"
RECEIPT_FENCE: Final = "onex-review-receipt"


class ModelReviewReceipt(BaseModel):
    """A receipt as it travels in a fenced block of a pull request review."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    schema_version: Literal["hostile_review_receipt.v1"]
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    pr: int = Field(gt=0)
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    reviewer_id: str = Field(min_length=1, max_length=63)
    verdict: Literal["clean", "findings"]
    findings_count: int = Field(ge=0)
    issued_at: datetime
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_receipt(self) -> Self:
        if self.issued_at.tzinfo is None:
            raise ValueError("issued_at must carry a timezone")
        if (self.verdict == "clean") != (self.findings_count == 0):
            raise ValueError("verdict is 'clean' exactly when findings_count is 0")
        return self


__all__ = ["RECEIPT_FENCE", "RECEIPT_SCHEMA_VERSION", "ModelReviewReceipt"]
