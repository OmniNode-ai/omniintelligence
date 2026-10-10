# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""One voter of the Hostile Reviewer gate, as the overlay declares it (OMN-20910)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

VOTER_ID_PATTERN = r"^[a-z][a-z0-9-]{0,62}$"


class ModelReviewVoter(BaseModel):
    """A voter: where it is, which model, how it samples, what it stresses."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    voter_id: str = Field(
        pattern=VOTER_ID_PATTERN,
        description=(
            "Name the result, the quorum summary and the PR comment report this "
            "voter under. Names the role, not the model, so a model swap needs "
            "no rename."
        ),
    )
    backend_id: str | None = Field(
        default=None,
        min_length=1,
        description="A backend of the overlay named by backend_overlay.",
    )
    endpoint_url: str | None = Field(
        default=None,
        min_length=1,
        description="An explicit OpenAI-compatible endpoint, for a voter no "
        "delegation backend describes.",
    )
    model_id_source: Literal["served", "declared"] = Field(
        default="served",
        description="served: the endpoint's one /v1/models id, read at call "
        "time (OMN-18623). declared: send api_model_id, for an endpoint that "
        "serves several models.",
    )
    api_model_id: str = Field(default="")
    required: bool = Field(
        description="A required voter that is unreachable or fails makes the run "
        "fail, naming it. No default: every voter states it."
    )
    timeout_seconds: float = Field(gt=0.0, le=1800.0)
    max_retries: int | None = Field(default=None, ge=0, le=5)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)
    review_focus: str = Field(default="")
    enable_thinking: bool = Field(default=False)
    reasoning_effort: Literal["low", "medium", "high"] | None = Field(default=None)
    constrain_findings_schema: bool = Field(default=False)

    @model_validator(mode="after")
    def _validate_shape(self) -> Self:
        if (self.backend_id is None) == (self.endpoint_url is None):
            raise ValueError(
                f"voter {self.voter_id!r} must name exactly one of backend_id "
                "or endpoint_url"
            )
        if self.model_id_source == "declared" and not self.api_model_id:
            raise ValueError(
                f"voter {self.voter_id!r} declares model_id_source 'declared' "
                "but no api_model_id"
            )
        if self.model_id_source == "served" and self.api_model_id:
            raise ValueError(
                f"voter {self.voter_id!r} reads its model from the endpoint "
                "(model_id_source 'served') and must not also declare "
                f"api_model_id {self.api_model_id!r}"
            )
        return self


__all__ = ["VOTER_ID_PATTERN", "ModelReviewVoter"]
