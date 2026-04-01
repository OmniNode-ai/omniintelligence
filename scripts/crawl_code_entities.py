# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CLI script for batch code entity crawling.

Usage:
  uv run python scripts/crawl_code_entities.py --dry-run
  uv run python scripts/crawl_code_entities.py --execute
  uv run python scripts/crawl_code_entities.py --execute --sync
  uv run python scripts/crawl_code_entities.py --repo omniintelligence --execute

Related:
    - OMN-5718: CLI script — batch crawl
    - OMN-5720: AST-based code pattern extraction (epic)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_config import (
        ModelCrawlConfig,
    )

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _load_crawl_config() -> ModelCrawlConfig:
    """Load crawl config from the crawler contract YAML."""
    import yaml

    from omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_config import (
        ModelCrawlConfig,
        ModelRepoCrawlConfig,
    )

    contract_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "omniintelligence"
        / "nodes"
        / "node_code_crawler_effect"
        / "contract.yaml"
    )

    if not contract_path.exists():
        logger.error("Crawler contract not found at %s", contract_path)
        sys.exit(1)

    with open(contract_path) as f:  # noqa: PTH123
        raw = yaml.safe_load(f)

    config_section = raw.get("config", {})
    repos = []
    for repo_raw in config_section.get("repos", []):
        repos.append(ModelRepoCrawlConfig(**repo_raw))

    return ModelCrawlConfig(repos=repos)


def cmd_dry_run(repo_filter: str | None = None) -> None:
    """List files that would be crawled without side effects."""
    from omniintelligence.nodes.node_code_crawler_effect.handlers.handler_crawl_files import (
        crawl_files,
    )

    config = _load_crawl_config()
    events = list(crawl_files(config, repo_filter=repo_filter))

    # Count by repo and extension
    repo_counts: Counter[str] = Counter()
    ext_counts: Counter[str] = Counter()
    for event in events:
        repo_counts[event.repo_name] += 1
        ext_counts[event.file_extension] += 1

    print(f"\n{'=' * 60}")
    print("Code Entity Crawl — Dry Run")
    print(f"{'=' * 60}")
    print(f"\nTotal files: {len(events)}")
    print("\nBy repository:")
    for repo, count in sorted(repo_counts.items()):
        print(f"  {repo}: {count}")
    print("\nBy extension:")
    for ext, count in sorted(ext_counts.items()):
        print(f"  {ext}: {count}")
    print()


async def cmd_execute_kafka(repo_filter: str | None = None) -> None:
    """Emit code-crawl-requested command to Kafka."""
    import json
    import os

    try:
        from confluent_kafka import Producer
    except ImportError:
        logger.error("confluent_kafka not installed. Use --sync for local execution.")
        sys.exit(1)

    from omniintelligence.constants import TOPIC_CODE_CRAWL_REQUESTED_V1

    bootstrap_servers = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
    producer = Producer({"bootstrap.servers": bootstrap_servers})

    topic = TOPIC_CODE_CRAWL_REQUESTED_V1
    payload = {"crawl_id": f"crawl_cli_{hashlib.sha256(b'batch').hexdigest()[:8]}"}
    if repo_filter:
        payload["repo_filter"] = repo_filter

    producer.produce(
        topic=topic,
        key="cli-batch-crawl",
        value=json.dumps(payload).encode("utf-8"),
    )
    producer.flush()

    print(f"Emitted code-crawl-requested command to {topic}")
    print(f"  bootstrap_servers: {bootstrap_servers}")
    print(f"  payload: {payload}")


async def cmd_execute_sync(repo_filter: str | None = None) -> None:
    """Run the full pipeline synchronously with Postgres persistence."""
    import os

    import asyncpg

    from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_extract_ast import (
        extract_entities_from_source,
    )
    from omniintelligence.nodes.node_ast_extraction_compute.repository.repository_code_entity import (
        RepositoryCodeEntity,
    )
    from omniintelligence.nodes.node_code_crawler_effect.handlers.handler_crawl_files import (
        crawl_files,
    )

    config = _load_crawl_config()

    # Connect to Postgres
    db_url = os.environ.get("OMNIINTELLIGENCE_DB_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        print(
            "ERROR: OMNIINTELLIGENCE_DB_URL or DATABASE_URL must be set",
            file=sys.stderr,
        )  # noqa: T201
        sys.exit(1)
    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
    repo_db = RepositoryCodeEntity(pool)

    total_files = 0
    total_entities = 0
    total_relationships = 0
    total_persisted_entities = 0
    total_persisted_relationships = 0
    total_skipped = 0
    repo_stats: dict[str, dict[str, int]] = {}

    try:
        for event in crawl_files(config, repo_filter=repo_filter):
            # Resolve file path
            repo_config = next(
                (r for r in config.repos if r.name == event.repo_name), None
            )
            if repo_config is None:
                continue

            full_path = Path(repo_config.path) / event.file_path
            if not full_path.exists():
                continue

            # Read and extract
            source_code = full_path.read_text(encoding="utf-8", errors="replace")
            result = extract_entities_from_source(
                source_code,
                file_path=event.file_path,
                source_repo=event.repo_name,
                file_hash=event.file_hash,
            )

            total_files += 1
            total_entities += len(result.entities)
            total_relationships += len(result.relationships)

            if event.repo_name not in repo_stats:
                repo_stats[event.repo_name] = {
                    "files": 0,
                    "entities": 0,
                    "relationships": 0,
                    "persisted_entities": 0,
                    "persisted_relationships": 0,
                }
            repo_stats[event.repo_name]["files"] += 1
            repo_stats[event.repo_name]["entities"] += len(result.entities)
            repo_stats[event.repo_name]["relationships"] += len(result.relationships)

            # Persist entities
            entity_id_map: dict[str, str] = {}  # qualified_name -> db UUID
            for entity in result.entities:
                entity_dict = entity.model_dump()
                try:
                    db_id = await repo_db.upsert_entity(entity_dict)
                    entity_id_map[entity.qualified_name] = db_id
                    total_persisted_entities += 1
                    repo_stats[event.repo_name]["persisted_entities"] += 1
                except Exception as exc:
                    logger.debug(
                        "Failed to upsert entity %s: %s", entity.qualified_name, exc
                    )

            # Persist relationships (resolve qualified names to entity IDs)
            for rel in result.relationships:
                source_id = entity_id_map.get(rel.source_entity)
                target_id = entity_id_map.get(rel.target_entity)

                # If target not in current file's entities, look up in DB
                if source_id and not target_id:
                    target_id = await repo_db.get_entity_id_by_qualified_name(
                        rel.target_entity, event.repo_name
                    )
                if target_id and not source_id:
                    source_id = await repo_db.get_entity_id_by_qualified_name(
                        rel.source_entity, event.repo_name
                    )

                if source_id and target_id:
                    try:
                        await repo_db.upsert_relationship(
                            {
                                "source_entity_id": source_id,
                                "target_entity_id": target_id,
                                "relationship_type": rel.relationship_type,
                                "trust_tier": rel.trust_tier,
                                "confidence": rel.confidence,
                                "evidence": rel.evidence,
                                "inject_into_context": rel.inject_into_context,
                                "source_repo": event.repo_name,
                            }
                        )
                        total_persisted_relationships += 1
                        repo_stats[event.repo_name]["persisted_relationships"] += 1
                    except Exception as exc:
                        logger.debug(
                            "Failed to upsert relationship %s->%s: %s",
                            rel.source_entity,
                            rel.target_entity,
                            exc,
                        )
                else:
                    total_skipped += 1

            # Progress indicator every 100 files
            if total_files % 100 == 0:
                print(
                    f"  ... processed {total_files} files, {total_persisted_entities} entities persisted"
                )

        # Clean up stale entities per file is deferred to a separate sweep

    finally:
        await pool.close()

    print(f"\n{'=' * 60}")
    print("Code Entity Crawl — Sync Execution (with persistence)")
    print(f"{'=' * 60}")
    print(
        f"\nExtracted: {total_files} files, {total_entities} entities, {total_relationships} relationships"
    )
    print(
        f"Persisted: {total_persisted_entities} entities, {total_persisted_relationships} relationships"
    )
    print(f"Skipped relationships (unresolved targets): {total_skipped}")
    print("\nBy repository:")
    for repo, stats in sorted(repo_stats.items()):
        print(
            f"  {repo}: {stats['files']} files, "
            f"{stats['entities']} entities ({stats['persisted_entities']} persisted), "
            f"{stats['relationships']} relationships ({stats['persisted_relationships']} persisted)"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch crawl code entities from configured repositories."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be crawled without side effects.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Emit crawl command to Kafka (or run locally with --sync).",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run pipeline synchronously without Kafka (use with --execute).",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Filter to a single repository name.",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.error("Specify --dry-run or --execute")

    if args.dry_run:
        cmd_dry_run(repo_filter=args.repo)
    elif args.execute and args.sync:
        asyncio.run(cmd_execute_sync(repo_filter=args.repo))
    elif args.execute:
        asyncio.run(cmd_execute_kafka(repo_filter=args.repo))


if __name__ == "__main__":
    main()
