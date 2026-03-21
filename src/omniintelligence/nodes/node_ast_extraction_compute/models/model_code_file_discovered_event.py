# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Event model for code file discovery during crawl."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ModelCodeFileDiscoveredEvent(BaseModel):
    """Wire model emitted when a code file is discovered during crawl.

    Published to onex.evt.omniintelligence.code-file-discovered.v1.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    event_id: str = Field(..., min_length=1)
    crawl_id: str = Field(..., min_length=1)
    repo_name: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    file_hash: str = Field(..., min_length=1)
    file_extension: str
    timestamp: datetime = Field(default_factory=_utc_now)


__all__ = ["ModelCodeFileDiscoveredEvent"]
