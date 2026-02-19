"""Result model for ID-only queries."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ModelIdResult(BaseModel):
    """Result model for ID-only queries.

    Used by operations that return only a pattern UUID (e.g., check_exists_by_id).
    Returns a single UUID field from the database.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    id: UUID


__all__ = ["ModelIdResult"]
