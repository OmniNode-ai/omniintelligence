# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Remediation signal consumed by the finding-feedback handler (OMN-2499)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelFindingFeedbackSignal(BaseModel):
    """A remediation signal as emitted by the RemediationPipeline.

    Fields are deliberately loose: the handler validates them and reports a
    malformed signal as ``None`` rather than raising.

    Attributes:
        signal_type: "remediation_accepted" or "remediation_rejected".
        finding_id: UUID string of the finding.
        rule_id: Rule that produced the finding.
        confidence: Confidence at time the finding was created.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    signal_type: object = None
    finding_id: object = None
    rule_id: object = None
    confidence: object = None


__all__ = ["ModelFindingFeedbackSignal"]
