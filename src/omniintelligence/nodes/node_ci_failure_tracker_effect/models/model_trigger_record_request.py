# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input for recording a CI failure and checking its streak threshold."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelTriggerRecordRequest(BaseModel):
    """Input for recording a CI failure and checking its streak threshold."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    repo: str
    branch: str
    sha: str
    failure_fingerprint: str
    error_classification: str
    streak_threshold: int
    correlation_id: str = "unknown"
