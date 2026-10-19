# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A signed receipt and the record of the findings it counts (OMN-20981)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from omniintelligence.nodes.node_review_receipt_substitute_compute.models.model_review_receipt import (
    ModelReviewReceipt,
)
from omniintelligence.nodes.node_review_record_compute.models import (
    ModelReviewRecorded,
)


class ModelIssuedReceipt(BaseModel):
    """The unchanged receipt, and beside it the record holding the findings.

    The receipt carries a verdict and a count only; the record carries the
    findings themselves, exactly as many as the receipt counts.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    receipt: ModelReviewReceipt
    record: ModelReviewRecorded

    @model_validator(mode="after")
    def _validate_issued(self) -> Self:
        if len(self.record.findings) != self.receipt.findings_count:
            raise ValueError(
                f"the record holds {len(self.record.findings)} finding(s); the "
                f"receipt counts {self.receipt.findings_count}"
            )
        return self


__all__ = ["ModelIssuedReceipt"]
