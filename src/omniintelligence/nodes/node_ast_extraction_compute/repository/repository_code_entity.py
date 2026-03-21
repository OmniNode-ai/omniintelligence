# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Repository for code entity and relationship persistence.

Uses asyncpg connection pool. Entity identity: (qualified_name, source_repo).
Upserts update in-place on file change. file_hash used for skip-if-unchanged.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)


class RepositoryCodeEntity:
    """Repository for code entity and relationship persistence.

    Uses asyncpg connection pool. Entity identity: (qualified_name, source_repo).
    Upserts update in-place on file change. file_hash used for skip-if-unchanged.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def check_file_hash(
        self, qualified_name: str, source_repo: str, file_hash: str
    ) -> bool:
        """Return True if entity exists with matching file_hash (skip optimization)."""
        row = await self._pool.fetchrow(
            "SELECT 1 FROM code_entities "
            "WHERE qualified_name = $1 AND source_repo = $2 AND file_hash = $3",
            qualified_name,
            source_repo,
            file_hash,
        )
        return row is not None

    async def upsert_entity(self, entity: dict[str, Any]) -> str:
        """Upsert entity using ON CONFLICT (qualified_name, source_repo) DO UPDATE.

        Returns entity UUID as string.
        """
        methods_json = (
            json.dumps(entity.get("methods"))
            if entity.get("methods") is not None
            else None
        )
        fields_json = (
            json.dumps(entity.get("fields"))
            if entity.get("fields") is not None
            else None
        )

        row = await self._pool.fetchrow(
            """
            INSERT INTO code_entities (
                entity_name, entity_type, qualified_name, source_repo, source_path,
                line_number, bases, methods, fields, decorators, docstring, signature,
                file_hash, last_extracted_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10, $11, $12, $13, NOW(), NOW())
            ON CONFLICT (qualified_name, source_repo) DO UPDATE SET
                entity_name = EXCLUDED.entity_name,
                entity_type = EXCLUDED.entity_type,
                source_path = EXCLUDED.source_path,
                line_number = EXCLUDED.line_number,
                bases = EXCLUDED.bases,
                methods = EXCLUDED.methods,
                fields = EXCLUDED.fields,
                decorators = EXCLUDED.decorators,
                docstring = EXCLUDED.docstring,
                signature = EXCLUDED.signature,
                file_hash = EXCLUDED.file_hash,
                last_extracted_at = NOW(),
                updated_at = NOW()
            RETURNING id
            """,
            entity["entity_name"],
            entity["entity_type"],
            entity["qualified_name"],
            entity["source_repo"],
            entity["source_path"],
            entity.get("line_number"),
            entity.get("bases"),
            methods_json,
            fields_json,
            entity.get("decorators"),
            entity.get("docstring"),
            entity.get("signature"),
            entity["file_hash"],
        )
        return str(row["id"])

    async def upsert_relationship(self, relationship: dict[str, Any]) -> str:
        """Upsert relationship using ON CONFLICT DO UPDATE.

        Returns relationship UUID as string.
        """
        row = await self._pool.fetchrow(
            """
            INSERT INTO code_relationships (
                source_entity_id, target_entity_id, relationship_type,
                trust_tier, confidence, evidence, inject_into_context, source_repo,
                updated_at
            ) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, NOW())
            ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO UPDATE SET
                trust_tier = EXCLUDED.trust_tier,
                confidence = EXCLUDED.confidence,
                evidence = EXCLUDED.evidence,
                inject_into_context = EXCLUDED.inject_into_context,
                source_repo = EXCLUDED.source_repo,
                updated_at = NOW()
            RETURNING id
            """,
            relationship["source_entity_id"],
            relationship["target_entity_id"],
            relationship["relationship_type"],
            relationship.get("trust_tier", "strong"),
            relationship.get("confidence", 1.0),
            relationship.get("evidence"),
            relationship.get("inject_into_context", True),
            relationship["source_repo"],
        )
        return str(row["id"])

    async def get_entity_id_by_qualified_name(
        self, qualified_name: str, source_repo: str
    ) -> str | None:
        """Look up entity UUID by qualified name + repo."""
        row = await self._pool.fetchrow(
            "SELECT id FROM code_entities WHERE qualified_name = $1 AND source_repo = $2",
            qualified_name,
            source_repo,
        )
        return str(row["id"]) if row else None

    async def delete_stale_entities(
        self,
        source_path: str,
        source_repo: str,
        current_qualified_names: list[str],
    ) -> int:
        """Delete entities for a file that are no longer present (zombie cleanup).

        Only call after successful parse. Returns count deleted.
        """
        if current_qualified_names:
            result = await self._pool.execute(
                """
                DELETE FROM code_entities
                WHERE source_path = $1
                  AND source_repo = $2
                  AND qualified_name != ALL($3)
                """,
                source_path,
                source_repo,
                current_qualified_names,
            )
        else:
            result = await self._pool.execute(
                """
                DELETE FROM code_entities
                WHERE source_path = $1
                  AND source_repo = $2
                """,
                source_path,
                source_repo,
            )
        # asyncpg execute returns "DELETE N"
        return int(result.split()[-1])

    async def delete_stale_relationships_for_file(
        self,
        source_path: str,
        source_repo: str,
        current_relationship_keys: list[tuple[str, str, str]],
    ) -> int:
        """Delete relationships whose source file was re-extracted and whose edges are no longer emitted.

        current_relationship_keys: list of (source_qualified_name, target_qualified_name, relationship_type).
        Returns count deleted.
        """
        # Get all source entity IDs for this file
        source_ids = await self._pool.fetch(
            "SELECT id FROM code_entities WHERE source_path = $1 AND source_repo = $2",
            source_path,
            source_repo,
        )
        if not source_ids:
            return 0

        source_id_list = [row["id"] for row in source_ids]

        if current_relationship_keys:
            # Build a set of (source_entity_id, target_entity_id, relationship_type) to keep
            # by resolving qualified names to entity IDs
            keep_tuples: list[tuple[str, str, str]] = []
            for src_qn, tgt_qn, rel_type in current_relationship_keys:
                src_id = await self.get_entity_id_by_qualified_name(src_qn, source_repo)
                tgt_id = await self.get_entity_id_by_qualified_name(tgt_qn, source_repo)
                if src_id and tgt_id:
                    keep_tuples.append((src_id, tgt_id, rel_type))

            if keep_tuples:
                # Delete relationships from source entities in this file that are not in the keep set
                # We use a CTE to express the keep set
                keep_src = [t[0] for t in keep_tuples]
                keep_tgt = [t[1] for t in keep_tuples]
                keep_rel = [t[2] for t in keep_tuples]

                result = await self._pool.execute(
                    """
                    DELETE FROM code_relationships cr
                    WHERE cr.source_entity_id = ANY($1::uuid[])
                      AND NOT EXISTS (
                          SELECT 1
                          FROM unnest($2::uuid[], $3::uuid[], $4::text[]) AS keep(src, tgt, rel)
                          WHERE cr.source_entity_id = keep.src
                            AND cr.target_entity_id = keep.tgt
                            AND cr.relationship_type = keep.rel
                      )
                    """,
                    source_id_list,
                    keep_src,
                    keep_tgt,
                    keep_rel,
                )
            else:
                # No valid keep tuples means delete all relationships from these source entities
                result = await self._pool.execute(
                    "DELETE FROM code_relationships WHERE source_entity_id = ANY($1::uuid[])",
                    source_id_list,
                )
        else:
            # No current relationships means delete all from these source entities
            result = await self._pool.execute(
                "DELETE FROM code_relationships WHERE source_entity_id = ANY($1::uuid[])",
                source_id_list,
            )
        return int(result.split()[-1])

    async def get_entities_needing_enrichment(
        self, limit: int = 25
    ) -> list[dict[str, Any]]:
        """Get entities where classification IS NULL, ordered by last_extracted_at."""
        rows = await self._pool.fetch(
            """
            SELECT id, entity_name, entity_type, qualified_name, source_repo,
                   source_path, docstring, signature, bases, methods, fields, decorators
            FROM code_entities
            WHERE classification IS NULL
            ORDER BY last_extracted_at ASC
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]

    async def get_entities_needing_embedding(
        self, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get entities where last_embedded_at IS NULL or last_embedded_at < last_extracted_at."""
        rows = await self._pool.fetch(
            """
            SELECT id, entity_name, entity_type, qualified_name, source_repo,
                   source_path, docstring, signature, classification, llm_description
            FROM code_entities
            WHERE last_embedded_at IS NULL OR last_embedded_at < last_extracted_at
            ORDER BY last_extracted_at ASC
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]

    async def get_all_entities_and_relationships(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Get all entities and injectable relationships for Memgraph rebuild."""
        entity_rows = await self._pool.fetch(
            """
            SELECT id, entity_name, entity_type, qualified_name, source_repo,
                   source_path, classification, architectural_pattern
            FROM code_entities
            """
        )
        relationship_rows = await self._pool.fetch(
            """
            SELECT cr.id, cr.source_entity_id, cr.target_entity_id,
                   cr.relationship_type, cr.trust_tier, cr.confidence,
                   cr.source_repo
            FROM code_relationships cr
            WHERE cr.inject_into_context = true
            """
        )
        return [dict(r) for r in entity_rows], [dict(r) for r in relationship_rows]

    async def update_enrichment(
        self,
        entity_id: str,
        classification: str,
        llm_description: str,
        architectural_pattern: str,
        classification_confidence: float,
        enrichment_version: str,
    ) -> None:
        """Update enrichment fields and set last_enriched_at."""
        await self._pool.execute(
            """
            UPDATE code_entities SET
                classification = $2,
                llm_description = $3,
                architectural_pattern = $4,
                classification_confidence = $5,
                enrichment_version = $6,
                last_enriched_at = NOW(),
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            entity_id,
            classification,
            llm_description,
            architectural_pattern,
            classification_confidence,
            enrichment_version,
        )

    async def update_embedded_at(self, entity_ids: list[str]) -> None:
        """Batch update last_embedded_at for entities that were just embedded."""
        await self._pool.execute(
            """
            UPDATE code_entities SET
                last_embedded_at = NOW(),
                updated_at = NOW()
            WHERE id = ANY($1::uuid[])
            """,
            entity_ids,
        )

    async def update_deterministic_classification(
        self,
        entity_id: str,
        node_type: str,
        confidence: float,
        alternatives: str,
        enrichment_meta_patch: str,
    ) -> None:
        """Update deterministic classification columns and enrichment metadata.

        Args:
            entity_id: UUID of the entity.
            node_type: Classified node type (e.g. 'effect', 'compute').
            confidence: Classification confidence (0.0-1.0).
            alternatives: JSONB string of alternative classifications.
            enrichment_meta_patch: JSONB string to merge into enrichment_metadata.
        """
        await self._pool.execute(
            """
            UPDATE code_entities SET
                deterministic_node_type = $2,
                deterministic_confidence = $3,
                deterministic_alternatives = $4::jsonb,
                enrichment_metadata = enrichment_metadata || $5::jsonb,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            entity_id,
            node_type,
            confidence,
            alternatives,
            enrichment_meta_patch,
        )

    async def update_quality_score(
        self,
        entity_id: str,
        quality_score: float,
        quality_dimensions: str,
        enrichment_meta_patch: str,
    ) -> None:
        """Update quality scoring columns and enrichment metadata.

        Args:
            entity_id: UUID of the entity.
            quality_score: Overall quality score (0.0-1.0).
            quality_dimensions: JSONB string of per-dimension scores.
            enrichment_meta_patch: JSONB string to merge into enrichment_metadata.
        """
        await self._pool.execute(
            """
            UPDATE code_entities SET
                quality_score = $2,
                quality_dimensions = $3::jsonb,
                enrichment_metadata = enrichment_metadata || $4::jsonb,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            entity_id,
            quality_score,
            quality_dimensions,
            enrichment_meta_patch,
        )

    async def get_entity_enrichment_metadata(
        self, entity_id: str
    ) -> dict[str, Any] | None:
        """Get enrichment metadata and file_hash for idempotency checks."""
        row = await self._pool.fetchrow(
            "SELECT file_hash, enrichment_metadata FROM code_entities WHERE id = $1::uuid",
            entity_id,
        )
        if not row:
            return None
        meta = row["enrichment_metadata"]
        return {
            "file_hash": row["file_hash"],
            "enrichment_metadata": meta if isinstance(meta, dict) else {},
        }

    async def get_entities_by_ids(self, entity_ids: list[str]) -> list[dict[str, Any]]:
        """Get entities by IDs for enrichment processing."""
        rows = await self._pool.fetch(
            """
            SELECT id, entity_name, entity_type, qualified_name, source_repo,
                   source_path, docstring, signature, bases, methods, fields,
                   decorators, file_hash, enrichment_metadata
            FROM code_entities
            WHERE id = ANY($1::uuid[])
            """,
            entity_ids,
        )
        return [dict(row) for row in rows]

    async def update_graph_synced_at(self, entity_ids: list[str]) -> None:
        """Batch update last_graph_synced_at for entities synced to Memgraph."""
        await self._pool.execute(
            """
            UPDATE code_entities SET
                last_graph_synced_at = NOW(),
                updated_at = NOW()
            WHERE id = ANY($1::uuid[])
            """,
            entity_ids,
        )
