#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Batch crawl CLI for code entity extraction.

Emits a ``code-crawl-requested.v1`` command to Kafka to trigger the
AST-based code entity extraction pipeline.  The downstream dispatch
handler reads repo configuration from the ``node_code_crawler_effect``
contract YAML, so the command payload is intentionally minimal.

Usage:
    uv run python scripts/crawl_code_entities.py --dry-run
    uv run python scripts/crawl_code_entities.py --execute
    uv run python scripts/crawl_code_entities.py --repo omniintelligence --execute
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.resources
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import yaml


# ---------------------------------------------------------------------------
# Contract config reader (mirrors dispatch_handler_code_crawl._load_repos_config)
# ---------------------------------------------------------------------------


def _load_repos_config() -> list[dict]:
    """Load repo configuration from the code crawler contract YAML."""
    package = "omniintelligence.nodes.node_code_crawler_effect"
    contract_ref = importlib.resources.files(package).joinpath("contract.yaml")
    contract_text = contract_ref.read_text(encoding="utf-8")
    contract = yaml.safe_load(contract_text)
    return contract.get("config", {}).get("repos", [])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _estimate_file_count(repo: dict) -> int:
    """Quick count of .py files matching the repo's include patterns."""
    repo_path = Path(repo["path"])
    if not repo_path.exists():
        return 0
    count = 0
    for pattern in repo.get("include", ["src/**/*.py"]):
        count += sum(1 for _ in repo_path.glob(pattern))
    return count


def _valid_repo_names(repos: list[dict]) -> list[str]:
    return [r["name"] for r in repos]


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


def dry_run(repos: list[dict], repo_filter: str | None = None) -> None:
    """Show what would be crawled without side effects."""
    # Import from canonical constants to avoid hardcoded topic lint violation
    from omniintelligence.constants import TOPIC_CODE_CRAWL_REQUESTED_V1

    print("\n=== Code Entity Crawl -- Dry Run ===\n")  # noqa: T201

    total_files = 0
    shown = 0
    for repo in repos:
        name = repo["name"]
        if repo_filter and name != repo_filter:
            continue

        path = repo["path"]
        exists = Path(path).exists()
        file_count = _estimate_file_count(repo) if exists else 0
        status = "OK" if exists else "MISSING"

        print(f"  {name:25s} {status:8s} ~{file_count:5d} files  {path}")  # noqa: T201
        total_files += file_count
        shown += 1

    print()  # noqa: T201
    print(f"  Total: ~{total_files} files across {shown} repos")  # noqa: T201
    print(f"  Topic: {TOPIC_CODE_CRAWL_REQUESTED_V1}")  # noqa: T201
    print("\n  Run with --execute to start crawl.\n")  # noqa: T201


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------


async def execute(repos: list[dict], repo_filter: str | None = None) -> None:
    """Emit crawl command to Kafka."""
    from aiokafka import AIOKafkaProducer

    # Import from canonical constants to avoid hardcoded topic lint violation
    from omniintelligence.constants import TOPIC_CODE_CRAWL_REQUESTED_V1

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    crawl_id = str(uuid4())

    payload = json.dumps(
        {
            "crawl_id": crawl_id,
            "repo": repo_filter,
        }
    ).encode()

    repo_names = (
        [repo_filter] if repo_filter else [r["name"] for r in repos]
    )

    print(f"\n=== Emitting crawl command ===")  # noqa: T201
    print(f"  Crawl ID:   {crawl_id}")  # noqa: T201
    print(f"  Repos:      {', '.join(repo_names)}")  # noqa: T201
    print(f"  Topic:      {TOPIC_CODE_CRAWL_REQUESTED_V1}")  # noqa: T201
    print(f"  Bootstrap:  {bootstrap_servers}")  # noqa: T201

    producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
    await producer.start()
    try:
        await producer.send_and_wait(
            TOPIC_CODE_CRAWL_REQUESTED_V1,
            key=crawl_id.encode(),
            value=payload,
        )
        print("\n  Command emitted successfully.\n")  # noqa: T201
    finally:
        await producer.stop()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns:
        0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        description="Batch crawl CLI for code entity extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be crawled without side effects",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Emit crawl command to Kafka",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Filter to a single repo (e.g. omniintelligence)",
    )

    args = parser.parse_args(argv)

    if not args.dry_run and not args.execute:
        parser.error("Must specify --dry-run or --execute")

    repos = _load_repos_config()

    if args.repo:
        valid = _valid_repo_names(repos)
        if args.repo not in valid:
            print(  # noqa: T201
                f"Unknown repo: {args.repo}. Valid: {', '.join(valid)}",
                file=sys.stderr,
            )
            return 1

    if args.dry_run:
        dry_run(repos, repo_filter=args.repo)
    elif args.execute:
        asyncio.run(execute(repos, repo_filter=args.repo))

    return 0


if __name__ == "__main__":
    sys.exit(main())
