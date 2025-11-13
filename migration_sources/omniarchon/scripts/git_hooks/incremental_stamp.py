#!/usr/bin/env python3
"""
Incremental Tree Stamping Git Hook

Pre-commit hook that triggers incremental stamping for changed files.
Publishes events to Kafka for async processing without blocking commits.

Usage:
    python incremental_stamp.py [--config CONFIG_PATH]

Performance Target: <2s (non-blocking, async event publishing)
Integration: Pre-commit framework + Kafka event bus

Created: 2025-10-27
ONEX Pattern: Effect (Git operations + Kafka publishing)
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Optional, Set
from uuid import uuid4

# Add project root to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ==============================================================================
# Configuration
# ==============================================================================

DEFAULT_CONFIG = {
    "enabled": True,
    "async_mode": True,  # Non-blocking: publish event and return immediately
    "kafka_enabled": True,  # Use Kafka for event publishing
    "min_files_for_stamping": 1,  # Minimum changed files to trigger stamping
    "max_files_per_event": 100,  # Max files in single event (batch size)
    "timeout_seconds": 2.0,  # Maximum execution time
    "project_name": None,  # Auto-detect from git remote or directory name
    "kafka_bootstrap_servers": os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:9092"
    ),  # Host machine Kafka port
    "kafka_topic": "dev.archon-intelligence.tree.incremental-stamp-requested.v1",
    "exclude_patterns": [
        "*.pyc",
        "*.pyo",
        "__pycache__/*",
        ".git/*",
        "node_modules/*",
        "dist/*",
        "build/*",
        ".venv/*",
        "venv/*",
        "*.min.js",
        "*.bundle.js",
        "*.map",
    ],
    "supported_extensions": [
        ".py",
        ".pyi",  # Python
        ".js",
        ".jsx",
        ".ts",
        ".tsx",  # JavaScript/TypeScript
        ".java",
        ".kt",  # Java/Kotlin
        ".rs",  # Rust
        ".go",  # Go
        ".rb",  # Ruby
        ".php",  # PHP
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cc",
        ".cxx",  # C/C++
        ".cs",  # C#
        ".swift",  # Swift
        ".scala",  # Scala
        ".clj",  # Clojure
        ".ex",
        ".exs",  # Elixir
        ".erl",
        ".hrl",  # Erlang
        ".r",
        ".R",  # R
        ".sql",  # SQL
        ".sh",
        ".bash",
        ".zsh",
        ".fish",  # Shell
        ".yaml",
        ".yml",  # YAML
        ".json",  # JSON
        ".toml",  # TOML
        ".md",
        ".markdown",  # Markdown
        ".rst",  # reStructuredText
        ".proto",  # Protobuf
        ".graphql",
        ".gql",  # GraphQL
        ".vue",
        ".svelte",  # Vue/Svelte
    ],
}


def load_config(config_path: Optional[Path] = None) -> dict:
    """
    Load configuration from YAML file or use defaults.

    Args:
        config_path: Path to config.yaml (default: scripts/git_hooks/config.yaml)

    Returns:
        Configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()

    if config_path is None:
        config_path = SCRIPT_DIR / "config.yaml"

    if config_path.exists():
        try:
            import yaml

            with open(config_path, "r") as f:
                user_config = yaml.safe_load(f) or {}

            # Merge user config into defaults
            config.update(user_config)

            logger.debug(f"Loaded config from {config_path}")
        except ImportError:
            logger.warning("PyYAML not installed - using default config")
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")

    return config


# ==============================================================================
# Git Operations
# ==============================================================================


def get_staged_files() -> List[str]:
    """
    Get list of staged files from git.

    Returns:
        List of relative file paths that are staged for commit
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--staged", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5.0,
        )

        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        logger.debug(f"Found {len(files)} staged files")
        return files

    except subprocess.TimeoutExpired:
        logger.error("Git command timed out")
        return []
    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to get staged files: {e}")
        return []


def get_git_root() -> Optional[Path]:
    """
    Get git repository root directory.

    Returns:
        Path to git root or None if not in a git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5.0,
        )

        return Path(result.stdout.strip())

    except Exception as e:
        logger.error(f"Failed to get git root: {e}")
        return None


def get_project_name(git_root: Path) -> str:
    """
    Get project name from git remote or directory name.

    Args:
        git_root: Git repository root path

    Returns:
        Project name slug
    """
    try:
        # Try to get from git remote
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )

        if result.returncode == 0:
            remote_url = result.stdout.strip()
            # Extract repo name from URL (e.g., "omniarchon" from "git@github.com:user/omniarchon.git")
            project_name = remote_url.split("/")[-1].replace(".git", "")
            return project_name

    except Exception:
        pass

    # Fallback: use directory name
    return git_root.name


# ==============================================================================
# File Filtering
# ==============================================================================


def filter_files(files: List[str], config: dict, git_root: Path) -> List[str]:
    """
    Filter files by supported extensions and exclude patterns.

    Args:
        files: List of relative file paths
        config: Configuration dictionary
        git_root: Git repository root path

    Returns:
        Filtered list of file paths that should be stamped
    """
    supported_extensions = set(config["supported_extensions"])
    exclude_patterns = config["exclude_patterns"]

    filtered = []

    for file_path in files:
        # Skip if not a supported extension
        ext = Path(file_path).suffix.lower()
        if ext not in supported_extensions:
            continue

        # Skip if matches exclude pattern
        excluded = False
        for pattern in exclude_patterns:
            if _matches_pattern(file_path, pattern):
                excluded = True
                break

        if not excluded:
            filtered.append(file_path)

    logger.debug(f"Filtered {len(files)} files → {len(filtered)} files for stamping")
    return filtered


def _matches_pattern(file_path: str, pattern: str) -> bool:
    """
    Check if file path matches exclusion pattern.

    Supports simple glob-style patterns:
    - *.pyc: matches any .pyc file
    - __pycache__/*: matches files in __pycache__ directory
    - .git/*: matches files in .git directory

    Args:
        file_path: Relative file path
        pattern: Exclusion pattern

    Returns:
        True if file matches pattern
    """
    import fnmatch

    return fnmatch.fnmatch(file_path, pattern)


# ==============================================================================
# Event Publishing
# ==============================================================================


async def publish_incremental_stamp_event(
    files: List[str],
    git_root: Path,
    project_name: str,
    config: dict,
) -> bool:
    """
    Publish incremental stamp event to Kafka.

    Event payload:
    {
        "event_id": "uuid",
        "event_type": "dev.archon-intelligence.tree.incremental-stamp-requested.v1",
        "correlation_id": "uuid",
        "timestamp": "ISO8601",
        "source": {"service": "git-hook", "instance_id": "pre-commit"},
        "payload": {
            "project_name": "omniarchon",
            "project_path": "/path/to/project",
            "files": ["/abs/path/to/file1.py", ...],
            "trigger": "pre-commit",
            "commit_sha": "abc123" (optional)
        }
    }

    Args:
        files: List of relative file paths to stamp
        git_root: Git repository root path
        project_name: Project name slug
        config: Configuration dictionary

    Returns:
        True if event published successfully
    """
    if not config["kafka_enabled"]:
        logger.info("Kafka disabled - skipping event publishing")
        return True

    try:
        # Import Kafka client (lazy import to avoid startup overhead)
        from aiokafka import AIOKafkaProducer

        # Convert relative paths to absolute paths
        absolute_files = [str(git_root / f) for f in files]

        # Build event envelope
        event = {
            "event_id": str(uuid4()),
            "event_type": config["kafka_topic"].split(".")[-2],  # Extract event type
            "correlation_id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "source": {
                "service": "git-hook",
                "instance_id": "pre-commit",
            },
            "payload": {
                "project_name": project_name,
                "project_path": str(git_root),
                "files": absolute_files,
                "trigger": "pre-commit",
                "file_count": len(absolute_files),
            },
        }

        # Try to get current commit SHA (may fail if pre-commit)
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if result.returncode == 0:
                event["payload"]["commit_sha"] = result.stdout.strip()
        except Exception:
            pass

        # Publish to Kafka
        producer = AIOKafkaProducer(
            bootstrap_servers=config["kafka_bootstrap_servers"],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

        await producer.start()
        try:
            await producer.send_and_wait(
                config["kafka_topic"],
                value=event,
                key=event["correlation_id"].encode("utf-8"),
            )

            logger.info(
                f"✅ Published incremental stamp event: {len(files)} files → {config['kafka_topic']}"
            )
            return True

        finally:
            await producer.stop()

    except ImportError:
        logger.error("aiokafka not installed - cannot publish events")
        return False
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")
        return False


# ==============================================================================
# Main Hook Logic
# ==============================================================================


async def run_hook_async(config: dict) -> int:
    """
    Run incremental stamping hook (async version).

    Args:
        config: Configuration dictionary

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    start_time = time.perf_counter()

    try:
        # Check if hook is enabled
        if not config["enabled"]:
            logger.info("Incremental stamping disabled in config")
            return 0

        # Get git root
        git_root = get_git_root()
        if not git_root:
            logger.error("Not in a git repository")
            return 1

        # Get project name
        project_name = config["project_name"] or get_project_name(git_root)

        # Get staged files
        staged_files = get_staged_files()
        if not staged_files:
            logger.info("No staged files - skipping incremental stamping")
            return 0

        # Filter files
        files_to_stamp = filter_files(staged_files, config, git_root)

        if len(files_to_stamp) < config["min_files_for_stamping"]:
            logger.info(
                f"Only {len(files_to_stamp)} files changed (min: {config['min_files_for_stamping']}) - skipping"
            )
            return 0

        # Batch files if too many
        if len(files_to_stamp) > config["max_files_per_event"]:
            logger.warning(
                f"Large commit: {len(files_to_stamp)} files (max: {config['max_files_per_event']})"
            )
            files_to_stamp = files_to_stamp[: config["max_files_per_event"]]

        logger.info(
            f"Triggering incremental stamping: {len(files_to_stamp)} files in {project_name}"
        )

        # Publish event (async, non-blocking)
        success = await publish_incremental_stamp_event(
            files_to_stamp, git_root, project_name, config
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"✅ Hook completed in {elapsed_ms}ms")

        return 0 if success else 1

    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(f"Hook failed after {elapsed_ms}ms: {e}")
        return 1


def run_hook(config: dict) -> int:
    """
    Run incremental stamping hook (sync wrapper).

    Args:
        config: Configuration dictionary

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    if config["async_mode"]:
        # Async mode: run with asyncio
        return asyncio.run(run_hook_async(config))
    else:
        # Sync mode: not implemented (use async)
        logger.error("Sync mode not implemented - use async_mode: true")
        return 1


# ==============================================================================
# CLI Entry Point
# ==============================================================================


def main() -> int:
    """
    Main entry point for git hook.

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    parser = argparse.ArgumentParser(description="Incremental tree stamping git hook")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config.yaml (default: scripts/git_hooks/config.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (don't publish events)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load config
    config = load_config(args.config)

    # Dry run mode
    if args.dry_run:
        config["kafka_enabled"] = False
        logger.info("DRY RUN MODE - events will not be published")

    # Run hook
    return run_hook(config)


if __name__ == "__main__":
    sys.exit(main())
