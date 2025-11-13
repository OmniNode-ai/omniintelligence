#!/usr/bin/env python3
"""
Verify Environment - Complete Infrastructure Health Check

This script validates all infrastructure components:
1. vLLM embedding service migration (192.168.86.201:8002)
2. Core Archon services (intelligence, bridge, search)
3. Memgraph graph structure and relationships
4. Language field coverage in Memgraph (per-project)
5. project_name property consistency
6. Qdrant vector coverage
7. File tree graph structure (PROJECT/DIRECTORY/CONTAINS relationships)
8. Overall system health
9. Identifies orphaned data requiring cleanup

Usage:
    python3 scripts/verify_environment.py           # Standard check
    python3 scripts/verify_environment.py --verbose # Detailed output
    python3 scripts/verify_environment.py --json    # JSON output
"""

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import requests
from neo4j import GraphDatabase


@dataclass
class VerificationResult:
    """Verification result for a single check."""

    name: str
    status: str  # PASS, WARN, FAIL
    message: str
    details: Optional[Dict] = None


@dataclass
class VerificationReport:
    """Complete verification report."""

    timestamp: str
    results: List[VerificationResult] = field(default_factory=list)
    overall_status: str = "UNKNOWN"  # PASS, WARN, FAIL
    recommendations: List[str] = field(default_factory=list)


def check_vllm_service() -> VerificationResult:
    """Verify vLLM embedding service is accessible."""
    try:
        start = time.time()
        response = requests.get("http://192.168.86.201:8002/health", timeout=5)
        response_time = (time.time() - start) * 1000

        if response.status_code == 200:
            return VerificationResult(
                name="vLLM Embedding Service",
                status="PASS",
                message=f"Service healthy ({response_time:.0f}ms)",
                details={
                    "url": "http://192.168.86.201:8002",
                    "response_time_ms": round(response_time, 2),
                },
            )
        else:
            return VerificationResult(
                name="vLLM Embedding Service",
                status="FAIL",
                message=f"HTTP {response.status_code}",
                details={"url": "http://192.168.86.201:8002"},
            )
    except Exception as e:
        return VerificationResult(
            name="vLLM Embedding Service",
            status="FAIL",
            message=f"Connection failed: {e}",
            details={"url": "http://192.168.86.201:8002"},
        )


def check_memgraph_language_coverage() -> VerificationResult:
    """Verify language field coverage in Memgraph (per-project and overall)."""
    try:
        driver = GraphDatabase.driver("bolt://localhost:7687")

        with driver.session() as session:
            # Check ALL FILE nodes
            result = session.run(
                """
                MATCH (f:File)
                RETURN
                    count(f) as total,
                    count(f.language) as with_language,
                    count(f.project_name) as with_project_name
            """
            )

            stats = result.single()
            total = stats["total"]
            with_language = stats["with_language"]
            with_project_name = stats["with_project_name"]

            overall_pct = (with_language / total * 100) if total > 0 else 0

            # Check per-project breakdown
            result2 = session.run(
                """
                MATCH (f:File)
                RETURN
                    f.project_name as project,
                    count(f) as count,
                    count(f.language) as with_lang
                ORDER BY count DESC
            """
            )

            projects = []
            for record in result2:
                project = record["project"] or "NULL"
                count = record["count"]
                with_lang = record["with_lang"]
                pct = (with_lang / count * 100) if count > 0 else 0
                projects.append(
                    {
                        "project": project,
                        "files": count,
                        "with_language": with_lang,
                        "coverage_pct": round(pct, 2),
                    }
                )

        driver.close()

        # Determine status
        # PASS if all non-NULL projects have >90% coverage
        # WARN if orphaned data exists (NULL project)
        # FAIL if active projects have <90% coverage

        has_orphaned_data = any(
            p["project"] == "NULL" and p["files"] > 0 for p in projects
        )
        active_projects = [p for p in projects if p["project"] != "NULL"]
        all_active_good = all(p["coverage_pct"] >= 90 for p in active_projects)

        if all_active_good and not has_orphaned_data:
            status = "PASS"
            message = f"Language coverage excellent: {overall_pct:.1f}% overall"
        elif all_active_good and has_orphaned_data:
            status = "WARN"
            orphaned_count = next(
                (p["files"] for p in projects if p["project"] == "NULL"), 0
            )
            message = f"Active projects good, but {orphaned_count:,} orphaned files need cleanup"
        else:
            status = "FAIL"
            message = f"Language coverage below target: {overall_pct:.1f}% overall"

        return VerificationResult(
            name="Language Field Coverage",
            status=status,
            message=message,
            details={
                "total_files": total,
                "overall_coverage_pct": round(overall_pct, 2),
                "projects": projects,
            },
        )

    except Exception as e:
        return VerificationResult(
            name="Language Field Coverage", status="FAIL", message=f"Check failed: {e}"
        )


def check_project_name_consistency() -> VerificationResult:
    """Verify project_name field consistency."""
    try:
        driver = GraphDatabase.driver("bolt://localhost:7687")

        with driver.session() as session:
            result = session.run(
                """
                MATCH (f:File)
                RETURN
                    count(f) as total,
                    count(f.project_name) as with_project_name,
                    count(CASE WHEN f.project_name IS NULL THEN 1 END) as null_project
            """
            )

            stats = result.single()
            total = stats["total"]
            with_project_name = stats["with_project_name"]
            null_count = stats["null_project"]
            coverage_pct = (with_project_name / total * 100) if total > 0 else 0

        driver.close()

        if null_count == 0:
            return VerificationResult(
                name="project_name Consistency",
                status="PASS",
                message=f"All {total:,} files have project_name",
                details={"total": total, "coverage_pct": 100.0},
            )
        else:
            return VerificationResult(
                name="project_name Consistency",
                status="WARN",
                message=f"{null_count:,} files missing project_name ({coverage_pct:.1f}% coverage)",
                details={
                    "total": total,
                    "with_project_name": with_project_name,
                    "null_count": null_count,
                    "coverage_pct": round(coverage_pct, 2),
                },
            )

    except Exception as e:
        return VerificationResult(
            name="project_name Consistency", status="FAIL", message=f"Check failed: {e}"
        )


def check_service_health(name: str, url: str) -> VerificationResult:
    """Check if a service is healthy."""
    try:
        start = time.time()
        response = requests.get(f"{url}/health", timeout=5)
        response_time = (time.time() - start) * 1000

        if response.status_code == 200:
            return VerificationResult(
                name=name,
                status="PASS",
                message=f"Healthy ({response_time:.0f}ms)",
                details={"url": url, "response_time_ms": round(response_time, 2)},
            )
        else:
            return VerificationResult(
                name=name,
                status="FAIL",
                message=f"HTTP {response.status_code}",
                details={"url": url},
            )
    except Exception as e:
        return VerificationResult(
            name=name,
            status="FAIL",
            message=f"Connection failed: {str(e)[:50]}",
            details={"url": url},
        )


def check_qdrant_coverage() -> VerificationResult:
    """Check Qdrant vector collection coverage."""
    try:
        response = requests.get(
            "http://localhost:6333/collections/archon_vectors", timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            vector_count = data.get("result", {}).get("vectors_count", 0)

            # Get file count from Memgraph for comparison
            driver = GraphDatabase.driver("bolt://localhost:7687")
            with driver.session() as session:
                result = session.run(
                    """
                    MATCH (f:File)
                    WHERE f.project_name IS NOT NULL
                    RETURN count(f) as total
                """
                )
                file_count = result.single()["total"]
            driver.close()

            coverage_pct = (vector_count / file_count * 100) if file_count > 0 else 0

            if coverage_pct >= 90:
                status = "PASS"
                message = f"{vector_count:,} vectors ({coverage_pct:.1f}% of {file_count:,} files)"
            elif coverage_pct >= 50:
                status = "WARN"
                message = f"{vector_count:,} vectors ({coverage_pct:.1f}% coverage) - needs indexing"
            else:
                status = "FAIL"
                message = f"{vector_count:,} vectors ({coverage_pct:.1f}% coverage) - severely low"

            return VerificationResult(
                name="Qdrant Vector Coverage",
                status=status,
                message=message,
                details={
                    "vectors": vector_count,
                    "files": file_count,
                    "coverage_pct": round(coverage_pct, 2),
                },
            )
        else:
            return VerificationResult(
                name="Qdrant Vector Coverage",
                status="FAIL",
                message=f"Qdrant API returned {response.status_code}",
            )

    except Exception as e:
        return VerificationResult(
            name="Qdrant Vector Coverage",
            status="FAIL",
            message=f"Check failed: {str(e)[:50]}",
        )


def check_memgraph_graph_structure() -> VerificationResult:
    """Check Memgraph graph structure and data quality."""
    try:
        driver = GraphDatabase.driver("bolt://localhost:7687")
        with driver.session() as session:
            # Get node counts by type
            node_stats = session.run(
                """
                MATCH (n)
                WITH labels(n) as labels, count(n) as count
                RETURN labels[0] as node_type, count
                ORDER BY count DESC
            """
            )
            nodes_by_type = {
                record["node_type"]: record["count"] for record in node_stats
            }

            # Get relationship counts
            rel_stats = session.run(
                """
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY count DESC
            """
            )
            rels_by_type = {record["rel_type"]: record["count"] for record in rel_stats}

            # Check for orphaned data (exclude module imports)
            orphaned_files = session.run(
                """
                MATCH (f:File)
                WHERE (f.project_name IS NULL OR f.language IS NULL)
                  AND (f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/')
                RETURN count(f) as count
            """
            ).single()["count"]

            # Sample diagnostics for when relationships are missing
            sample_file = None
            sample_entity = None
            if len(rels_by_type) == 0 and nodes_by_type.get("File", 0) > 0:
                # Get sample FILE node to check for relationship metadata
                file_sample = session.run(
                    """
                    MATCH (f:File)
                    RETURN f.entity_count as entity_count, f.import_count as import_count
                    LIMIT 1
                """
                ).single()
                if file_sample:
                    sample_file = dict(file_sample)

                # Get sample Entity node to check for file linkage
                entity_sample = session.run(
                    """
                    MATCH (e:Entity)
                    RETURN e.file_hash as file_hash, e.source_path as source_path
                    LIMIT 1
                """
                ).single()
                if entity_sample:
                    sample_entity = dict(entity_sample)

        driver.close()

        total_nodes = sum(nodes_by_type.values())
        total_rels = sum(rels_by_type.values())

        # Determine status with more nuanced relationship checking
        if orphaned_files > 0:
            status = "WARN"
            message = f"Graph has {orphaned_files:,} orphaned files needing cleanup"
        elif total_rels == 0 and total_nodes > 1000:
            status = "WARN"
            message = f"Graph has {total_nodes:,} nodes but NO relationships - entities not linked!"
        elif orphaned_files == 0 and total_nodes > 0:
            status = "PASS"
            message = (
                f"Graph healthy: {total_nodes:,} nodes, {total_rels:,} relationships"
            )
        else:
            status = "FAIL"
            message = "Empty graph or connection failed"

        details = {
            "total_nodes": total_nodes,
            "total_relationships": total_rels,
            "nodes_by_type": nodes_by_type,
            "relationships_by_type": rels_by_type if rels_by_type else {},
            "orphaned_files": orphaned_files,
        }

        # Add diagnostic info if relationships are missing
        if total_rels == 0 and sample_file:
            details["diagnostic"] = {
                "issue": "No relationships despite having nodes",
                "sample_file_metadata": sample_file,
                "sample_entity_metadata": sample_entity,
                "likely_cause": "Relationship creation not implemented or not being called during indexing",
            }

        return VerificationResult(
            name="Memgraph Graph Structure",
            status=status,
            message=message,
            details=details,
        )

    except Exception as e:
        return VerificationResult(
            name="Memgraph Graph Structure",
            status="FAIL",
            message=f"Failed to check graph: {str(e)}",
        )


def check_file_tree_graph() -> VerificationResult:
    """Check file tree graph structure (PROJECT/DIRECTORY/CONTAINS relationships)."""
    try:
        driver = GraphDatabase.driver("bolt://localhost:7687")
        with driver.session() as session:
            # Get PROJECT node count
            project_count = session.run(
                """
                MATCH (p:PROJECT)
                RETURN count(p) as count
            """
            ).single()["count"]

            # Get DIRECTORY node count (note: using 'Directory' label, not 'DIRECTORY')
            directory_count = session.run(
                """
                MATCH (d:Directory)
                RETURN count(d) as count
            """
            ).single()["count"]

            # Get CONTAINS relationship count
            contains_count = session.run(
                """
                MATCH ()-[r:CONTAINS]->()
                RETURN count(r) as count
            """
            ).single()["count"]

            # Get orphaned FILE nodes (files not connected via CONTAINS to PROJECT/DIRECTORY)
            # Exclude module imports (they don't have filesystem paths)
            # Use OPTIONAL MATCH to avoid unbounded variable error in Memgraph
            orphaned_files = session.run(
                """
                MATCH (f:File)
                WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                OPTIONAL MATCH path = (f)<-[:CONTAINS*]-(:PROJECT)
                WITH f, path
                WHERE path IS NULL
                RETURN count(f) as count
            """
            ).single()["count"]

            # Get total FILE count for context (source files only, not module imports)
            total_files = session.run(
                """
                MATCH (f:File)
                WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                RETURN count(f) as count
            """
            ).single()["count"]

        driver.close()

        # Determine status
        if (
            project_count > 0
            and directory_count > 0
            and contains_count > 0
            and orphaned_files == 0
        ):
            status = "PASS"
            message = f"Tree graph healthy: {project_count} PROJECT, {directory_count} DIRs, {contains_count} CONTAINS, 0 orphans"
        elif project_count == 0 or directory_count == 0:
            status = "WARN"
            message = f"Tree graph missing: {project_count} PROJECT, {directory_count} DIRs (needs build_directory_tree.py)"
        elif orphaned_files > 0:
            orphan_pct = (orphaned_files / total_files * 100) if total_files > 0 else 0
            status = "FAIL"
            message = f"Tree graph has {orphaned_files:,} orphaned files ({orphan_pct:.1f}% of {total_files:,} total)"
        else:
            status = "WARN"
            message = f"Tree graph incomplete: {project_count} PROJECT, {directory_count} DIRs, {contains_count} CONTAINS"

        return VerificationResult(
            name="File Tree Graph",
            status=status,
            message=message,
            details={
                "project_nodes": project_count,
                "directory_nodes": directory_count,
                "contains_relationships": contains_count,
                "orphaned_files": orphaned_files,
                "total_files": total_files,
            },
        )

    except Exception as e:
        return VerificationResult(
            name="File Tree Graph",
            status="FAIL",
            message=f"Failed to check tree graph: {str(e)}",
        )


def generate_recommendations(report: VerificationReport) -> None:
    """Generate recommendations based on verification results."""
    # Check for missing relationships
    graph_result = next(
        (r for r in report.results if r.name == "Memgraph Graph Structure"), None
    )
    if graph_result and graph_result.details:
        if (
            graph_result.details.get("total_relationships", 0) == 0
            and graph_result.details.get("total_nodes", 0) > 1000
        ):
            report.recommendations.append(
                "Missing relationships: Check if memgraph_adapter.store_relationships() is being called during indexing. "
                "Nodes have metadata (file_hash, entity_count) but no graph edges."
            )

    # Check for orphaned data
    lang_result = next(
        (r for r in report.results if r.name == "Language Field Coverage"), None
    )
    if lang_result and lang_result.status == "WARN" and lang_result.details:
        projects = lang_result.details.get("projects", [])
        orphaned = next((p for p in projects if p["project"] == "NULL"), None)
        if orphaned and orphaned["files"] > 0:
            report.recommendations.append(
                f"Clean up {orphaned['files']:,} orphaned FILE nodes: "
                f"bash scripts/cleanup_orphaned_data.sh"
            )

    # Check for low Qdrant coverage
    qdrant_result = next(
        (r for r in report.results if r.name == "Qdrant Vector Coverage"), None
    )
    if qdrant_result and qdrant_result.status in ["WARN", "FAIL"]:
        report.recommendations.append(
            "Re-index repository to populate Qdrant vectors: "
            "python3 scripts/bulk_ingest_repository.py /path/to/project"
        )

    # Check for missing or incomplete tree graph
    tree_result = next((r for r in report.results if r.name == "File Tree Graph"), None)
    if tree_result and tree_result.status == "WARN":
        if tree_result.details and tree_result.details.get("project_nodes", 0) == 0:
            report.recommendations.append(
                "Build file tree graph structure: "
                "python3 scripts/build_directory_tree.py"
            )
    elif tree_result and tree_result.status == "FAIL":
        if tree_result.details:
            orphaned = tree_result.details.get("orphaned_files", 0)
            if orphaned > 0:
                report.recommendations.append(
                    f"Fix {orphaned:,} orphaned files in tree graph: "
                    "Run scripts/migrate_orphaned_relationships.py or rebuild tree"
                )

    # Check for failed services
    failed_services = [
        r for r in report.results if r.status == "FAIL" and "Service" in r.name
    ]
    for service in failed_services:
        container_name = service.name.lower().replace(" ", "-")
        report.recommendations.append(
            f"Restart {service.name}: docker restart {container_name}"
        )


def print_report(report: VerificationReport, verbose: bool = False) -> None:
    """Print human-readable report."""
    print("\n" + "=" * 70)
    print("🔍 ENVIRONMENT VERIFICATION REPORT")
    print("=" * 70)
    print(f"Timestamp: {report.timestamp}\n")

    # Group results by status
    passed = [r for r in report.results if r.status == "PASS"]
    warned = [r for r in report.results if r.status == "WARN"]
    failed = [r for r in report.results if r.status == "FAIL"]

    # Print results
    for result in report.results:
        if result.status == "PASS":
            icon = "✅"
        elif result.status == "WARN":
            icon = "⚠️"
        else:
            icon = "❌"

        print(f"{icon} {result.name:40s} {result.message}")

        if verbose and result.details:
            for key, value in result.details.items():
                if key == "projects" and isinstance(value, list):
                    print(f"   Projects:")
                    for project in value:
                        proj_name = project["project"]
                        files = project["files"]
                        coverage = project["coverage_pct"]
                        print(
                            f"     - {proj_name:30s}: {files:5,} files ({coverage:6.2f}% language)"
                        )
                elif key == "nodes_by_type" and isinstance(value, dict):
                    print(f"   Nodes by Type:")
                    for node_type, count in value.items():
                        print(f"     - {node_type:30s}: {count:>6,}")
                elif key == "relationships_by_type" and isinstance(value, dict):
                    if value:
                        print(f"   Relationships by Type:")
                        for rel_type, count in value.items():
                            print(f"     - {rel_type:30s}: {count:>6,}")
                    else:
                        print(f"   Relationships by Type: (none)")
                elif key == "diagnostic" and isinstance(value, dict):
                    print(f"   ⚠️  DIAGNOSTIC INFORMATION:")
                    print(f"      Issue: {value.get('issue', 'Unknown')}")
                    if value.get("sample_file_metadata"):
                        print(
                            f"      Sample FILE has metadata: {value['sample_file_metadata']}"
                        )
                    if value.get("sample_entity_metadata"):
                        print(
                            f"      Sample Entity has linkage: {value['sample_entity_metadata']}"
                        )
                    print(f"      Likely Cause: {value.get('likely_cause', 'Unknown')}")
                elif not isinstance(value, (list, dict)):
                    print(f"   {key}: {value}")

    # Overall status
    print(f"\n{'=' * 70}")
    if report.overall_status == "PASS":
        print("🎉 Overall Status: PASS - All checks passed!")
    elif report.overall_status == "WARN":
        print("⚠️  Overall Status: WARN - Some issues need attention")
    else:
        print("❌ Overall Status: FAIL - Critical issues found")

    print(f"   Passed: {len(passed)}, Warned: {len(warned)}, Failed: {len(failed)}")

    # Recommendations
    if report.recommendations:
        print(f"\n📋 RECOMMENDATIONS:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"   {i}. {rec}")

    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Verify recent infrastructure fixes")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed output")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    # Create report
    report = VerificationReport(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Run checks
    report.results.append(check_vllm_service())
    report.results.append(
        check_service_health("archon-intelligence", "http://localhost:8053")
    )
    report.results.append(
        check_service_health("archon-bridge", "http://localhost:8054")
    )
    report.results.append(
        check_service_health("archon-search", "http://localhost:8055")
    )
    report.results.append(check_memgraph_graph_structure())
    report.results.append(check_memgraph_language_coverage())
    report.results.append(check_project_name_consistency())
    report.results.append(check_qdrant_coverage())
    report.results.append(check_file_tree_graph())

    # Determine overall status
    has_failures = any(r.status == "FAIL" for r in report.results)
    has_warnings = any(r.status == "WARN" for r in report.results)

    if has_failures:
        report.overall_status = "FAIL"
    elif has_warnings:
        report.overall_status = "WARN"
    else:
        report.overall_status = "PASS"

    # Generate recommendations
    generate_recommendations(report)

    # Output
    if args.json:
        output = asdict(report)
        print(json.dumps(output, indent=2))
    else:
        print_report(report, verbose=args.verbose)

    # Exit code
    sys.exit(
        0
        if report.overall_status == "PASS"
        else 1 if report.overall_status == "WARN" else 2
    )


if __name__ == "__main__":
    main()
