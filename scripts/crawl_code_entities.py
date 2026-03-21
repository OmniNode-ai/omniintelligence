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

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _load_crawl_config() -> "ModelCrawlConfig":
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

    print(f"\n{'='*60}")
    print("Code Entity Crawl — Dry Run")
    print(f"{'='*60}")
    print(f"\nTotal files: {len(events)}")
    print(f"\nBy repository:")
    for repo, count in sorted(repo_counts.items()):
        print(f"  {repo}: {count}")
    print(f"\nBy extension:")
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

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
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
    """Run the full pipeline synchronously (no Kafka)."""
    from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_extract_ast import (
        extract_entities_from_source,
    )
    from omniintelligence.nodes.node_code_crawler_effect.handlers.handler_crawl_files import (
        crawl_files,
    )

    config = _load_crawl_config()

    total_files = 0
    total_entities = 0
    total_relationships = 0
    repo_stats: dict[str, dict[str, int]] = {}

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
            }
        repo_stats[event.repo_name]["files"] += 1
        repo_stats[event.repo_name]["entities"] += len(result.entities)
        repo_stats[event.repo_name]["relationships"] += len(result.relationships)

    print(f"\n{'='*60}")
    print("Code Entity Crawl — Sync Execution (extract only, no persist)")
    print(f"{'='*60}")
    print(f"\nTotal: {total_files} files, {total_entities} entities, {total_relationships} relationships")
    print(f"\nBy repository:")
    for repo, stats in sorted(repo_stats.items()):
        print(
            f"  {repo}: {stats['files']} files, "
            f"{stats['entities']} entities, "
            f"{stats['relationships']} relationships"
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
