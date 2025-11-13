#!/usr/bin/env python3
"""
Automated Data Integrity Validation for Archon Intelligence Platform

Checks:
- Memgraph document nodes count
- Qdrant vector collection coverage
- Search service file path retrieval
- Metadata filtering functionality

Usage:
    python3 scripts/validate_data_integrity.py [--verbose] [--json]
"""

import json
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict

import requests

# Configuration
QDRANT_URL = "http://localhost:6333"
SEARCH_URL = "http://localhost:8055"
MEMGRAPH_CONTAINER = "memgraph"


def check_memgraph() -> Dict[str, Any]:
    """Check Memgraph document nodes (optional - skipped if not accessible)"""
    try:
        # Note: mgconsole is not available in the container
        # Memgraph validation is optional - skip for now
        return {
            "status": "skipped",
            "document_count": None,
            "error": "Memgraph validation skipped (mgconsole not available in container)",
        }
    except Exception as e:
        return {"status": "error", "document_count": 0, "error": str(e)}


def check_qdrant() -> Dict[str, Any]:
    """Check Qdrant vector collections"""
    try:
        # Get all collections
        response = requests.get(f"{QDRANT_URL}/collections", timeout=5)
        response.raise_for_status()

        result = response.json().get("result", {})
        collections = result.get("collections", [])

        # Get specific archon_vectors collection details
        archon_vectors_count = 0
        archon_collection_found = False
        try:
            archon_response = requests.get(
                f"{QDRANT_URL}/collections/archon_vectors", timeout=5
            )
            if archon_response.status_code == 200:
                archon_collection_found = True
                archon_data = archon_response.json().get("result", {})
                archon_vectors_count = archon_data.get(
                    "vectors_count", archon_data.get("points_count", 0)
                )
        except Exception:
            pass  # Collection might not exist

        # Handle different response structures for all collections
        total_points = 0
        for c in collections:
            points = c.get("points_count", c.get("points", 0))
            total_points += points

        # Find file-related collections
        file_collections = []
        for c in collections:
            name = c.get("name", "")
            if (
                "file" in name.lower()
                or "omniarchon" in name.lower()
                or "archon" in name.lower()
            ):
                points = c.get("points_count", c.get("points", 0))
                file_collections.append({"name": name, "points": points})

        return {
            "status": (
                "healthy" if (total_points > 0 or archon_vectors_count > 0) else "empty"
            ),
            "total_collections": len(collections),
            "total_points": total_points,
            "archon_vectors_count": archon_vectors_count,
            "archon_collection_found": archon_collection_found,
            "file_collections": file_collections,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_search_paths() -> Dict[str, Any]:
    """Test file path retrieval from search"""
    try:
        response = requests.post(
            f"{SEARCH_URL}/search",
            json={"query": "python code", "limit": 10},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()

        # Handle different response structures
        if isinstance(data, list):
            # Response is directly a list of results
            results = data
            total_results = len(data)
        elif isinstance(data, dict):
            # Response is a dictionary
            results = data.get("results", [])
            if not results and "results" in data:
                # Try nested structure
                vector_results = data.get("results", {})
                if isinstance(vector_results, dict):
                    results = vector_results.get("vector_search", {}).get("results", [])
            total_results = data.get("total_results", len(results))
        else:
            results = []
            total_results = 0

        # Count results with valid paths
        paths_found = 0
        for r in results:
            if isinstance(r, dict):
                path = r.get("metadata", {}).get("file_path") or r.get(
                    "metadata", {}
                ).get("source_path")
                if path and path != "null" and not path.startswith("http"):
                    paths_found += 1

        path_percentage = (paths_found / len(results) * 100) if results else 0

        return {
            "status": "working" if len(results) > 0 else "no_results",
            "results_count": len(results),
            "total_results": total_results,
            "paths_found": paths_found,
            "path_retrieval_rate": f"{path_percentage:.1f}%",
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_metadata_filtering() -> Dict[str, Any]:
    """Test metadata filtering functionality"""
    try:
        # Test language filter
        response = requests.post(
            f"{SEARCH_URL}/search",
            json={
                "query": "code functions",
                "filters": {"language": "python"},
                "limit": 5,
            },
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()

        # Handle different response structures
        if isinstance(data, list):
            # Response is directly a list of results
            results = data
        elif isinstance(data, dict):
            # Response is a dictionary
            results = data.get("results", [])
            if not results and "results" in data:
                # Try nested structure
                vector_results = data.get("results", {})
                if isinstance(vector_results, dict):
                    results = vector_results.get("vector_search", {}).get("results", [])

        # Check if filters applied correctly
        python_results = 0
        for r in results:
            if (
                isinstance(r, dict)
                and r.get("metadata", {}).get("language") == "python"
            ):
                python_results += 1

        filter_working = python_results > 0 if results else None

        return {
            "status": "working" if filter_working else "not_working",
            "results_count": len(results),
            "filtered_correctly": python_results,
            "filter_accuracy": (
                f"{(python_results/len(results)*100):.1f}%" if results else "N/A"
            ),
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def generate_report(verbose: bool = False, json_output: bool = False) -> Dict[str, Any]:
    """Run all validation checks and generate report"""

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "memgraph": check_memgraph(),
        "qdrant": check_qdrant(),
        "search_paths": check_search_paths(),
        "metadata_filtering": check_metadata_filtering(),
    }

    # Calculate overall health (excluding skipped components)
    components_to_check = [
        report["qdrant"],
        report["search_paths"],
        report["metadata_filtering"],
    ]

    # Only include Memgraph if it's not skipped
    if report["memgraph"]["status"] != "skipped":
        components_to_check.append(report["memgraph"])

    healthy_count = sum(
        1
        for component in components_to_check
        if component["status"] in ["healthy", "working"]
    )

    total_components = len(components_to_check)

    report["overall_health"] = {
        "status": (
            "healthy"
            if healthy_count >= (total_components - 1)  # Allow one failure
            else "degraded" if healthy_count >= (total_components // 2) else "unhealthy"
        ),
        "healthy_components": healthy_count,
        "total_components": total_components,
    }

    return report


def print_report(report: Dict[str, Any], verbose: bool = False):
    """Print human-readable report"""
    print("\n" + "=" * 70)
    print("📊 ARCHON DATA INTEGRITY VALIDATION REPORT")
    print("=" * 70)
    print(f"Timestamp: {report['timestamp']}")
    print()

    # Overall health
    status_emoji = {"healthy": "🟢", "degraded": "🟡", "unhealthy": "🔴"}
    health = report["overall_health"]
    print(
        f"{status_emoji.get(health['status'], '⚪')} Overall Health: {health['status'].upper()}"
    )
    print(
        f"   {health['healthy_components']}/{health['total_components']} components healthy"
    )
    print()

    # Memgraph
    mg = report["memgraph"]
    print(f"📊 Memgraph Knowledge Graph")
    print(f"   Status: {mg['status']}")
    if mg["document_count"] is not None:
        print(f"   Document nodes: {mg['document_count']:,}")
    if mg["error"]:
        print(f"   ℹ️  Note: {mg['error']}")
    print()

    # Qdrant
    qd = report["qdrant"]
    print(f"🔍 Qdrant Vector Database")
    print(f"   Status: {qd.get('status', 'error')}")
    if "total_points" in qd:
        print(f"   Total vectors: {qd['total_points']:,}")
        print(f"   Collections: {qd['total_collections']}")
        if qd.get("archon_collection_found"):
            print(f"   Archon vectors: {qd['archon_vectors_count']:,}")
        if verbose and qd.get("file_collections"):
            print(f"   File collections:")
            for fc in qd["file_collections"]:
                print(f"      - {fc['name']}: {fc['points']:,} points")
    if qd.get("error"):
        print(f"   ⚠️  Error: {qd['error']}")
    print()

    # Search paths
    sp = report["search_paths"]
    print(f"📁 Search Service")
    print(f"   Status: {sp['status']}")
    if "paths_found" in sp:
        print(f"   Results returned: {sp['results_count']}")
        if sp.get("total_results"):
            print(f"   Total indexed: {sp['total_results']}")
        print(f"   Paths found: {sp['paths_found']}/{sp['results_count']}")
        print(f"   Retrieval rate: {sp['path_retrieval_rate']}")
    if sp.get("error"):
        print(f"   ⚠️  Error: {sp['error']}")
    print()

    # Metadata filtering
    mf = report["metadata_filtering"]
    print(f"🏷️  Metadata Filtering")
    print(f"   Status: {mf['status']}")
    if "filtered_correctly" in mf:
        print(
            f"   Filter test: {mf['filtered_correctly']}/{mf['results_count']} correct"
        )
        print(f"   Accuracy: {mf['filter_accuracy']}")
    if mf.get("error"):
        print(f"   ⚠️  Error: {mf['error']}")

    print("=" * 70)
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate Archon data integrity")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    args = parser.parse_args()

    report = generate_report(verbose=args.verbose, json_output=args.json)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report, verbose=args.verbose)

    # Exit code based on health
    health_status = report["overall_health"]["status"]
    sys.exit(
        0 if health_status == "healthy" else 1 if health_status == "degraded" else 2
    )


if __name__ == "__main__":
    main()
