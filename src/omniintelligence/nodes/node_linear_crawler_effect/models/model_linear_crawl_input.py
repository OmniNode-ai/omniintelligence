# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Input model for LinearCrawlerEffect.

Defines the crawl request payload consumed from crawl-tick.v1 events
with crawl_type=LINEAR.

Ticket: OMN-2388
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelLinearCrawlInput(BaseModel):
    """Input for a Linear crawl request.

    Consumed from the ``crawl-tick.v1`` Kafka topic when
    ``crawl_type == CrawlerType.LINEAR``.

    Attributes:
        team_id: Linear team identifier (e.g., "omninode"). Used to list
            issues via the Linear API.
        crawl_scope: Logical scope for the crawl
            (e.g., "omninode/shared", "omninode/omniintelligence").
            Stored as the ``scope`` field in crawl-state entries and emitted
            events.
        project_id: Optional Linear project identifier. When set, limits
            the issue list to a specific project rather than the full team.
        correlation_id: Optional tracing ID propagated from the trigger.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    team_id: str = Field(description="Linear team identifier (e.g., 'omninode').")
    crawl_scope: str = Field(
        description=(
            "Logical scope for the crawl "
            "(e.g., 'omninode/shared', 'omninode/omniintelligence')."
        )
    )
    project_id: str | None = Field(
        default=None,
        description="Optional Linear project ID to filter issues.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelLinearCrawlInput"]
