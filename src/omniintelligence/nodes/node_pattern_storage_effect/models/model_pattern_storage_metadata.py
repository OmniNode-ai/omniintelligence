# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""ModelPatternStorageMetadata - metadata for pattern storage operations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternStorageMetadata(BaseModel):
    """Metadata for pattern storage operations.

    Captures contextual information about the pattern including its
    source, learning context, and any additional attributes.

    Attributes:
        source_run_id: ID of the run that produced this pattern.
        actor: Identifier of the entity that created/learned the pattern.
        learning_context: Context in which the pattern was learned.
        tags: Optional tags for categorization.
        additional_attributes: Extra metadata as key-value pairs.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    source_run_id: str | None = Field(
        default=None,
        description="ID of the run that produced this pattern",
    )
    actor: str | None = Field(
        default=None,
        description="Identifier of the entity that created/learned the pattern",
    )
    learning_context: str | None = Field(
        default=None,
        description="Context in which the pattern was learned",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags for categorization",
    )
    additional_attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Extra metadata as key-value pairs (string values only)",
    )
