# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Protocol for code entity storage operations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_relationship import (
    ModelCodeRelationship,
)


@runtime_checkable
class ProtocolCodeEntityStore(Protocol):
    """Protocol for code entity persistence operations."""

    async def upsert_entity(self, entity: ModelCodeEntity) -> str:
        """Upsert a code entity. Returns the entity ID."""
        ...

    async def upsert_relationship(self, relationship: ModelCodeRelationship) -> str:
        """Upsert a code relationship. Returns the relationship ID."""
        ...

    async def delete_entities_by_file(self, source_repo: str, file_path: str) -> int:
        """Delete all entities for a file. Returns count deleted."""
        ...

    async def get_entities_by_repo(
        self, source_repo: str, *, limit: int = 1000
    ) -> list[ModelCodeEntity]:
        """Get entities by repository."""
        ...

    async def get_entities_by_file(
        self, source_repo: str, file_path: str
    ) -> list[ModelCodeEntity]:
        """Get entities by file."""
        ...


__all__ = ["ProtocolCodeEntityStore"]
