# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output of the standing-rules handler (OMN-20784)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.models.review.model_review_standing_rules import (
    ModelReviewStandingRules,
)
from omniintelligence.models.review.model_standing_rule_weakening import (
    ModelStandingRuleWeakening,
)


class ModelStandingRulesResult(BaseModel):
    """Outcome of validating the rules and comparing the pull request's copy.

    Attributes:
        ok: True when the rules are valid and the candidate, if compared,
            weakens nothing and is itself valid.
        rules: The authoritative rules, None when they are missing or invalid.
        errors: Why the authoritative rules are unusable.
        weakened: Mandatory rules the candidate does not keep intact.
        candidate_errors: Why the candidate file is itself invalid.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    ok: bool = Field(description="Rules usable and nothing weakened.")
    rules: ModelReviewStandingRules | None = Field(
        default=None, description="The authoritative rules, when valid."
    )
    errors: tuple[str, ...] = Field(
        default=(), description="Why the authoritative rules are unusable."
    )
    weakened: tuple[ModelStandingRuleWeakening, ...] = Field(
        default=(), description="Mandatory rules the candidate does not keep."
    )
    candidate_errors: tuple[str, ...] = Field(
        default=(), description="Why the candidate rules file is invalid."
    )


__all__ = ["ModelStandingRulesResult"]
