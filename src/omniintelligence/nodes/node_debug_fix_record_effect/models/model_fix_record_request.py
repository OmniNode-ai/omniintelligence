# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerFixRecord."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelFixRecordRequest(BaseModel):
    """Inputs for creating a FixRecord when CI recovers."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    repo: str
    branch: str
    sha: str
    pr_number: int | None
    changed_files: list[str]


__all__ = ["ModelFixRecordRequest"]
