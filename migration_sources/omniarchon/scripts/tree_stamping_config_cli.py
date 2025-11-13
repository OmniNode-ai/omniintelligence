#!/usr/bin/env python3
"""
Tree Stamping Configuration Management CLI

Command-line interface for managing multi-repository tree stamping configuration.

Features:
- Validate configuration files
- List configured repositories
- Show repository details
- Discover new repositories
- Test configuration
- Export/import configurations

Usage:
    # Validate configuration
    python scripts/tree_stamping_config_cli.py validate

    # List repositories
    python scripts/tree_stamping_config_cli.py list

    # Show repository details
    python scripts/tree_stamping_config_cli.py show omniarchon

    # Discover repositories
    python scripts/tree_stamping_config_cli.py discover

    # Test configuration
    python scripts/tree_stamping_config_cli.py test omniarchon

    # Export configuration
    python scripts/tree_stamping_config_cli.py export --output exported_config.yaml

Created: 2025-10-27
Purpose: CLI for tree stamping configuration management
ONEX Compliance: Effect node (CLI interface for external user interaction)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.lib.config_manager import TreeStampingConfigManager


# Color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_header(text: str) -> None:
    """Print formatted header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"{Colors.OKBLUE}ℹ {text}{Colors.ENDC}")


def load_config(config_path: str) -> Optional[TreeStampingConfigManager]:
    """
    Load and validate configuration.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration manager or None if failed
    """
    try:
        config_manager = TreeStampingConfigManager.from_file(config_path)
        return config_manager
    except FileNotFoundError as e:
        print_error(f"Configuration file not found: {e}")
        return None
    except ValueError as e:
        print_error(f"Invalid configuration: {e}")
        return None
    except Exception as e:
        print_error(f"Failed to load configuration: {e}")
        return None


def cmd_validate(args: argparse.Namespace) -> int:
    """
    Validate configuration file.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print_header("Configuration Validation")

    config_manager = load_config(args.config)
    if config_manager is None:
        return 1

    print_info(f"Configuration loaded successfully from: {args.config}")
    print_info(f"Schema version: {config_manager.config.schema_version}")
    print_info(f"Config type: {config_manager.config.config_type}")
    print()

    # Run validation
    print_info("Running validation checks...")
    results = config_manager.validate()

    # Print checks
    if results["checks"]:
        print(f"\n{Colors.OKBLUE}Validation Checks:{Colors.ENDC}")
        for check in results["checks"]:
            print(f"  {check}")

    # Print warnings
    if results["warnings"]:
        print(f"\n{Colors.WARNING}Warnings:{Colors.ENDC}")
        for warning in results["warnings"]:
            print_warning(f"  {warning}")

    # Print errors
    if results["errors"]:
        print(f"\n{Colors.FAIL}Errors:{Colors.ENDC}")
        for error in results["errors"]:
            print_error(f"  {error}")

    # Print summary
    summary = results["summary"]
    print(f"\n{Colors.BOLD}Summary:{Colors.ENDC}")
    print(f"  Total repositories: {summary['total_repositories']}")
    print(f"  Enabled repositories: {summary['enabled_repositories']}")
    print(f"  Validation checks: {summary['check_count']}")
    print(f"  Warnings: {summary['warning_count']}")
    print(f"  Errors: {summary['error_count']}")
    print()

    if results["valid"]:
        print_success("Configuration is valid!")
        return 0
    else:
        print_error("Configuration validation failed")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """
    List configured repositories.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print_header("Configured Repositories")

    config_manager = load_config(args.config)
    if config_manager is None:
        return 1

    repositories = config_manager.config.repositories

    if not repositories:
        print_warning("No repositories configured")
        return 0

    # Calculate column widths
    name_width = max(len(repo.name) for repo in repositories) + 2
    status_width = 10
    path_width = 60

    # Print header
    print(
        f"{Colors.BOLD}{'Name':<{name_width}} {'Status':<{status_width}} {'Path':<{path_width}}{Colors.ENDC}"
    )
    print(f"{'-' * (name_width + status_width + path_width + 4)}")

    # Print repositories
    for repo in repositories:
        status = (
            f"{Colors.OKGREEN}enabled{Colors.ENDC}"
            if repo.enabled
            else f"{Colors.WARNING}disabled{Colors.ENDC}"
        )
        path_display = (
            repo.path
            if len(repo.path) <= path_width
            else f"...{repo.path[-(path_width-3):]}"
        )
        print(f"{repo.name:<{name_width}} {status:<{status_width+9}} {path_display}")

    print()
    print_info(f"Total: {len(repositories)} repositories")
    print_info(
        f"Enabled: {len(config_manager.get_enabled_repositories())} repositories"
    )

    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """
    Show repository details.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print_header(f"Repository Details: {args.repository}")

    config_manager = load_config(args.config)
    if config_manager is None:
        return 1

    repo = config_manager.get_repository_config(args.repository)
    if repo is None:
        print_error(f"Repository not found: {args.repository}")
        return 1

    # Basic info
    print(f"{Colors.BOLD}Basic Information:{Colors.ENDC}")
    print(f"  Name: {repo.name}")
    print(f"  Description: {repo.description or 'N/A'}")
    print(f"  Enabled: {'Yes' if repo.enabled else 'No'}")
    print(f"  Path: {repo.path}")
    print(f"  Path Type: {repo.path_type}")
    print()

    # Filters
    print(f"{Colors.BOLD}File Filters:{Colors.ENDC}")
    print(f"  Include patterns: {', '.join(repo.filters.include)}")
    print(f"  Exclude patterns: {', '.join(repo.filters.exclude)}")
    print(f"  Max file size: {repo.filters.max_file_size:,} bytes")
    print(f"  Min file size: {repo.filters.min_file_size:,} bytes")
    print()

    # Processing
    if repo.processing:
        print(f"{Colors.BOLD}Processing Configuration (Override):{Colors.ENDC}")
        print(f"  Batch size: {repo.processing.batch_size}")
        print(f"  Max workers: {repo.processing.max_workers}")
        print(f"  Timeout: {repo.processing.timeout_seconds}s")
        print()

    # Intelligence
    if repo.intelligence:
        print(f"{Colors.BOLD}Intelligence Configuration (Override):{Colors.ENDC}")
        print(
            f"  Quality scoring: {'Yes' if repo.intelligence.quality_scoring else 'No'}"
        )
        print(
            f"  ONEX classification: {'Yes' if repo.intelligence.onex_classification else 'No'}"
        )
        print(
            f"  Semantic analysis: {'Yes' if repo.intelligence.semantic_analysis else 'No'}"
        )
        print()

    # Git hooks
    print(f"{Colors.BOLD}Git Hooks:{Colors.ENDC}")
    print(f"  Enabled: {'Yes' if repo.git_hooks.enabled else 'No'}")
    print(f"  Pre-commit: {'Yes' if repo.git_hooks.pre_commit else 'No'}")
    print(f"  Pre-push: {'Yes' if repo.git_hooks.pre_push else 'No'}")
    print(f"  Incremental: {'Yes' if repo.git_hooks.incremental else 'No'}")
    print()

    # Metadata
    if repo.metadata:
        print(f"{Colors.BOLD}Metadata:{Colors.ENDC}")
        for key, value in repo.metadata.items():
            print(f"  {key}: {value}")
        print()

    # Effective configuration
    if args.effective:
        print(
            f"{Colors.BOLD}Effective Configuration (Global + Overrides):{Colors.ENDC}"
        )
        effective = config_manager.get_effective_config(args.repository)
        print(json.dumps(effective, indent=2))
        print()

    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    """
    Discover repositories.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print_header("Repository Discovery")

    config_manager = load_config(args.config)
    if config_manager is None:
        return 1

    if (
        not config_manager.config.discovery
        or not config_manager.config.discovery.enabled
    ):
        print_error("Repository discovery is not enabled in configuration")
        print_info(
            "Set discovery.enabled = true in your configuration to use this feature"
        )
        return 1

    print_info("Scanning for repositories...")
    print_info(f"Scan paths: {', '.join(config_manager.config.discovery.scan_paths)}")
    print()

    discovered = config_manager.discover_repositories()

    if not discovered:
        print_warning("No repositories discovered")
        return 0

    print_success(f"Discovered {len(discovered)} repositories:\n")

    for repo in discovered:
        print(f"  {Colors.OKGREEN}●{Colors.ENDC} {repo['name']}")
        print(f"    Path: {repo['path']}")
        print(f"    Discovered from: {repo['discovered_from']}")
        print()

    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """
    Test repository configuration.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print_header(f"Testing Repository: {args.repository}")

    config_manager = load_config(args.config)
    if config_manager is None:
        return 1

    repo = config_manager.get_repository_config(args.repository)
    if repo is None:
        print_error(f"Repository not found: {args.repository}")
        return 1

    # Test 1: Path exists
    print_info("Test 1: Path exists...")
    path = Path(repo.path)
    if path.exists():
        print_success(f"  Path exists: {repo.path}")
    else:
        print_error(f"  Path does not exist: {repo.path}")
        return 1

    # Test 2: Is directory
    print_info("Test 2: Is directory...")
    if path.is_dir():
        print_success(f"  Path is a directory")
    else:
        print_error(f"  Path is not a directory")
        return 1

    # Test 3: Is git repository
    print_info("Test 3: Is git repository...")
    git_dir = path / ".git"
    if git_dir.exists():
        print_success(f"  Git repository detected")
    else:
        print_warning(f"  Not a git repository")

    # Test 4: File count estimation
    print_info("Test 4: File count estimation...")
    try:
        all_files = list(path.rglob("*"))
        file_count = len([f for f in all_files if f.is_file()])
        print_success(f"  Total files: {file_count:,}")
    except Exception as e:
        print_error(f"  Failed to count files: {e}")

    # Test 5: Filter matching
    print_info("Test 5: Filter matching...")
    include_patterns = repo.filters.include
    print_info(f"  Include patterns: {len(include_patterns)}")
    for pattern in include_patterns[:3]:  # Show first 3
        print(f"    - {pattern}")
    if len(include_patterns) > 3:
        print(f"    ... and {len(include_patterns) - 3} more")

    # Test 6: Effective configuration
    print_info("Test 6: Effective configuration...")
    try:
        effective = config_manager.get_effective_config(args.repository)
        print_success(f"  Configuration merged successfully")
        print_info(f"  Batch size: {effective['processing']['batch_size']}")
        print_info(f"  Max workers: {effective['processing']['max_workers']}")
    except Exception as e:
        print_error(f"  Failed to merge configuration: {e}")
        return 1

    print()
    print_success("All tests passed!")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """
    Export configuration.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print_header("Export Configuration")

    config_manager = load_config(args.config)
    if config_manager is None:
        return 1

    try:
        config_manager.to_yaml(args.output)
        print_success(f"Configuration exported to: {args.output}")
        return 0
    except Exception as e:
        print_error(f"Failed to export configuration: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Tree Stamping Configuration Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate configuration
  %(prog)s validate

  # List repositories
  %(prog)s list

  # Show repository details
  %(prog)s show omniarchon

  # Show effective configuration (with overrides)
  %(prog)s show omniarchon --effective

  # Discover repositories
  %(prog)s discover

  # Test repository configuration
  %(prog)s test omniarchon

  # Export configuration
  %(prog)s export --output exported_config.yaml

For more information, see docs/guides/MULTI_REPO_SETUP.md
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        default="config/tree_stamping_repos.yaml",
        help="Path to configuration file (default: config/tree_stamping_repos.yaml)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate configuration file"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List configured repositories")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show repository details")
    show_parser.add_argument("repository", help="Repository name")
    show_parser.add_argument(
        "--effective",
        action="store_true",
        help="Show effective configuration (global + overrides)",
    )

    # Discover command
    discover_parser = subparsers.add_parser("discover", help="Discover repositories")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test repository configuration")
    test_parser.add_argument("repository", help="Repository name")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export configuration")
    export_parser.add_argument("--output", "-o", required=True, help="Output file path")

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == "validate":
        return cmd_validate(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "show":
        return cmd_show(args)
    elif args.command == "discover":
        return cmd_discover(args)
    elif args.command == "test":
        return cmd_test(args)
    elif args.command == "export":
        return cmd_export(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
