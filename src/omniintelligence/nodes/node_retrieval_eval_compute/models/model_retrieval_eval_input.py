# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for NodeRetrievalEvalCompute (OMN-21945)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ModelRetrievalEvalInput(BaseModel):
    """Request to run the offline retrieval eval harness.

    Both paths default to the committed artifacts, so an empty request runs the
    same harness the retrieval eval gate runs in CI.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    correlation_id: UUID = Field(default_factory=uuid4)
    fixture_root: Path | None = Field(
        default=None,
        description="Replay fixture root; defaults to the committed v2 fixtures.",
    )
    golden_set_path: Path | None = Field(
        default=None,
        description="Golden query set; defaults to the committed v1 set.",
    )


__all__ = ["ModelRetrievalEvalInput"]
