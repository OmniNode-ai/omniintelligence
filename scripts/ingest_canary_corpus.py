# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Canary corpus ingestion script — OMN-7848.

Ingests a controlled set of files from the corpus manifest into code_entities
and tags them with canary_id for scoped analysis.

Usage:
    uv run python scripts/ingest_canary_corpus.py --dry-run
    uv run python scripts/ingest_canary_corpus.py --execute

Output:
    .onex_state/canary/ingestion-counts.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OMNI_HOME = Path(os.environ.get("OMNI_HOME", Path(__file__).resolve().parents[2]))
MANIFEST_PATH = OMNI_HOME / ".onex_state" / "canary" / "corpus-manifest.json"
COUNTS_PATH = OMNI_HOME / ".onex_state" / "canary" / "ingestion-counts.json"
CANARY_ID = "node-classes-v1"


def _resolve_file_path(manifest_path: str) -> Path:
    """Resolve a manifest path (e.g. 'omnibase_core/src/...') to absolute."""
    # manifest paths are repo-relative, e.g. "omnibase_core/src/.../node_compute.py"
    return OMNI_HOME / manifest_path


def _extract_repo_from_path(manifest_path: str) -> str:
    """Extract repo name from manifest path prefix."""
    return manifest_path.split("/")[0]


def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _ingest_python_file(
    file_path: Path,
    manifest_path: str,
    source_repo: str,
) -> dict[str, Any] | None:
    """Extract AST entities from a Python file and return ingestion result dict."""
    from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_extract_ast import (
        extract_entities_from_source,
    )

    try:
        source_code = file_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Cannot read %s: %s", file_path, e)
        return None

    file_hash = _compute_hash(source_code)
    # relative path within the repo (strip repo prefix)
    relative_path = "/".join(manifest_path.split("/")[1:])

    result = extract_entities_from_source(
        source_code,
        file_path=relative_path,
        source_repo=source_repo,
        file_hash=file_hash,
    )

    return {
        "entities": [e.model_dump() for e in result.entities],
        "relationships": result.relationships,
        "source_repo": source_repo,
        "source_path": relative_path,
        "file_hash": file_hash,
        "manifest_path": manifest_path,
    }


def _ingest_yaml_file(
    file_path: Path,
    manifest_path: str,
    source_repo: str,
    role: str,
    description: str,
) -> dict[str, Any] | None:
    """Represent a YAML file as a synthetic code entity (contract declaration)."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Cannot read %s: %s", file_path, e)
        return None

    file_hash = _compute_hash(content)
    relative_path = "/".join(manifest_path.split("/")[1:])
    entity_name = file_path.name
    qualified_name = f"{source_repo}.{relative_path.replace('/', '.').replace('.yaml', '')}"

    # Synthetic entity representing the contract YAML
    entity = {
        "entity_name": entity_name,
        "entity_type": "contract_yaml",
        "qualified_name": qualified_name,
        "source_repo": source_repo,
        "source_path": relative_path,
        "line_number": None,
        "bases": None,
        "methods": None,
        "fields": None,
        "decorators": None,
        "docstring": description,
        "signature": None,
        "file_hash": file_hash,
    }

    return {
        "entities": [entity],
        "relationships": [],
        "source_repo": source_repo,
        "source_path": relative_path,
        "file_hash": file_hash,
        "manifest_path": manifest_path,
    }


def cmd_dry_run(manifest: dict) -> None:
    """Print what would be ingested without writing to DB."""
    files = manifest["files"]
    print(f"\n{'=' * 60}")
    print(f"Canary Corpus Dry Run — {CANARY_ID}")
    print(f"{'=' * 60}")
    print(f"\nFiles in manifest: {len(files)}")

    total_entities = 0
    errors = []

    for entry in files:
        manifest_path = entry["path"]
        role = entry["role"]
        file_path = _resolve_file_path(manifest_path)

        if not file_path.exists():
            errors.append(f"MISSING: {manifest_path}")
            print(f"  [MISSING] {manifest_path}")
            continue

        if manifest_path.endswith(".py"):
            result = _ingest_python_file(file_path, manifest_path, _extract_repo_from_path(manifest_path))
            if result:
                n = len(result["entities"])
                total_entities += n
                print(f"  [{role:20s}] {manifest_path} -> {n} entities")
            else:
                errors.append(f"PARSE_ERROR: {manifest_path}")
                print(f"  [ERROR] {manifest_path}")
        elif manifest_path.endswith(".yaml"):
            print(f"  [{role:20s}] {manifest_path} -> 1 entity (contract_yaml)")
            total_entities += 1
        else:
            print(f"  [{role:20s}] {manifest_path} -> 1 entity (other)")
            total_entities += 1

    print(f"\nTotal entities that would be ingested: ~{total_entities}")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
    print()


async def cmd_execute(manifest: dict) -> None:
    """Run ingestion and write counts to ingestion-counts.json."""
    import asyncpg

    from omniintelligence.nodes.node_ast_extraction_compute.repository.repository_code_entity import (
        RepositoryCodeEntity,
    )

    db_url = os.environ.get("OMNIINTELLIGENCE_DB_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: OMNIINTELLIGENCE_DB_URL must be set", file=sys.stderr)
        sys.exit(1)

    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
    repo_db = RepositoryCodeEntity(pool)

    files = manifest["files"]
    files_in_manifest = len(files)
    documents_ingested = 0
    entities_persisted = 0
    relationships_persisted = 0
    errors: list[str] = []
    ingested_entity_ids: list[str] = []

    print(f"\n{'=' * 60}")
    print(f"Canary Corpus Ingestion — {CANARY_ID}")
    print(f"{'=' * 60}")
    print(f"\nIngesting {files_in_manifest} files from manifest...\n")

    try:
        for entry in files:
            manifest_path = entry["path"]
            role = entry["role"]
            description = entry.get("description", "")
            source_repo = _extract_repo_from_path(manifest_path)
            file_path = _resolve_file_path(manifest_path)

            if not file_path.exists():
                msg = f"File not found: {manifest_path}"
                logger.warning(msg)
                errors.append(msg)
                continue

            if manifest_path.endswith(".py"):
                result = _ingest_python_file(file_path, manifest_path, source_repo)
            elif manifest_path.endswith(".yaml"):
                result = _ingest_yaml_file(file_path, manifest_path, source_repo, role, description)
            else:
                result = _ingest_python_file(file_path, manifest_path, source_repo)

            if result is None:
                msg = f"Failed to process: {manifest_path}"
                errors.append(msg)
                continue

            documents_ingested += 1
            entity_id_map: dict[str, str] = {}

            for entity in result["entities"]:
                try:
                    db_id = await repo_db.upsert_entity(entity)
                    entity_id_map[entity["qualified_name"]] = db_id
                    ingested_entity_ids.append(db_id)
                    entities_persisted += 1
                except Exception as exc:
                    msg = f"Entity upsert failed for {entity.get('qualified_name', '?')}: {exc}"
                    logger.debug(msg)
                    errors.append(msg)

            for rel in result.get("relationships", []):
                rel_dict = rel if isinstance(rel, dict) else rel.__dict__ if hasattr(rel, "__dict__") else {}
                if not rel_dict and hasattr(rel, "model_dump"):
                    rel_dict = rel.model_dump()

                source_id = entity_id_map.get(rel_dict.get("source_entity", ""))
                target_id = entity_id_map.get(rel_dict.get("target_entity", ""))

                if source_id and target_id:
                    try:
                        await repo_db.upsert_relationship({
                            "source_entity_id": source_id,
                            "target_entity_id": target_id,
                            "relationship_type": rel_dict.get("relationship_type"),
                            "trust_tier": rel_dict.get("trust_tier"),
                            "confidence": rel_dict.get("confidence"),
                            "evidence": rel_dict.get("evidence"),
                            "inject_into_context": rel_dict.get("inject_into_context", True),
                            "source_repo": source_repo,
                        })
                        relationships_persisted += 1
                    except Exception as exc:
                        logger.debug("Relationship upsert failed: %s", exc)

            print(f"  [{role:20s}] {Path(manifest_path).name} -> {len(result['entities'])} entities")

        # Tag all ingested entities with canary_id via enrichment_metadata
        if ingested_entity_ids:
            print(f"\nTagging {len(ingested_entity_ids)} entities with canary_id={CANARY_ID}...")
            id_list = [str(eid) for eid in ingested_entity_ids]
            # Batch update in chunks to avoid parameter limit
            chunk_size = 100
            tagged = 0
            async with pool.acquire() as conn:
                for i in range(0, len(id_list), chunk_size):
                    chunk = id_list[i:i + chunk_size]
                    placeholders = ", ".join(f"${j+1}" for j in range(len(chunk)))
                    await conn.execute(
                        f"""
                        UPDATE code_entities
                        SET enrichment_metadata = COALESCE(enrichment_metadata, '{{}}'::jsonb) ||
                            jsonb_build_object('canary_id', '{CANARY_ID}')
                        WHERE id::text IN ({placeholders})
                        """,
                        *chunk,
                    )
                    tagged += len(chunk)
            print(f"  Tagged {tagged} entities.")

    finally:
        await pool.close()

    print(f"\n{'=' * 60}")
    print("Ingestion Complete")
    print(f"{'=' * 60}")
    print(f"  Files in manifest:       {files_in_manifest}")
    print(f"  Documents ingested:      {documents_ingested}")
    print(f"  Entities persisted:      {entities_persisted}")
    print(f"  Relationships persisted: {relationships_persisted}")
    print(f"  Errors:                  {len(errors)}")
    if errors:
        print("\nErrors:")
        for e in errors[:10]:
            print(f"  {e}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    # Write ingestion counts
    counts = {
        "canary_id": CANARY_ID,
        "files_in_manifest": files_in_manifest,
        "documents_ingested": documents_ingested,
        "entities_persisted": entities_persisted,
        "relationships_persisted": relationships_persisted,
        "discovery_events_emitted": 0,
        "errors": errors[:20],
        "ingestion_command": (
            f"cd $OMNI_HOME/omniintelligence && "
            f"OMNIINTELLIGENCE_DB_URL=<url> "
            f"uv run python scripts/ingest_canary_corpus.py --execute"
        ),
        "discovery_command": "n/a — pattern discovery runs via learned_patterns table (session-based pipeline); "
                             "code entity ingestion feeds code_entities table for future pattern extraction",
        "notes": [
            "code_entities table was missing — migrations 025-028 applied as prerequisite",
            "YAML contract files ingested as synthetic contract_yaml entities",
            "All entities tagged via enrichment_metadata.canary_id = 'node-classes-v1'",
        ],
    }

    COUNTS_PATH.write_text(json.dumps(counts, indent=2))
    print(f"\nCounts written to: {COUNTS_PATH}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Ingest canary corpus ({CANARY_ID}) into code_entities."
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without DB writes.")
    parser.add_argument("--execute", action="store_true", help="Run ingestion and write counts.")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.error("Specify --dry-run or --execute")

    if not MANIFEST_PATH.exists():
        print(f"ERROR: Manifest not found at {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(MANIFEST_PATH) as f:  # noqa: PTH123
        manifest = json.load(f)

    if args.dry_run:
        cmd_dry_run(manifest)
    elif args.execute:
        asyncio.run(cmd_execute(manifest))


if __name__ == "__main__":
    main()
