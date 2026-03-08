# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for CI error classifier compute node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelCiErrorClassifierInput(BaseModel):
    """Input for NodeCiErrorClassifierCompute."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    error_fingerprint: str = Field(
        description="SHA-256 hex fingerprint of the CI failure."
    )
    failure_output: str = Field(description="Raw CI failure output for classification.")


__all__ = ["ModelCiErrorClassifierInput"]
