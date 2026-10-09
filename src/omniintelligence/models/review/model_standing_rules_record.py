# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The standing rules a verdict was reached under (OMN-20784)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.models.review.model_standing_rule_weakening import (
    ModelStandingRuleWeakening,
)


class ModelStandingRulesRecord(BaseModel):
    """Carried by the verdict so it names the rules it was reached under.

    Attributes:
        version: The rules file's version label.
        digest: Content digest of the rules the models were handed.
        rule_ids: Every rule id in the file, in file order.
        mandatory_rule_ids: The mandatory subset.
        source: Where the rules were read from (a ref and path, or a file path).
        gated: True when the review ran with ``--gated``.
        violations: Mandatory rules the pull request's own rules file weakens.
        candidate_errors: Why the pull request's own rules file is invalid.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    version: str = Field(description="Rules version label.")
    digest: str = Field(description="Content digest of the rules in force.")
    rule_ids: tuple[str, ...] = Field(description="Every rule id, in file order.")
    mandatory_rule_ids: tuple[str, ...] = Field(description="The mandatory rule ids.")
    source: str = Field(description="Where the rules were read from.")
    gated: bool = Field(description="True when the review ran with --gated.")
    violations: tuple[ModelStandingRuleWeakening, ...] = Field(
        default=(), description="Mandatory rules the pull request weakens."
    )
    candidate_errors: tuple[str, ...] = Field(
        default=(), description="Why the pull request's own rules file is invalid."
    )


__all__ = ["ModelStandingRulesRecord"]
