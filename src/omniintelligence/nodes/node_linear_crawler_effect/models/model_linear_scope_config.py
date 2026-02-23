# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Scope mapping configuration for LinearCrawlerEffect.

Maps Linear team/project combinations to logical crawl scopes
(e.g., "omninode/shared", "omninode/omniintelligence").

Ticket: OMN-2388
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelLinearScopeMapping(BaseModel):
    """A single mapping from a Linear team/project to a crawl scope.

    Attributes:
        team_id: Linear team identifier to match (e.g., "omninode").
        project_id: Optional Linear project identifier. When set, this mapping
            only applies to issues in the specified project.
        crawl_scope: Logical scope to assign when this mapping matches
            (e.g., "omninode/shared", "omninode/omniintelligence").
    """

    model_config = {"frozen": True, "extra": "ignore"}

    team_id: str = Field(description="Linear team ID to match.")
    project_id: str | None = Field(
        default=None,
        description="Optional Linear project ID to match within the team.",
    )
    crawl_scope: str = Field(
        description="Logical scope assigned when this mapping matches."
    )


class ModelLinearScopeConfig(BaseModel):
    """Configuration for Linear-to-scope mapping.

    Holds the ordered list of scope mappings. The first mapping that matches
    a (team_id, project_id) pair wins.

    Default mappings (from the design doc):
        - team=OmniNode → "omninode/shared"
        - team=OmniNode, project=OmniIntelligence → "omninode/omniintelligence"

    Attributes:
        mappings: Ordered list of scope mappings. More-specific mappings
            (with project_id) should appear before less-specific ones.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    mappings: tuple[ModelLinearScopeMapping, ...] = Field(
        default_factory=tuple,
        description="Ordered scope mappings (most specific first).",
    )

    def resolve_scope(self, team_id: str, project_id: str | None) -> str | None:
        """Return the crawl scope for a given (team_id, project_id) pair.

        Matches mappings in order. A mapping with project_id set only matches
        when the project_id argument is equal to that mapping's project_id.
        A mapping with project_id=None matches any project within the team.

        Returns None if no mapping matches.
        """
        for mapping in self.mappings:
            if mapping.team_id != team_id:
                continue
            if mapping.project_id is not None and mapping.project_id != project_id:
                continue
            return mapping.crawl_scope
        return None


_DEFAULT_MAPPINGS = (
    ModelLinearScopeMapping(
        team_id="omninode",
        project_id="omniintelligence",
        crawl_scope="omninode/omniintelligence",
    ),
    ModelLinearScopeMapping(
        team_id="omninode",
        project_id=None,
        crawl_scope="omninode/shared",
    ),
)

DEFAULT_SCOPE_CONFIG = ModelLinearScopeConfig(mappings=_DEFAULT_MAPPINGS)
"""Default scope configuration matching the design doc specification.

More-specific project mapping appears first so it wins over the team-level
catch-all.
"""

__all__ = [
    "DEFAULT_SCOPE_CONFIG",
    "ModelLinearScopeConfig",
    "ModelLinearScopeMapping",
]
