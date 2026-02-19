"""Result model for EXISTS queries."""

from pydantic import BaseModel, ConfigDict


class ModelExistsResult(BaseModel):
    """Result model for EXISTS queries.

    Used by operations that check if a pattern exists by signature hash.
    Returns a single boolean field from the database.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    exists: bool


__all__ = ["ModelExistsResult"]
