# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Bootstrap tier assignment policy model.

Defines the configurable pattern table for determining the starting
trust tier of a context item based on its source_ref. The policy is
evaluated in order; the first matching pattern wins.

Ticket: OMN-2393
"""

from __future__ import annotations

import fnmatch

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_context_item_writer_effect.models.enum_bootstrap_tier import (
    EnumBootstrapTier,
)


class ModelTierPolicy(BaseModel):
    """A single tier policy rule: pattern → tier."""

    model_config = {"frozen": True, "extra": "ignore"}

    pattern: str = Field(
        description="Glob pattern matched against source_ref (fnmatch semantics)."
    )
    tier: EnumBootstrapTier = Field(
        description="Tier assigned when source_ref matches pattern."
    )
    bootstrap_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Initial confidence score at bootstrap.",
    )
    expires_after_runs: int | None = Field(
        default=None,
        description="Number of scored runs before bootstrap tier expires. None = no expiry.",
    )

    def matches(self, source_ref: str) -> bool:
        """Return True if source_ref matches this policy's pattern."""
        return fnmatch.fnmatch(source_ref, self.pattern)


# Default policy table (first match wins)
DEFAULT_TIER_POLICIES: tuple[ModelTierPolicy, ...] = (
    ModelTierPolicy(
        pattern="*/.claude/CLAUDE.md",
        tier=EnumBootstrapTier.VALIDATED,
        bootstrap_confidence=0.85,
        expires_after_runs=5,
    ),
    ModelTierPolicy(
        pattern="*/CLAUDE.md",
        tier=EnumBootstrapTier.VALIDATED,
        bootstrap_confidence=0.85,
        expires_after_runs=5,
    ),
    ModelTierPolicy(
        pattern="omni_save/design/*.md",
        tier=EnumBootstrapTier.VALIDATED,
        bootstrap_confidence=0.75,
        expires_after_runs=5,
    ),
    ModelTierPolicy(
        pattern="omni_save/plans/*.md",
        tier=EnumBootstrapTier.QUARANTINE,
        bootstrap_confidence=0.65,
        expires_after_runs=None,
    ),
    ModelTierPolicy(
        pattern="*.md",
        tier=EnumBootstrapTier.QUARANTINE,
        bootstrap_confidence=0.0,
        expires_after_runs=None,
    ),
    # Catch-all: everything else goes to QUARANTINE
    ModelTierPolicy(
        pattern="*",
        tier=EnumBootstrapTier.QUARANTINE,
        bootstrap_confidence=0.0,
        expires_after_runs=None,
    ),
)


def assign_bootstrap_tier(
    source_ref: str,
    policies: tuple[ModelTierPolicy, ...] = DEFAULT_TIER_POLICIES,
) -> ModelTierPolicy:
    """Return the first policy that matches source_ref.

    Args:
        source_ref: The file path or reference key of the context item source.
        policies: Ordered policy table. First match wins. Defaults to DEFAULT_TIER_POLICIES.

    Returns:
        The first matching ModelTierPolicy. The catch-all (*) at the end
        ensures this never returns None.
    """
    for policy in policies:
        if policy.matches(source_ref):
            return policy
    # The catch-all * policy always matches; this is unreachable but satisfies mypy
    return ModelTierPolicy(
        pattern="*",
        tier=EnumBootstrapTier.QUARANTINE,
        bootstrap_confidence=0.0,
    )


__all__ = [
    "ModelTierPolicy",
    "DEFAULT_TIER_POLICIES",
    "assign_bootstrap_tier",
]
