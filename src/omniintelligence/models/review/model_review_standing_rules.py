# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The standing rules of a reviewed repository, with a version and a digest (OMN-20784)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.models.review.model_review_standing_rule import (
    ModelReviewStandingRule,
)


class ModelReviewStandingRules(BaseModel):
    """Schema of a reviewed repository's rules file.

    The schema ships with this repository; the rules are the reviewed
    repository's own overlay file. ``digest`` is computed from the content, so
    a file cannot declare one, and two files with the same rules in a different
    order have the same digest.

    Attributes:
        schema_version: Version of this schema. Only 1 exists.
        version: The rules file's own version label.
        rules: At least one rule, with unique ids.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    schema_version: Literal[1] = Field(description="Version of this schema.")
    version: str = Field(min_length=1, max_length=64, description="Rules version.")
    rules: tuple[ModelReviewStandingRule, ...] = Field(
        min_length=1, description="The rules, ids unique."
    )

    digest: str = Field(
        default="",
        description="SHA-256 of the canonical content; computed, never declared.",
    )

    @model_validator(mode="before")
    @classmethod
    def _digest_is_not_declared(cls, data: Any) -> Any:
        if isinstance(data, dict) and "digest" in data:
            raise ValueError(
                "digest is computed from the content and cannot be declared"
            )
        return data

    @model_validator(mode="after")
    def _ids_are_unique_and_digest_stamped(self) -> ModelReviewStandingRules:
        seen: set[str] = set()
        for rule in self.rules:
            if rule.id in seen:
                raise ValueError(f"duplicate rule id {rule.id!r}")
            seen.add(rule.id)
        # Frozen models refuse setattr; the digest is part of construction.
        object.__setattr__(self, "digest", self._compute_digest())
        return self

    def _compute_digest(self) -> str:
        """SHA-256 over the canonical content: schema, version, rules sorted by id."""
        canonical = {
            "schema_version": self.schema_version,
            "version": self.version,
            "rules": [
                {"id": r.id, "mandatory": r.mandatory, "text": r.text}
                for r in sorted(self.rules, key=lambda r: r.id)
            ],
        }
        payload = json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def rule(self, rule_id: str) -> ModelReviewStandingRule | None:
        """The rule with this id, or None."""
        return next((r for r in self.rules if r.id == rule_id), None)


__all__ = ["ModelReviewStandingRules"]
