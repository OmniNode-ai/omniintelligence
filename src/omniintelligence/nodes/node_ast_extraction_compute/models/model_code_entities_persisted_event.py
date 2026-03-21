# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Event model emitted after code entities are persisted to Postgres.

Consumed by Part 2 classification and quality scoring handlers to trigger
enrichment of newly persisted entities.

Reference: OMN-5677
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelCodeEntitiesPersistedEvent(BaseModel):
    """Event confirming successful persistence of code entities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(description="UUID identifying this event")
    crawl_id: str = Field(description="ID of the crawl session")
    repo_name: str = Field(description="Repository the entities belong to")
    file_path: str = Field(description="Source file path")
    file_hash: str = Field(description="SHA256 hash of the source file")
    entity_ids: list[str] = Field(description="UUIDs of persisted entities")
    persisted_count: int = Field(description="Number of entities persisted")
    timestamp: datetime = Field(description="When persistence completed")
