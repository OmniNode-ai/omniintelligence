"""Result model for version queries."""

from pydantic import BaseModel, ConfigDict


class ModelVersionResult(BaseModel):
    """Result model for version queries.

    Used by operations that return version numbers (e.g., get_latest_version).
    The version can be None when no patterns exist (MAX aggregate on empty set).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    version: int | None = None


__all__ = ["ModelVersionResult"]
