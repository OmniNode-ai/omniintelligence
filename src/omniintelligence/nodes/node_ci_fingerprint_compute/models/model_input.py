# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for CI fingerprint compute node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelCiFingerprintInput(BaseModel):
    """Input for NodeCiFingerprintCompute."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    failure_output: str = Field(description="Raw CI failure output / traceback text.")
    failing_tests: list[str] = Field(
        default_factory=list,
        description="List of failing test node IDs (order-independent for fingerprint).",
    )


__all__ = ["ModelCiFingerprintInput"]
