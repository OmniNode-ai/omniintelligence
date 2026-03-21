# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wire event model emitted after AST extraction completes for a file."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_relationship import (
    ModelCodeRelationship,
)


class ModelCodeEntitiesExtractedEvent(BaseModel):
    """Event emitted when entities have been extracted from a source file.

    Published to ``onex.evt.omniintelligence.code-entities-extracted.v1``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    event_id: str = Field(description="Unique event identifier")
    crawl_id: str = Field(description="Crawl run identifier")
    repo_name: str = Field(description="Repository name")
    file_path: str = Field(description="Path relative to repo root")
    file_hash: str = Field(description="SHA256 hash of the source file")
    entities: list[ModelCodeEntity] = Field(
        default_factory=list, description="Extracted entities"
    )
    relationships: list[ModelCodeRelationship] = Field(
        default_factory=list, description="Extracted relationships"
    )
    parse_status: str = Field(
        description="Parse outcome: 'success', 'partial', or 'syntax_error'"
    )
    parse_error: str | None = Field(
        default=None, description="Error message when parse_status is 'syntax_error'"
    )
    extractor_version: str = Field(
        default="1.0.0", description="Version of the extractor"
    )
    timestamp: datetime = Field(description="Extraction timestamp")
