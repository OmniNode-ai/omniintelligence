# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The review bot's verdict on one rejection (OMN-17427)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelRejectionJudgement(BaseModel):
    """Accepted or refused, with the one sentence the judge gave."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    verdict: Literal["accepted", "refused"]
    sentence: str = Field(min_length=1)


class ModelRejectionJudgementRecord(BaseModel):
    """A verdict bound to its rejection and to the judge that gave it."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    key: str = Field(min_length=1)
    verdict: Literal["accepted", "refused"]
    sentence: str = Field(min_length=1)
    judge_id: str = Field(min_length=1)
    identity: str = Field(min_length=1)


class ModelRejectionJudgeBatchResult(BaseModel):
    """The ``--output`` file of ``cli_review judge-rejections``.

    ``unavailable`` names why no rejection could be judged at all; ``notes``
    names, per rejection key, why that one was not. Both fail closed: the
    reviewed repository's gate keeps those findings blocked.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    unavailable: str = ""
    judgements: tuple[ModelRejectionJudgementRecord, ...] = ()
    notes: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "ModelRejectionJudgeBatchResult",
    "ModelRejectionJudgement",
    "ModelRejectionJudgementRecord",
]
