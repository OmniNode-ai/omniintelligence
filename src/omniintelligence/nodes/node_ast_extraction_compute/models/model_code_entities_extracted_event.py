# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wire event model emitted after AST extraction completes for a file."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_relationship import (
    ModelCodeRelationship,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ModelCodeEntitiesExtractedEvent(BaseModel):
    """Wire model emitted after AST extraction completes for a file.

    Published to onex.evt.omniintelligence.code-entities-extracted.v1.
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
    entities: list[ModelCodeEntity] = Field(default_factory=list)
    relationships: list[ModelCodeRelationship] = Field(default_factory=list)
    entity_count: int = Field(default=0, ge=0)
    relationship_count: int = Field(default=0, ge=0)
    parse_status: str = Field(
        default="success",
        description="Parse outcome: success, partial, or syntax_error",
    )
    parse_error: str | None = Field(
        default=None, description="Error message when parse_status is syntax_error"
    )
    extractor_version: str = Field(
        default="1.0.0", description="Version of the extractor"
    )
    timestamp: datetime = Field(default_factory=_utc_now)


__all__ = ["ModelCodeEntitiesExtractedEvent"]
