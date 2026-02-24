# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Output model for NavigationRetrieverEffect.

Ticket: OMN-2579
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_navigation_retriever_effect.models.model_retrieved_path import (
    RetrievedPath,
)


class ModelNavigationRetrieveOutput(BaseModel):
    """Result of a navigation path retrieval operation.

    Attributes:
        paths: Ranked list of retrieved navigation paths (similarity descending).
               Empty list on cold start or retrieval timeout/failure.
        timed_out: True if retrieval exceeded the timeout and fell back to empty.
        collection_exists: True if the Qdrant collection was found.
        total_candidates: Total paths in collection before filtering.
        hard_filtered_count: Paths excluded by hard filters.
        stale_steps_filtered: Total steps removed by staleness filtering.
        correlation_id: Optional correlation ID, propagated from input.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    paths: tuple[RetrievedPath, ...] = Field(
        description="Ranked retrieved paths (similarity descending, staleness-filtered).",
    )
    timed_out: bool = Field(
        default=False,
        description="True if retrieval exceeded the timeout threshold.",
    )
    collection_exists: bool = Field(
        default=True,
        description="True if the Qdrant collection was found.",
    )
    total_candidates: int = Field(
        default=0,
        description="Total paths in collection before filtering.",
    )
    hard_filtered_count: int = Field(
        default=0,
        description="Paths excluded by hard filters (type/datasource/tier mismatch).",
    )
    stale_steps_filtered: int = Field(
        default=0,
        description="Total individual steps removed by staleness filtering.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelNavigationRetrieveOutput"]
