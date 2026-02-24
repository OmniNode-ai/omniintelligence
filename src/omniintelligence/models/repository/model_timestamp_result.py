# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Result model for timestamp queries."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelTimestampResult(BaseModel):
    """Result model for timestamp queries.

    Used by operations that return timestamps (e.g., get_stored_at).
    The timestamp can be None when no matching pattern exists.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    created_at: datetime | None = None


__all__ = ["ModelTimestampResult"]
