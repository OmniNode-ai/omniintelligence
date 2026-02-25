# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for the evidence collection effect node (OMN-2578).

The ModelCollectionInput carries the session check results and the
objective spec selector for one session evaluation request.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_evidence_collection_effect.models.model_session_check_results import (
    ModelSessionCheckResults,
)

__all__ = ["ModelCollectionInput"]


class ModelCollectionInput(BaseModel):
    """Input to the evidence collection evaluation pipeline.

    Carries the structured check results from a completed agent session
    and an optional task class for objective spec selection.

    Attributes:
        check_results: Structured check results from the agent session.
        task_class: Optional task class identifier for selecting the applicable
            ObjectiveSpec. If None, a default/fallback spec is used.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    check_results: ModelSessionCheckResults = Field(
        description="Aggregated structured check results for the session."
    )
    task_class: str | None = Field(
        default=None,
        description=(
            "Task class identifier for selecting the applicable ObjectiveSpec. "
            "If None, the default ObjectiveSpec is used."
        ),
    )
