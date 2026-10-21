# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Which judge asks what, or why no judge can (OMN-17427)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelRejectionJudgePlan(BaseModel):
    """The chosen judge and its prompt; ``refusal`` set when none may judge."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    judge_id: str = ""
    identity: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    refusal: str = ""


__all__ = ["ModelRejectionJudgePlan"]
