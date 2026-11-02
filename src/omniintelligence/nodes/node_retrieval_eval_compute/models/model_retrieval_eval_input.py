# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelRetrievalEvalInput -- the request of the retrieval eval compute node."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ModelRetrievalEvalInput(BaseModel):
    """Where the offline harness reads its replay fixtures and golden set.

    Both paths default to the committed artifacts, so an empty request runs the
    same harness CI gates on.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    correlation_id: UUID = Field(default_factory=uuid4)
    fixture_root: Path | None = Field(
        default=None,
        description="Replay fixture root; the committed v2 fixtures when unset.",
    )
    golden_set_path: Path | None = Field(
        default=None,
        description="Golden query set file; the committed v1 set when unset.",
    )


__all__ = ["ModelRetrievalEvalInput"]
