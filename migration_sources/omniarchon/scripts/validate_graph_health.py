#!/usr/bin/env python3
"""
Permanent Graph Health Validation Script

Validates Memgraph knowledge graph completeness:
- Relationship creation
- File tree structure
- Node/relationship ratios
- Orphaned nodes

Usage:
    python3 scripts/validate_graph_health.py
    python3 scripts/validate_graph_health.py --project omnidash
    python3 scripts/validate_graph_health.py --fail-on-warn  # Exit 1 on warnings
"""

import argparse
import sys
from typing import Dict, List, Tuple

from neo4j import GraphDatabase

# Thresholds for validation
THRESHOLDS = {
    "min_relationships_per_file": 0.5,  # At least 0.5 relationships per file
    "min_tree_coverage": 0.95,  # 95% of files should be in tree
    "max_orphaned_files": 10,  # Max 10 orphaned files acceptable
    "min_project_nodes": 1,  # Must have at least 1 PROJECT node
}

MEMGRAPH_URI = "bolt://localhost:7687"


class GraphHealthValidator:
    """Validates Memgraph graph health and completeness."""

    def __init__(self, uri: str = MEMGRAPH_URI):
        self.driver = GraphDatabase.driver(uri)
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.passes: List[str] = []

    def close(self):
        self.driver.close()

    def run_query(self, query: str) -> List[Dict]:
        """Execute Cypher query and return results."""
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record) for record in result]

    def validate_relationship_creation(self, project: str = None) -> Tuple[bool, Dict]:
        """Validate that relationships are being created."""
        project_filter = f"WHERE f.project_name = '{project}'" if project else ""

        query = f"""
        MATCH (f:File) {project_filter}
        OPTIONAL MATCH (f)-[r]->()
        RETURN
            count(DISTINCT f) as file_count,
            count(r) as relationship_count,
            count(r) * 1.0 / count(DISTINCT f) as relationships_per_file
        """

        result = self.run_query(query)[0]
        file_count = result["file_count"]
        rel_count = result["relationship_count"]
        rel_per_file = result["relationships_per_file"] or 0

        min_threshold = THRESHOLDS["min_relationships_per_file"]

        if rel_count == 0 and file_count > 0:
            self.issues.append(
                f"❌ CRITICAL: 0 relationships found for {file_count} files! "
                f"Relationship creation is broken."
            )
            return False, result
        elif rel_per_file < min_threshold:
            self.warnings.append(
                f"⚠️  Low relationship density: {rel_per_file:.2f} per file "
                f"(threshold: {min_threshold})"
            )
            return True, result
        else:
            self.passes.append(
                f"✅ Relationship creation healthy: {rel_count} relationships "
                f"for {file_count} files ({rel_per_file:.2f} per file)"
            )
            return True, result

    def validate_file_tree_structure(self, project: str = None) -> Tuple[bool, Dict]:
        """Validate file tree structure completeness."""
        project_filter = f"WHERE f.project_name = '{project}'" if project else ""

        # Count PROJECT and DIRECTORY nodes
        tree_query = f"""
        MATCH (p:PROJECT)
        OPTIONAL MATCH (p)-[:CONTAINS]->(d:DIRECTORY)
        OPTIONAL MATCH (d)-[:CONTAINS]->(f:File)
        WITH count(DISTINCT p) as project_count,
             count(DISTINCT d) as dir_count,
             count(DISTINCT f) as tree_files
        MATCH (all_files:File) {project_filter}
        RETURN
            project_count,
            dir_count,
            tree_files,
            count(all_files) as total_files,
            count(all_files) - tree_files as orphaned_files
        """

        result = self.run_query(tree_query)[0]
        project_count = result["project_count"]
        dir_count = result["dir_count"]
        tree_files = result["tree_files"]
        total_files = result["total_files"]
        orphaned = result["orphaned_files"]

        min_projects = THRESHOLDS["min_project_nodes"]
        max_orphaned = THRESHOLDS["max_orphaned_files"]
        min_coverage = THRESHOLDS["min_tree_coverage"]

        coverage = tree_files / total_files if total_files > 0 else 0

        # Critical issues
        if project_count < min_projects:
            self.issues.append(
                f"❌ CRITICAL: No PROJECT nodes found! Tree structure missing."
            )
            return False, result

        if orphaned > max_orphaned:
            self.issues.append(
                f"❌ CRITICAL: {orphaned} orphaned files (max: {max_orphaned})"
            )
            return False, result

        # Warnings
        if coverage < min_coverage:
            self.warnings.append(
                f"⚠️  Low tree coverage: {coverage:.1%} (threshold: {min_coverage:.1%})"
            )

        # Success
        if orphaned == 0:
            self.passes.append(
                f"✅ File tree complete: {project_count} PROJECT, {dir_count} DIRECTORY, "
                f"{tree_files}/{total_files} files in tree"
            )
        else:
            self.passes.append(
                f"✅ File tree mostly complete: {orphaned} orphaned files (acceptable)"
            )

        return True, result

    def validate_node_relationship_balance(self) -> Tuple[bool, Dict]:
        """Validate node/relationship balance (detect disconnected graphs)."""
        query = """
        MATCH (n)
        OPTIONAL MATCH ()-[r]->()
        RETURN
            count(DISTINCT n) as node_count,
            count(r) as relationship_count,
            count(r) * 1.0 / count(DISTINCT n) as rel_per_node
        """

        result = self.run_query(query)[0]
        node_count = result["node_count"]
        rel_count = result["relationship_count"]
        rel_per_node = result["rel_per_node"] or 0

        # A healthy graph should have at least 1 relationship per 2 nodes
        if rel_count == 0 and node_count > 0:
            self.issues.append(
                f"❌ CRITICAL: {node_count} nodes but 0 relationships! Graph is disconnected."
            )
            return False, result
        elif rel_per_node < 0.3:
            self.warnings.append(
                f"⚠️  Sparse graph: {rel_per_node:.2f} relationships per node "
                f"({rel_count} rels for {node_count} nodes)"
            )
        else:
            self.passes.append(
                f"✅ Graph connectivity healthy: {rel_per_node:.2f} relationships per node"
            )

        return True, result

    def validate_relationship_types(self) -> Tuple[bool, Dict]:
        """Check that expected relationship types exist."""
        query = """
        MATCH ()-[r]->()
        RETURN type(r) as rel_type, count(r) as count
        ORDER BY count DESC
        """

        results = self.run_query(query)

        if not results:
            self.issues.append("❌ CRITICAL: No relationship types found!")
            return False, {}

        # Expected relationship types for code graphs
        expected_types = {"IMPORTS", "DEFINES", "CALLS", "CONTAINS"}
        found_types = {r["rel_type"] for r in results}

        missing = expected_types - found_types
        if missing:
            self.warnings.append(f"⚠️  Missing relationship types: {', '.join(missing)}")

        summary = ", ".join([f"{r['rel_type']}: {r['count']}" for r in results[:5]])
        self.passes.append(f"✅ Relationship types: {summary}")

        return True, {"types": results}

    def run_all_validations(self, project: str = None) -> bool:
        """Run all validation checks."""
        print("=" * 70)
        print("🔍 GRAPH HEALTH VALIDATION")
        print("=" * 70)
        if project:
            print(f"Project: {project}")
        print()

        all_passed = True

        # Run validations
        all_passed &= self.validate_relationship_creation(project)[0]
        all_passed &= self.validate_file_tree_structure(project)[0]
        all_passed &= self.validate_node_relationship_balance()[0]
        all_passed &= self.validate_relationship_types()[0]

        # Print results
        print()
        print("=" * 70)
        print("📊 RESULTS")
        print("=" * 70)

        if self.passes:
            print("\n✅ PASSING CHECKS:")
            for check in self.passes:
                print(f"  {check}")

        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")

        if self.issues:
            print("\n❌ CRITICAL ISSUES:")
            for issue in self.issues:
                print(f"  {issue}")

        print()
        print("=" * 70)
        if not self.issues and not self.warnings:
            print("🎉 STATUS: ALL CHECKS PASSED")
            print("=" * 70)
            return True
        elif self.issues:
            print("🚨 STATUS: CRITICAL ISSUES FOUND")
            print("=" * 70)
            return False
        else:
            print("⚠️  STATUS: WARNINGS (passing with issues)")
            print("=" * 70)
            return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="Validate Memgraph graph health and completeness"
    )
    parser.add_argument(
        "--project", help="Filter validation to specific project", default=None
    )
    parser.add_argument(
        "--fail-on-warn", help="Exit with code 1 if warnings found", action="store_true"
    )
    parser.add_argument(
        "--uri",
        help="Memgraph URI (default: bolt://localhost:7687)",
        default=MEMGRAPH_URI,
    )

    args = parser.parse_args()

    validator = GraphHealthValidator(uri=args.uri)

    try:
        passed = validator.run_all_validations(project=args.project)

        # Determine exit code
        if not passed:
            sys.exit(2)  # Critical issues
        elif args.fail_on_warn and validator.warnings:
            sys.exit(1)  # Warnings (when --fail-on-warn)
        else:
            sys.exit(0)  # All good

    finally:
        validator.close()


if __name__ == "__main__":
    main()
