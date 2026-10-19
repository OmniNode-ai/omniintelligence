# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The review rubric file format, ``review_rubric.v1`` (OMN-21186)."""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rubric_rule import (
    ModelReviewRubricRule,
)

REVIEW_RUBRIC_SCHEMA_VERSION: Final = "review_rubric.v1"
CONTENT_HASH_PATTERN: Final = r"^sha256:[0-9a-f]{64}$"


class ModelReviewRubric(BaseModel):
    """A versioned review rubric, a yaml file named ``review_rubric.vN.yaml``.

    ``content_hash`` is ``sha256:`` over the canonical json of every other key
    (see ``compute_content_hash``), so an edited file with a stale hash is
    refused. ``created_from`` lists the label events the rules were distilled
    from, by id. ``hints`` are free text a reviewer may weigh but a rule does
    not back with truth labels.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    schema_version: Literal["review_rubric.v1"]
    version: int = Field(ge=1)
    parent_version: int | None = Field(default=None, ge=1)
    content_hash: str = Field(pattern=CONTENT_HASH_PATTERN)
    created_from: tuple[str, ...] = Field(min_length=1)
    rules: tuple[ModelReviewRubricRule, ...] = Field(min_length=1)
    hints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def parent_is_older(self) -> Self:
        if self.parent_version is not None and self.parent_version >= self.version:
            raise ValueError("parent_version must be below version")
        return self


__all__ = ["CONTENT_HASH_PATTERN", "REVIEW_RUBRIC_SCHEMA_VERSION", "ModelReviewRubric"]
