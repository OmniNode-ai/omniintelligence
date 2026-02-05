#!/usr/bin/env python3
"""Generate comprehensive node status report for omniintelligence.

This script scans all nodes in src/omniintelligence/nodes/ and generates
a markdown report with:
- Summary counts by category
- Detailed table for each node
- Purity violations (nodes with >100 lines that aren't stubs)
- Recommendations

Stub Detection:
    Nodes are identified as "stubs" using AST-based parsing (not regex) to
    avoid false positives from commented code, docstrings, or strings.
    A node is a stub only if it has: is_stub: ClassVar[bool] = True

    See check_is_stub() for detailed detection rules.

Usage:
    python scripts/generate_node_report.py
    python scripts/generate_node_report.py --output docs/NODE_STATUS_REPORT.md

Reference: OMN-1140
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal


@dataclass
class NodeInfo:
    """Information about a single node."""

    name: str
    node_type: Literal["compute", "effect", "orchestrator", "reducer", "unknown"]
    line_count: int
    is_stub: bool
    has_handlers: bool
    has_contract: bool
    has_models: bool
    node_file_path: str | None
    status: str  # "Pure Shell", "Stub", "Needs Handler Extraction", "Missing Node File"


def get_node_type(
    name: str,
) -> Literal["compute", "effect", "orchestrator", "reducer", "unknown"]:
    """Determine node type from directory name."""
    if name.endswith("_compute"):
        return "compute"
    if name.endswith("_effect"):
        return "effect"
    if name.endswith("_orchestrator"):
        return "orchestrator"
    if name.endswith("_reducer"):
        return "reducer"
    # Handle special cases like intelligence_adapter
    if "adapter" in name:
        return "effect"
    return "unknown"


def check_is_stub(file_path: Path) -> bool:
    """Check if node file contains is_stub: ClassVar[bool] = True.

    Uses AST parsing for accurate detection, avoiding false positives that
    regex would produce (e.g., matching commented code, docstrings, or strings).

    Stub Detection Rules:
        A node is considered a "stub" if and only if:
        1. It contains a class definition
        2. That class has an annotated assignment: is_stub: ClassVar[bool] = True
        3. The assignment is a direct ClassVar[bool] annotation with value True

    NOT considered stubs (false positive prevention):
        - Commented out is_stub declarations
        - is_stub mentioned in docstrings or strings
        - is_stub = True without ClassVar annotation (non-standard pattern)
        - is_stub: ClassVar[bool] = False (explicitly not a stub)
        - Abstract methods that raise NotImplementedError (legitimate pattern)
        - Empty methods with pass (may be intentional)
        - Type stubs using ellipsis ... (separate from is_stub ClassVar)

    Args:
        file_path: Path to the Python file to check.

    Returns:
        True if the file contains a class with is_stub: ClassVar[bool] = True,
        False otherwise (including for nonexistent files or syntax errors).

    Reference:
        OMN-1140 PR #11 review identified the need for AST-based detection
        instead of regex to prevent false positives.
    """
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign):
                        if (
                            isinstance(item.target, ast.Name)
                            and item.target.id == "is_stub"
                        ):
                            if (
                                isinstance(item.value, ast.Constant)
                                and item.value.value is True
                            ):
                                return True
        return False
    except Exception:
        return False


def count_lines(file_path: Path) -> int:
    """Count non-empty lines in a file."""
    try:
        return sum(1 for line in file_path.read_text().splitlines() if line.strip())
    except Exception:
        return 0


def find_node_file(node_dir: Path) -> Path | None:
    """Find the main node file in a node directory."""
    # Look for node.py first
    node_py = node_dir / "node.py"
    if node_py.exists():
        return node_py
    # Look for node_*.py pattern
    for file in node_dir.glob("node_*.py"):
        if not file.name.startswith("node_test"):
            return file
    return None


def scan_node(node_dir: Path) -> NodeInfo:
    """Scan a single node directory and collect information."""
    name = node_dir.name
    node_type = get_node_type(name)

    # Find the main node file
    node_file = find_node_file(node_dir)

    # Get line count and stub status
    if node_file:
        line_count = count_lines(node_file)
        is_stub = check_is_stub(node_file)
        try:
            node_file_path = str(
                node_file.relative_to(node_dir.parent.parent.parent.parent)
            )
        except ValueError:
            node_file_path = str(node_file)
    else:
        line_count = 0
        is_stub = False
        node_file_path = None

    # Check for handlers directory
    has_handlers = (node_dir / "handlers").exists()

    # Check for contract.yaml
    has_contract = (node_dir / "contract.yaml").exists()

    # Check for models directory or models.py
    has_models = (node_dir / "models").is_dir() or (node_dir / "models.py").exists()

    # Determine status
    if node_file is None:
        status = "Missing Node File"
    elif is_stub:
        status = "Stub"
    elif line_count <= 100:
        status = "Pure Shell"
    else:
        status = "Needs Handler Extraction"

    return NodeInfo(
        name=name,
        node_type=node_type,
        line_count=line_count,
        is_stub=is_stub,
        has_handlers=has_handlers,
        has_contract=has_contract,
        has_models=has_models,
        node_file_path=node_file_path,
        status=status,
    )


def scan_all_nodes(nodes_dir: Path) -> list[NodeInfo]:
    """Scan all node directories."""
    nodes = []
    for node_dir in sorted(nodes_dir.iterdir()):
        if node_dir.is_dir() and not node_dir.name.startswith("_"):
            nodes.append(scan_node(node_dir))
    return nodes


def generate_report(nodes: list[NodeInfo]) -> str:
    """Generate the markdown report."""
    # Calculate summary stats
    pure_shells = sum(1 for n in nodes if n.status == "Pure Shell")
    stubs = sum(1 for n in nodes if n.status == "Stub")
    needs_extraction = sum(1 for n in nodes if n.status == "Needs Handler Extraction")
    missing_file = sum(1 for n in nodes if n.status == "Missing Node File")
    total = len(nodes)

    # Count by type
    type_counts = {}
    for n in nodes:
        type_counts[n.node_type] = type_counts.get(n.node_type, 0) + 1

    # Generate report
    lines = [
        "# Node Status Report",
        f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "## Summary",
        "",
        "### Status Breakdown",
        "| Category | Count | Description |",
        "|----------|-------|-------------|",
        f"| Pure Shells | {pure_shells} | Nodes with <100 lines, fully delegating to base class |",
        f"| Stubs | {stubs} | Nodes with `is_stub: ClassVar[bool] = True` marker |",
        f"| Needs Handler Extraction | {needs_extraction} | Nodes with >100 lines that need refactoring |",
        f"| Missing Node File | {missing_file} | Node directories without node.py |",
        f"| **Total** | **{total}** | |",
        "",
        "### Node Type Distribution",
        "| Type | Count |",
        "|------|-------|",
    ]

    for node_type in ["compute", "effect", "orchestrator", "reducer", "unknown"]:
        count = type_counts.get(node_type, 0)
        if count > 0:
            lines.append(f"| {node_type.title()} | {count} |")

    lines.extend(
        [
            "",
            "## Detailed Node Status",
            "",
            "| Node | Type | Lines | Stub | Handlers | Contract | Models | Status |",
            "|------|------|------:|:----:|:--------:|:--------:|:------:|--------|",
        ]
    )

    for node in nodes:
        stub_marker = "Yes" if node.is_stub else "No"
        handlers_marker = "Yes" if node.has_handlers else "No"
        contract_marker = "Yes" if node.has_contract else "No"
        models_marker = "Yes" if node.has_models else "No"

        # Status with emoji
        if node.status == "Pure Shell":
            status_text = "Pure Shell"
        elif node.status == "Stub":
            status_text = "Stub"
        elif node.status == "Needs Handler Extraction":
            status_text = "**NEEDS EXTRACTION**"
        else:
            status_text = "*Missing*"

        lines.append(
            f"| {node.name} | {node.node_type.title()} | {node.line_count} | "
            f"{stub_marker} | {handlers_marker} | {contract_marker} | {models_marker} | {status_text} |"
        )

    # Purity violations section
    violations = [n for n in nodes if n.status == "Needs Handler Extraction"]
    lines.extend(
        [
            "",
            "## Purity Violations",
            "",
        ]
    )

    if violations:
        lines.append(
            "The following nodes exceed 100 lines and need handler extraction:"
        )
        lines.append("")
        for v in violations:
            lines.append(
                f"- **{v.name}**: {v.line_count:,} lines "
                f"(file: `{v.node_file_path or 'unknown'}`)"
            )
        lines.append("")
        lines.append("### Why This Matters")
        lines.append("")
        lines.append(
            "ONEX nodes should be 'pure shells' that delegate all business logic to "
            "handler modules. This ensures:"
        )
        lines.append("- Testability: Handlers can be unit tested in isolation")
        lines.append("- Reusability: Handlers can be shared across nodes")
        lines.append("- Maintainability: Clear separation of concerns")
        lines.append(
            "- Contract compliance: Node shells focus on I/O, handlers on logic"
        )
    else:
        lines.append(
            "No purity violations detected. All non-stub nodes are under 100 lines."
        )

    # Missing node files section
    missing = [n for n in nodes if n.status == "Missing Node File"]
    if missing:
        lines.extend(
            [
                "",
                "## Missing Node Files",
                "",
                "The following node directories don't have a `node.py` file:",
                "",
            ]
        )
        for m in missing:
            lines.append(
                f"- **{m.name}**: Check `__init__.py` for stub/model-only definition"
            )

    # Recommendations section
    lines.extend(
        [
            "",
            "## Recommendations",
            "",
        ]
    )

    recommendations = []

    if violations:
        recommendations.append(
            "1. **Extract handlers from large nodes**: The nodes listed in Purity Violations "
            "should have their business logic moved to `handlers/` directories. This follows "
            "the ONEX pattern of 'pure shell' nodes."
        )

    stub_count = len([n for n in nodes if n.is_stub])
    if stub_count > total // 2:
        recommendations.append(
            f"2. **Implement stub nodes**: {stub_count}/{total} nodes are stubs. "
            "Prioritize implementing nodes based on operational requirements."
        )

    no_contract = [n for n in nodes if not n.has_contract]
    if no_contract:
        recommendations.append(
            f"3. **Add missing contracts**: {len(no_contract)} nodes lack contract.yaml files. "
            "All nodes should have contracts for validation and documentation."
        )

    no_handlers = [
        n
        for n in nodes
        if not n.has_handlers and n.status == "Needs Handler Extraction"
    ]
    if no_handlers:
        recommendations.append(
            "4. **Create handlers directories**: Nodes needing extraction should have "
            "`handlers/` directories created to hold extracted business logic."
        )

    if not recommendations:
        recommendations.append(
            "All nodes are in good shape! Continue following the pure shell pattern."
        )

    lines.extend(recommendations)

    # Legend section
    lines.extend(
        [
            "",
            "## Legend",
            "",
            "- **Pure Shell**: Node with <100 lines that delegates to base class",
            "- **Stub**: Node marked with `is_stub: ClassVar[bool] = True`",
            "- **Needs Handler Extraction**: Node with >100 lines requiring refactoring",
            "- **Handlers**: Whether `handlers/` directory exists",
            "- **Contract**: Whether `contract.yaml` exists",
            "- **Models**: Whether `models/` directory or `models.py` exists",
            "",
            "---",
            "*Report generated by `scripts/generate_node_report.py` for OMN-1140*",
        ]
    )

    # Add trailing newline for POSIX compliance
    return "\n".join(lines) + "\n"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate node status report for omniintelligence"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="docs/NODE_STATUS_REPORT.md",
        help="Output file path (default: docs/NODE_STATUS_REPORT.md)",
    )
    parser.add_argument(
        "--nodes-dir",
        default="src/omniintelligence/nodes",
        help="Path to nodes directory (default: src/omniintelligence/nodes)",
    )

    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    nodes_dir = project_root / args.nodes_dir
    output_file = project_root / args.output

    # Validate nodes directory exists
    if not nodes_dir.exists():
        print(f"Error: Nodes directory not found: {nodes_dir}")
        return 1

    # Scan nodes
    print(f"Scanning nodes in: {nodes_dir}")
    nodes = scan_all_nodes(nodes_dir)
    print(f"Found {len(nodes)} nodes")

    # Generate report
    report = generate_report(nodes)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write report
    output_file.write_text(report)
    print(f"Report written to: {output_file}")

    # Print summary
    print("\n--- Summary ---")
    pure_shells = sum(1 for n in nodes if n.status == "Pure Shell")
    stubs = sum(1 for n in nodes if n.status == "Stub")
    needs_extraction = sum(1 for n in nodes if n.status == "Needs Handler Extraction")
    print(f"Pure Shells: {pure_shells}")
    print(f"Stubs: {stubs}")
    print(f"Needs Handler Extraction: {needs_extraction}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
