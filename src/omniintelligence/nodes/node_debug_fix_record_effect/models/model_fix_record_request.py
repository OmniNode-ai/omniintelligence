# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for the FixRecord creation handler.

Ticket: OMN-3556
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelFixRecordRequest(BaseModel):
    """Data values needed to create a FixRecord after CI recovers."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    repo: str
    branch: str
    sha: str
    pr_number: int | None
    changed_files: list[str]


__all__ = ["ModelFixRecordRequest"]
