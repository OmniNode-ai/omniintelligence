# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for CI fingerprint compute node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelCiFingerprintOutput(BaseModel):
    """Output for NodeCiFingerprintCompute."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    fingerprint: str = Field(
        description="SHA-256 hex digest fingerprint of the CI failure."
    )


__all__ = ["ModelCiFingerprintOutput"]
