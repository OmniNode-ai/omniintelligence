# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A voter that succeeded in this review and may judge a dismissal (OMN-20910)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelDismissalVoter(BaseModel):
    """A succeeded voter's key and its reviewer identity (endpoint plus model)."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    voter_id: str = Field(min_length=1)
    identity: str = Field(description="Reviewer identity; the key when unknown.")


__all__ = ["ModelDismissalVoter"]
