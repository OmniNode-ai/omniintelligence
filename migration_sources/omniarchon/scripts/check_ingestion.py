#!/usr/bin/env python3
"""
Quick Ingestion Status Checker

Simple, reusable script to check ingestion progress, surface errors, and give general status.

Usage:
    # Quick status check
    python3 scripts/check_ingestion.py

    # Check specific project
    python3 scripts/check_ingestion.py --project omniarchon-reingestion-test

    # Continuous monitoring (updates every 30s)
    python3 scripts/check_ingestion.py --watch --interval 30

    # Show detailed errors
    python3 scripts/check_ingestion.py --show-errors

What it checks:
    ✅ Kafka topics - message counts and consumer lag
    ✅ Qdrant - document count growth
    ✅ Memgraph - entity/relationship counts
    ✅ Consumer health - are consumers running?
    ✅ Recent errors - failures in consumer logs
    ✅ Pipeline velocity - documents processed per minute

Author: Archon Team
Date: 2025-11-06
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# Track whether we've shown the .env warning (to show only once)
_env_warning_shown = False


# Polymorphic .env loader - tries multiple strategies
def load_env_config():
    """
    Polymorphic configuration loader that tries multiple strategies:
    1. python-dotenv if available
    2. Manual .env parsing
    3. Falls back to os.getenv()
    """
    global _env_warning_shown
    env_file_found = False

    # Strategy 1: Try python-dotenv
    try:
        from dotenv import load_dotenv

        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            env_file_found = True
            return
    except ImportError:
        pass

    # Strategy 2: Manual .env file parsing
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        env_file_found = True
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Only set if not already in environment
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = value.strip()

    # Warn if no .env file found (only once)
    if not env_file_found and not _env_warning_shown:
        print(
            "⚠️  Warning: No .env file found, using fallback configuration",
            file=sys.stderr,
        )
        print(f"   Expected location: {env_path.absolute()}", file=sys.stderr)
        print(
            "   Some features may not work correctly without proper configuration.",
            file=sys.stderr,
        )
        _env_warning_shown = True


# Load configuration on module import
load_env_config()


def check_qdrant_status() -> Dict:
    """Check Qdrant vector database status."""
    try:
        response = requests.get(
            "http://localhost:6333/collections/archon_vectors", timeout=5
        )
        if response.status_code == 200:
            data = response.json()["result"]
            return {
                "success": True,
                "vectors_count": data.get("vectors_count", 0),
                "points_count": data.get("points_count", 0),
                "status": data.get("status", "unknown"),
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "Unknown error"}


def check_memgraph_status(project: Optional[str] = None) -> Dict:
    """Check Memgraph knowledge graph status.

    Args:
        project: Optional project name to filter by
    """
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver("bolt://localhost:7687")
        with driver.session() as session:
            # Build WHERE clause for project filtering
            where_clause = ""
            params = {}
            if project:
                where_clause = "WHERE n.project_name = $project"
                params["project"] = project

            # Count nodes by type
            result = session.run(
                f"""
                MATCH (n)
                {where_clause}
                RETURN labels(n)[0] as label, count(n) as count
            """,
                **params,
            )

            node_counts = {}
            total = 0
            for record in result:
                label = record["label"] if record["label"] else "unlabeled"
                count = record["count"]
                node_counts[label] = count
                total += count

            # Count relationships
            if project:
                rel_result = session.run(
                    "MATCH (n)-[r]->() WHERE n.project_name = $project RETURN count(r) as count",
                    project=project,
                )
            else:
                rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = rel_result.single()["count"]

        driver.close()

        return {
            "success": True,
            "total_nodes": total,
            "node_counts": node_counts,
            "relationships": rel_count,
            "filtered_by_project": project,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_kafka_topic(topic_name: str) -> Dict:
    """Check Kafka topic status using rpk."""
    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "omninode-bridge-redpanda",
                "rpk",
                "topic",
                "describe",
                topic_name,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            # Parse output
            lines = result.stdout.split("\n")
            message_count = 0
            partition_count = 0

            for line in lines:
                if "high watermark" in line.lower() or "offset" in line.lower():
                    import re

                    numbers = re.findall(r"\d+", line)
                    if numbers:
                        message_count = max(message_count, int(numbers[-1]))
                if "partitions" in line.lower():
                    try:
                        partition_count = int(line.split(":")[1].strip().split()[0])
                    except:
                        pass

            return {
                "success": True,
                "topic": topic_name,
                "messages": message_count,
                "partitions": partition_count,
            }
    except Exception as e:
        return {"success": False, "topic": topic_name, "error": str(e)}

    return {"success": False, "topic": topic_name, "error": "Unknown error"}


def check_consumer_lag(consumer_group: str = "archon-intelligence-consumers") -> Dict:
    """Check consumer lag."""
    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "omninode-bridge-redpanda",
                "rpk",
                "group",
                "describe",
                consumer_group,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            # Parse output for lag
            lines = result.stdout.split("\n")
            total_lag = 0

            for line in lines:
                if "LAG" in line.upper():
                    import re

                    numbers = re.findall(r"\d+", line)
                    if numbers:
                        # Last number is usually the lag
                        lag = int(numbers[-1])
                        total_lag += lag

            return {
                "success": True,
                "total_lag": total_lag,
                "status": "✅ Caught up" if total_lag == 0 else f"⚠️ Lag: {total_lag}",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "Consumer group not found"}


def check_consumer_health() -> Dict:
    """Check if consumer containers are running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}", "--filter", "name=consumer"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            consumers = [name for name in result.stdout.strip().split("\n") if name]
            return {
                "success": True,
                "consumers": consumers,
                "count": len(consumers),
                "status": (
                    f"✅ {len(consumers)} running" if consumers else "❌ None running"
                ),
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "Unknown error"}


def get_recent_errors(container_names: List[str], minutes: int = 10) -> List[Dict]:
    """Get recent errors from consumer logs."""
    errors = []

    for container in container_names:
        try:
            # Get logs from last N minutes
            since_time = datetime.now() - timedelta(minutes=minutes)
            since_str = since_time.strftime("%Y-%m-%dT%H:%M:%S")

            result = subprocess.run(
                ["docker", "logs", "--since", since_str, container],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                # Parse for errors
                for line in result.stderr.split("\n") + result.stdout.split("\n"):
                    if any(
                        keyword in line.lower()
                        for keyword in ["error", "exception", "failed", "critical"]
                    ):
                        errors.append(
                            {
                                "container": container,
                                "message": line.strip()[:200],  # Truncate long messages
                                "time": "recent",
                            }
                        )
        except Exception as e:
            pass

    return errors[:20]  # Limit to 20 most recent errors


def calculate_velocity(
    current_count: int, previous_count: int, time_diff_seconds: float
) -> float:
    """Calculate processing velocity (documents per minute)."""
    if time_diff_seconds == 0:
        return 0.0

    docs_per_second = (current_count - previous_count) / time_diff_seconds
    return docs_per_second * 60  # Convert to per minute


def print_status_report(show_errors: bool = False, project: Optional[str] = None):
    """Print comprehensive status report.

    Args:
        show_errors: Whether to show recent errors from consumer logs
        project: Optional project name to filter by
    """
    print("\n" + "=" * 80)
    print(f"INGESTION STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if project:
        print(f"PROJECT FILTER: {project}")
    print("=" * 80)

    # 1. Qdrant Status
    print("\n📊 QDRANT VECTOR DATABASE")
    print("-" * 80)
    qdrant_status = check_qdrant_status()

    if qdrant_status["success"]:
        print(f"✅ Status: {qdrant_status['status']}")
        print(f"   Documents: {qdrant_status['vectors_count']:,}")
        print(f"   Points: {qdrant_status['points_count']:,}")
    else:
        print(f"❌ Error: {qdrant_status.get('error', 'Unknown')}")

    # 2. Memgraph Status
    print("\n🕸️  MEMGRAPH KNOWLEDGE GRAPH")
    print("-" * 80)
    memgraph_status = check_memgraph_status(project=project)

    if memgraph_status["success"]:
        if memgraph_status.get("filtered_by_project"):
            print(
                f"✅ Total Nodes (project: {memgraph_status['filtered_by_project']}): {memgraph_status['total_nodes']:,}"
            )
        else:
            print(f"✅ Total Nodes: {memgraph_status['total_nodes']:,}")
        print(f"   Relationships: {memgraph_status['relationships']:,}")
        if memgraph_status["node_counts"]:
            print("   Node Types:")
            for label, count in sorted(
                memgraph_status["node_counts"].items(), key=lambda x: -x[1]
            )[:5]:
                print(f"     - {label}: {count:,}")
    else:
        print(f"❌ Error: {memgraph_status.get('error', 'Unknown')}")

    # 3. Kafka Topics
    print("\n📨 KAFKA TOPICS")
    print("-" * 80)

    # Only check enrichment topics if async enrichment is enabled
    enable_async_enrichment = (
        os.getenv("ENABLE_ASYNC_ENRICHMENT", "false").lower() == "true"
    )

    if enable_async_enrichment:
        topics = [
            "dev.archon-intelligence.enrich-document.v1",
            "dev.archon-intelligence.enrich-document-completed.v1",
            "dev.archon-intelligence.enrich-document-dlq.v1",
        ]

        for topic in topics:
            status = check_kafka_topic(topic)
            topic_short = topic.replace("dev.archon-intelligence.", "")

            if status["success"]:
                print(f"   {topic_short:<40} {status['messages']:>10,} messages")
            else:
                print(f"❌ {topic_short:<40} Error")
    else:
        print("   ℹ️  Async enrichment disabled (ENABLE_ASYNC_ENRICHMENT=false)")
        print("   ℹ️  Enrichment topics not checked")

    # 4. Consumer Status
    print("\n⚙️  CONSUMERS")
    print("-" * 80)

    consumer_health = check_consumer_health()
    if consumer_health["success"]:
        print(f"{consumer_health['status']}")
        if consumer_health["consumers"]:
            for consumer in consumer_health["consumers"]:
                print(f"   - {consumer}")
    else:
        print(f"❌ Error checking consumers: {consumer_health.get('error', 'Unknown')}")

    # Consumer lag
    lag_status = check_consumer_lag()
    if lag_status["success"]:
        print(f"\n   {lag_status['status']}")
        if lag_status["total_lag"] > 100:
            print(f"   ⚠️ WARNING: High lag may indicate slow processing")

    # 5. Recent Errors
    if show_errors:
        print("\n❌ RECENT ERRORS (Last 10 minutes)")
        print("-" * 80)

        consumer_names = consumer_health.get("consumers", [])
        if consumer_names:
            errors = get_recent_errors(consumer_names, minutes=10)

            if errors:
                for error in errors[:10]:  # Show max 10
                    print(f"\n   Container: {error['container']}")
                    print(f"   Message: {error['message']}")
            else:
                print("   ✅ No errors found")
        else:
            print("   ⚠️ No consumers running to check")

    # 6. Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    issues = []

    if not qdrant_status["success"]:
        issues.append("❌ Qdrant unreachable")
    elif qdrant_status["vectors_count"] == 0:
        issues.append("⚠️ No documents in Qdrant")

    if not memgraph_status["success"]:
        issues.append("❌ Memgraph unreachable")
    elif memgraph_status["total_nodes"] == 0:
        issues.append("⚠️ No nodes in Memgraph")

    if not consumer_health["success"] or consumer_health["count"] == 0:
        issues.append("❌ No consumers running")

    if lag_status["success"] and lag_status["total_lag"] > 500:
        issues.append("⚠️ High consumer lag (>500)")

    if issues:
        print("\n⚠️ Issues Found:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ All systems operational")
        if qdrant_status["success"]:
            print(
                f"   Processing: {qdrant_status['vectors_count']:,} documents indexed"
            )

    print("\n" + "=" * 80)


def watch_ingestion(
    interval: int = 30, show_errors: bool = False, project: Optional[str] = None
):
    """Watch ingestion progress continuously.

    Args:
        interval: Update interval in seconds
        show_errors: Whether to show recent errors from consumer logs
        project: Optional project name to filter by
    """
    print(f"📊 Monitoring ingestion (updating every {interval} seconds)")
    if project:
        print(f"   Filtering by project: {project}")
    print("Press Ctrl+C to stop\n")

    previous_count = None
    previous_time = None

    try:
        while True:
            print_status_report(show_errors=show_errors, project=project)

            # Calculate velocity
            qdrant_status = check_qdrant_status()
            if qdrant_status["success"]:
                current_count = qdrant_status["vectors_count"]
                current_time = time.time()

                if previous_count is not None and previous_time is not None:
                    velocity = calculate_velocity(
                        current_count, previous_count, current_time - previous_time
                    )
                    if velocity > 0:
                        print(f"\n⚡ Velocity: {velocity:.1f} documents/minute")

                previous_count = current_count
                previous_time = current_time

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n✅ Monitoring stopped")


def main():
    parser = argparse.ArgumentParser(
        description="Quick ingestion status checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick status check
  python3 scripts/check_ingestion.py

  # Show recent errors
  python3 scripts/check_ingestion.py --show-errors

  # Continuous monitoring
  python3 scripts/check_ingestion.py --watch --interval 30

  # Check specific project
  python3 scripts/check_ingestion.py --project my-project
        """,
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously monitor (updates every interval)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Update interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--show-errors",
        action="store_true",
        help="Show recent errors from consumer logs",
    )
    parser.add_argument("--project", help="Filter by project name (optional)")

    args = parser.parse_args()

    if args.watch:
        watch_ingestion(
            interval=args.interval, show_errors=args.show_errors, project=args.project
        )
    else:
        print_status_report(show_errors=args.show_errors, project=args.project)


if __name__ == "__main__":
    main()
