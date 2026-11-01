# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for the pure criteria matching handler."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field


class ModelCriteriaMatchRequest(BaseModel):
    """An execution outcome and the success criteria to evaluate against it.

    Criteria are carried as plain mappings (``SuccessCriterionDict`` shaped) and
    validated by the handler, which reports an invalid set as a
    ``CriteriaMatchingValidationError``.

    Attributes:
        outcome: Dictionary containing execution results to match against.
        criteria: List of success criteria to evaluate.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    outcome: dict[str, object] = Field(description="Execution results to match.")
    criteria: Sequence[Mapping[str, object]] = Field(
        description="Success criteria to evaluate."
    )


__all__ = ["ModelCriteriaMatchRequest"]
