# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Dispatch handler for Memgraph type graph storage.

Reads entities and relationships from Postgres (source of truth) and writes
to Memgraph as a queryable graph. Memgraph is a derived index — if it drifts
or crashes, rebuild from Postgres.

Graph config:
  Node labels: Class, Protocol, Model, Function, Module, Constant, Entity
  Edge types: INHERITS, IMPLEMENTS, IMPORTS, CALLS, DEFINES
  Only writes relationships where inject_into_context = true
  (already filtered by repository.get_all_entities_and_relationships)

Architecture Decisions:
    - Split file: NOT in dispatch_handlers.py (already large)
    - Memgraph is derived, not source of truth: full rebuild from Postgres at any time
    - MERGE for idempotency: won't duplicate nodes/edges on re-run
    - Memgraph unavailable -> graceful skip: log warning, return 0 counts (Invariant §11)
    - Label from entity_type: maps class->Class, protocol->Protocol, model->Model, etc.
    - Uses neo4j async driver: Memgraph is bolt-compatible with neo4j driver

Related:
    - OMN-5666: Memgraph type graph storage
    - OMN-5657: AST-based code pattern extraction system (epic)
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

logger = logging.getLogger(__name__)

# Entity type -> Memgraph node label mapping
ENTITY_TYPE_TO_LABEL: dict[str, str] = {
    "class": "Class",
    "protocol": "Protocol",
    "model": "Model",
    "function": "Function",
    "import": "Module",
    "constant": "Constant",
}


async def handle_graph_storage(
    *,
    repository: Any,  # RepositoryCodeEntity
    driver: AsyncDriver | None = None,
    memgraph_uri: str = "bolt://localhost:7687",
    rebuild: bool = False,
) -> dict[str, int]:
    """Sync entities and relationships from Postgres to Memgraph.

    Reads all entities and injectable relationships from the Postgres repository
    (single source of truth) and writes them to Memgraph using MERGE for
    idempotent upserts.

    Args:
        repository: Postgres repository (source of truth). Must implement
            get_all_entities_and_relationships() and update_graph_synced_at().
        driver: Optional pre-configured neo4j AsyncDriver. If None, a new
            driver is created from memgraph_uri.
        memgraph_uri: Memgraph bolt URI. Only used if driver is None.
        rebuild: If True, drop all nodes/edges and rebuild from scratch.

    Returns:
        dict with 'nodes_written' and 'edges_written' counts.
    """
    owns_driver = driver is None

    if driver is None:
        try:
            driver = AsyncGraphDatabase.driver(memgraph_uri)
            await driver.verify_connectivity()
        except Exception:
            logger.warning(
                "Memgraph unavailable at %s — skipping graph storage",
                memgraph_uri,
            )
            return {"nodes_written": 0, "edges_written": 0}

    try:
        if rebuild:
            await _rebuild_graph(driver)

        entities, relationships = await repository.get_all_entities_and_relationships()

        if not entities:
            logger.info("No entities to sync to Memgraph")
            return {"nodes_written": 0, "edges_written": 0}

        # Build entity ID -> qualified_name lookup for relationship resolution.
        # The repository returns relationships with source_entity_id and
        # target_entity_id (UUIDs), but Memgraph MATCH needs qualified_name.
        id_to_qn: dict[str, str] = {}
        for entity in entities:
            entity_id = str(entity.get("id", ""))
            qn = entity.get("qualified_name", "")
            if entity_id and qn:
                id_to_qn[entity_id] = qn

        nodes_written = 0
        edges_written = 0
        synced_ids: list[str] = []

        async with driver.session() as session:
            # Write entity nodes
            for entity in entities:
                label = ENTITY_TYPE_TO_LABEL.get(
                    entity.get("entity_type", ""), "Entity"
                )
                try:
                    await session.run(
                        f"MERGE (n:{label} {{qualified_name: $qn, source_repo: $repo}}) "
                        f"SET n.entity_name = $name, n.source_path = $path, "
                        f"n.classification = $cls, n.entity_type = $etype",
                        qn=entity.get("qualified_name", ""),
                        repo=entity.get("source_repo", ""),
                        name=entity.get("entity_name", ""),
                        path=entity.get("source_path", ""),
                        cls=entity.get("classification"),
                        etype=entity.get("entity_type", ""),
                    )
                    nodes_written += 1
                    entity_id = str(entity.get("id", ""))
                    if entity_id:
                        synced_ids.append(entity_id)
                except Exception:
                    logger.exception(
                        "Failed to write node: %s",
                        entity.get("qualified_name"),
                    )

            # Write relationship edges
            for rel in relationships:
                # Resolve entity IDs to qualified names for Memgraph MATCH
                src_qn = id_to_qn.get(str(rel.get("source_entity_id", "")), "")
                tgt_qn = id_to_qn.get(str(rel.get("target_entity_id", "")), "")
                if not src_qn or not tgt_qn:
                    logger.debug(
                        "Skipping relationship with unresolvable entity IDs: "
                        "source=%s, target=%s",
                        rel.get("source_entity_id"),
                        rel.get("target_entity_id"),
                    )
                    continue

                edge_type = rel.get("relationship_type", "RELATES_TO").upper()
                try:
                    await session.run(
                        f"MATCH (s {{qualified_name: $src_qn}}), "
                        f"(t {{qualified_name: $tgt_qn}}) "
                        f"MERGE (s)-[r:{edge_type}]->(t) "
                        f"SET r.confidence = $conf, r.trust_tier = $tier, "
                        f"r.source_repo = $repo",
                        src_qn=src_qn,
                        tgt_qn=tgt_qn,
                        conf=rel.get("confidence", 1.0),
                        tier=rel.get("trust_tier", "strong"),
                        repo=rel.get("source_repo", ""),
                    )
                    edges_written += 1
                except Exception:
                    logger.exception(
                        "Failed to write edge: %s -> %s",
                        src_qn,
                        tgt_qn,
                    )

        # Update Postgres timestamps
        if synced_ids:
            await repository.update_graph_synced_at(synced_ids)

        logger.info(
            "Graph storage complete: %d nodes, %d edges",
            nodes_written,
            edges_written,
        )
        return {"nodes_written": nodes_written, "edges_written": edges_written}

    finally:
        if owns_driver and driver is not None:
            await driver.close()


async def _rebuild_graph(driver: AsyncDriver) -> None:
    """Drop all nodes and edges, then rebuild from Postgres."""
    logger.warning("Rebuilding Memgraph graph from Postgres (full drop + replay)")
    async with driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    logger.info("Graph cleared — rebuilding from Postgres")


__all__ = [
    "ENTITY_TYPE_TO_LABEL",
    "handle_graph_storage",
]
