#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Contract Inferencer CLI — infer ONEX contracts from existing node implementations.

AST-only (no LLM calls). Scans Python files for classes inheriting from Node*
base classes and generates contract.yaml drafts.

Ported from Archive/omninode_bridge ContractInferencer. Adapted to work as a
standalone CLI tool without bridge-specific deps.

Usage:
    uv run python scripts/infer_contracts.py --dry-run
    uv run python scripts/infer_contracts.py --execute
    uv run python scripts/infer_contracts.py --repo omniintelligence --execute
    uv run python scripts/infer_contracts.py --node NodePatternStorageEffect --execute

Reference: OMN-5683
"""

from __future__ import annotations

import argparse
import ast
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Inference rules (declarative)
NODE_TYPE_FROM_BASE: dict[str, str] = {
    "NodeEffect": "EFFECT_GENERIC",
    "NodeCompute": "COMPUTE_GENERIC",
    "NodeReducer": "REDUCER_GENERIC",
    "NodeOrchestrator": "ORCHESTRATOR_GENERIC",
}

SKIP_PATTERNS = {"test_", "_test", "__"}

# Known repo locations
REPO_ROOT = Path("/Volumes/PRO-G40/Code/omni_home")
REPO_DIRS: dict[str, Path] = {
    "omniintelligence": REPO_ROOT
    / "omniintelligence"
    / "src"
    / "omniintelligence"
    / "nodes",
    "omniclaude": REPO_ROOT / "omniclaude" / "src" / "omniclaude",
    "omnibase_core": REPO_ROOT / "omnibase_core" / "src" / "omnibase_core",
    "omnibase_infra": REPO_ROOT / "omnibase_infra" / "src" / "omnibase_infra" / "nodes",
}


@dataclass
class NodeAnalysis:
    """Analysis results from parsing a node.py file."""

    node_name: str
    node_type: str
    base_class: str
    mixins: list[str] = field(default_factory=list)
    imports: dict[str, list[str]] = field(default_factory=dict)
    methods: list[str] = field(default_factory=list)
    docstring: str | None = None
    io_operations: list[str] = field(default_factory=list)
    file_path: str = ""
    has_existing_contract: bool = False


def parse_node_file(file_path: Path) -> NodeAnalysis | None:
    """Parse a Python file using AST to extract node class information.

    Returns NodeAnalysis if a Node* class is found, None otherwise.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        logger.debug("Skipping %s: %s", file_path, exc)
        return None

    # Extract imports
    imports: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports[node.module] = [a.name for a in node.names if a.name]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.name] = [alias.name]

    # Find Node* class
    node_class: ast.ClassDef | None = None
    base_class_name = ""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            name = ""
            if isinstance(base, ast.Name):
                name = base.id
            elif isinstance(base, ast.Attribute):
                name = base.attr
            if name.startswith("Node") and name in NODE_TYPE_FROM_BASE:
                node_class = node
                base_class_name = name
                break
        if node_class:
            break

    if node_class is None:
        return None

    # Skip test-like classes
    class_name = node_class.name
    lower_name = class_name.lower()
    if any(lower_name.startswith(p) or lower_name.endswith(p) for p in SKIP_PATTERNS):
        return None

    # Extract mixins
    mixins: list[str] = []
    for base in node_class.bases:
        name = ""
        if isinstance(base, ast.Name):
            name = base.id
        elif isinstance(base, ast.Attribute):
            name = base.attr
        if name.startswith("Mixin"):
            mixins.append(name)

    # Extract methods
    methods: list[str] = []
    for item in node_class.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(item.name)

    # Extract docstring
    docstring = ast.get_docstring(node_class)

    # Infer I/O operations from method names and imports
    io_ops: list[str] = []
    io_keywords = {
        "http": "api",
        "kafka": "messaging",
        "database": "database",
        "postgres": "database",
        "redis": "cache",
        "qdrant": "vector_store",
        "memgraph": "graph_store",
        "file": "filesystem",
    }
    for method in methods:
        for kw, op in io_keywords.items():
            if kw in method.lower() and op not in io_ops:
                io_ops.append(op)
    for mod in imports:
        for kw, op in io_keywords.items():
            if kw in mod.lower() and op not in io_ops:
                io_ops.append(op)

    # Check if contract.yaml already exists
    node_dir = file_path.parent
    has_contract = (node_dir / "contract.yaml").exists()

    return NodeAnalysis(
        node_name=class_name,
        node_type=NODE_TYPE_FROM_BASE.get(base_class_name, "COMPUTE_GENERIC"),
        base_class=base_class_name,
        mixins=mixins,
        imports=imports,
        methods=methods,
        docstring=docstring,
        io_operations=io_ops,
        file_path=str(file_path),
        has_existing_contract=has_contract,
    )


def generate_contract_yaml(analysis: NodeAnalysis) -> str:
    """Generate a contract YAML draft from node analysis."""
    # Derive node directory name from class name
    # e.g., NodePatternStorageEffect -> node_pattern_storage_effect
    name_parts: list[str] = []
    for i, ch in enumerate(analysis.node_name):
        if ch.isupper() and i > 0:
            name_parts.append("_")
        name_parts.append(ch.lower())
    snake_name = "".join(name_parts)

    contract: dict[str, Any] = {
        "name": snake_name,
        "description": analysis.docstring.split("\n")[0]
        if analysis.docstring
        else f"# TODO: add description for {analysis.node_name}",
        "contract_version": {"major": 1, "minor": 0, "patch": 0},
        "node_version": {"major": 1, "minor": 0, "patch": 0},
        "node_type": analysis.node_type,
    }

    # Input/output models — only when we have strong evidence
    has_handle = any(
        "handle" in m.lower() or "execute" in m.lower() for m in analysis.methods
    )
    if has_handle:
        contract["input_model"] = {
            "name": "# TODO: verify input model",
            "module": "# TODO: verify module path",
        }
        contract["output_model"] = {
            "name": "# TODO: verify output model",
            "module": "# TODO: verify module path",
        }

    # Handler routing — only when conventions are clear
    if has_handle:
        contract["handler_routing"] = {
            "routing_strategy": "operation_match",
            "handlers": [
                {
                    "operation": "# TODO: verify routing",
                    "handler": {
                        "function": "# TODO: verify handler function",
                        "module": "# TODO: verify handler module",
                        "type": "async"
                        if any(isinstance(None, type(None)) for _ in []) or True
                        else "sync",
                    },
                }
            ],
        }
    else:
        contract["handler_routing"] = "# TODO: verify routing"

    # Event bus
    contract["event_bus"] = {
        "event_bus_enabled": bool(analysis.io_operations),
        "subscribe_topics": [],
        "publish_topics": [],
    }

    # Dependencies
    contract["dependencies"] = []

    # Metadata
    contract["metadata"] = {
        "author": "OmniNode Team",
        "tags": ["ONEX", analysis.node_type.split("_")[0].lower()],
    }

    return yaml.dump(
        contract, default_flow_style=False, sort_keys=False, allow_unicode=True
    )


def scan_repo(
    repo_name: str, nodes_dir: Path, node_filter: str | None = None
) -> list[NodeAnalysis]:
    """Scan a repo's nodes directory for Node* classes."""
    results: list[NodeAnalysis] = []

    if not nodes_dir.exists():
        logger.warning("Nodes directory not found: %s", nodes_dir)
        return results

    for py_file in sorted(nodes_dir.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        if "node_tests" in str(py_file):
            continue

        analysis = parse_node_file(py_file)
        if analysis is None:
            continue
        if node_filter and analysis.node_name != node_filter:
            continue

        results.append(analysis)

    return results


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Infer ONEX contracts from node implementations (AST-only, no LLM)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show nodes missing contracts without generating (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Generate contract.yaml drafts",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Filter to a single repo (e.g., omniintelligence)",
    )
    parser.add_argument(
        "--node",
        type=str,
        default=None,
        help="Filter to a single node class name",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if args.execute:
        args.dry_run = False

    # Scan repos
    repos_to_scan = REPO_DIRS
    if args.repo:
        if args.repo not in REPO_DIRS:
            logger.error(
                "Unknown repo: %s (known: %s)", args.repo, list(REPO_DIRS.keys())
            )
            sys.exit(1)
        repos_to_scan = {args.repo: REPO_DIRS[args.repo]}

    all_analyses: list[NodeAnalysis] = []
    for repo_name, nodes_dir in repos_to_scan.items():
        analyses = scan_repo(repo_name, nodes_dir, node_filter=args.node)
        all_analyses.extend(analyses)

    if not all_analyses:
        print("No Node* classes found matching filters.")
        sys.exit(0)

    # Report
    missing = [a for a in all_analyses if not a.has_existing_contract]
    existing = [a for a in all_analyses if a.has_existing_contract]

    print(f"\n{'=' * 60}")
    print("Contract Inference Report")
    print(f"{'=' * 60}")
    print(f"  Total Node* classes found: {len(all_analyses)}")
    print(f"  With existing contract:    {len(existing)}")
    print(f"  Missing contract:          {len(missing)}")
    print()

    if existing:
        print("Nodes WITH existing contract (skipped):")
        for a in existing:
            print(f"  - {a.node_name} ({a.base_class}) @ {a.file_path}")
        print()

    if missing:
        print("Nodes MISSING contract:")
        for a in missing:
            print(f"  - {a.node_name} ({a.base_class})")
            print(f"    File: {a.file_path}")
            print(f"    Type: {a.node_type}")
            if a.mixins:
                print(f"    Mixins: {', '.join(a.mixins)}")
            if a.io_operations:
                print(f"    I/O: {', '.join(a.io_operations)}")
            print()

    if args.dry_run:
        if missing:
            print("[DRY RUN] Would generate contracts for the above nodes.")
            print("Run with --execute to generate.")
    else:
        generated = 0
        for analysis in missing:
            node_dir = Path(analysis.file_path).parent
            contract_path = node_dir / "contract.yaml"

            if contract_path.exists():
                logger.info("Skipping %s — contract already exists", analysis.node_name)
                continue

            contract_yaml = generate_contract_yaml(analysis)
            contract_path.write_text(contract_yaml)
            print(f"Generated: {contract_path}")
            generated += 1

        print(f"\nGenerated {generated} contract draft(s).")
        if generated > 0:
            print(
                "Review and refine the generated contracts — they are drafts with TODO markers."
            )


if __name__ == "__main__":
    main()
