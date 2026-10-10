# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Input of the review voters overlay node (OMN-20910)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelReviewVotersOverlayRequest(BaseModel):
    """The overlay text and the delegation overlay text it names.

    The handler is pure: whoever builds the request reads the files. The
    sources are used only in messages.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    overlay_yaml: str = Field(description="The review voters overlay, as text.")
    overlay_source: str = Field(description="Where the overlay was read from.")
    backend_overlay_yaml: str | None = Field(
        default=None,
        description="The delegation overlay the overlay names, as text; None "
        "when the overlay names none or it could not be read.",
    )
    backend_overlay_source: str = Field(default="")


__all__ = ["ModelReviewVotersOverlayRequest"]
