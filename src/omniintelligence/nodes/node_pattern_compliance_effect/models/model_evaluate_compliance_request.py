# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelEvaluateComplianceRequest for compliance handlers (OMN-21536)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_compliance_effect.models.model_compliance_request import (
    ModelComplianceRequest,
)


class ModelEvaluateComplianceRequest(BaseModel):
    """Compliance input with an optional explicit tracing override."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    input_data: ModelComplianceRequest
    correlation_id: UUID | None = None


__all__ = ["ModelEvaluateComplianceRequest"]
