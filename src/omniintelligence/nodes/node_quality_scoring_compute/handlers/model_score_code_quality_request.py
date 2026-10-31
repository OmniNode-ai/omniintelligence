# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Typed request for the code quality scoring handler."""

from pydantic import BaseModel, ConfigDict

from .enum_onex_strictness_level import OnexStrictnessLevel


class ModelScoreCodeQualityRequest(BaseModel):
    """Source code and configuration for quality scoring."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    content: str
    language: str
    weights: dict[str, float] | None = None
    onex_threshold: float = 0.7
    preset: OnexStrictnessLevel | None = None


__all__ = ["ModelScoreCodeQualityRequest"]
