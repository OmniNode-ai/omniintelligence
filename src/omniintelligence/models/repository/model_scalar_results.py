"""Minimal result models for scalar database queries.

These models are used by the PostgresRepositoryRuntime to map single-value
or few-column query results to typed Python objects. They are intentionally
minimal to avoid the overhead of full row models (e.g., PatternRow with 29 fields)
when only 1-2 columns are needed.

Affected operations:
- check_exists: Returns {exists: bool}
- check_exists_by_id: Returns {id: UUID}
- get_latest_version: Returns {version: int | None}
- get_stored_at: Returns {created_at: datetime | None}
"""

from datetime import datetime
from uuid import UUID

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


__all__ = [
    "ModelExistsResult",
    "ModelIdResult",
    "ModelTimestampResult",
    "ModelVersionResult",
]
