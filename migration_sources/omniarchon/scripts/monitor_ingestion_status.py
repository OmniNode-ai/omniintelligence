#!/usr/bin/env python3
"""
Comprehensive ingestion monitoring script.
Verifies that documents are actually being processed correctly.

Usage:
    python3 scripts/monitor_ingestion_status.py [--watch] [--interval SECONDS]
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

import requests
from neo4j import GraphDatabase


class IngestionMonitor:
    """Monitor ingestion progress and data quality."""

    def __init__(self):
        self.qdrant_url = "http://localhost:6333"
        self.collection_name = "archon_vectors"
        self.memgraph_uri = "bolt://localhost:7687"
        self.expected_projects = [
            "omnidash",
            "omnibase_core",
            "omninode_bridge",
            "omniclaude",
            "omniarchon",
        ]
        self.expected_total_files = 34812

    def get_collection_info(self) -> Dict[str, Any]:
        """Get Qdrant collection information."""
        try:
            response = requests.get(
                f"{self.qdrant_url}/collections/{self.collection_name}"
            )
            response.raise_for_status()
            return response.json()["result"]
        except Exception as e:
            return {"error": str(e)}

    def get_documents_count(self) -> int:
        """Get total document count from Qdrant."""
        info = self.get_collection_info()
        if "error" in info:
            return 0
        return info.get("points_count", 0)

    def get_project_counts(self) -> Dict[str, int]:
        """Get document count per project."""
        project_counts = {}

        for project in self.expected_projects:
            try:
                response = requests.post(
                    f"{self.qdrant_url}/collections/{self.collection_name}/points/scroll",
                    json={
                        "filter": {
                            "must": [
                                {"key": "project_name", "match": {"value": project}}
                            ]
                        },
                        "limit": 1,
                        "with_payload": False,
                        "with_vector": False,
                    },
                )
                response.raise_for_status()

                # Get actual count using count API
                count_response = requests.post(
                    f"{self.qdrant_url}/collections/{self.collection_name}/points/count",
                    json={
                        "filter": {
                            "must": [
                                {"key": "project_name", "match": {"value": project}}
                            ]
                        },
                        "exact": True,
                    },
                )
                count_response.raise_for_status()
                project_counts[project] = count_response.json()["result"]["count"]
            except Exception as e:
                project_counts[project] = f"Error: {e}"

        return project_counts

    def verify_blake3_hashes(self, sample_size: int = 10) -> Dict[str, Any]:
        """Verify BLAKE3 hashes are present and correctly formatted."""
        try:
            response = requests.post(
                f"{self.qdrant_url}/collections/{self.collection_name}/points/scroll",
                json={
                    "limit": sample_size,
                    "with_payload": ["content_hash", "project_name", "relative_path"],
                    "with_vector": False,
                },
            )
            response.raise_for_status()
            points = response.json()["result"]["points"]

            total_sampled = len(points)
            blake3_count = 0
            sha256_count = 0
            missing_count = 0
            samples = []

            for point in points:
                payload = point.get("payload", {})
                content_hash = payload.get("content_hash")

                sample = {
                    "project": payload.get("project_name", "unknown"),
                    "path": payload.get("relative_path", "unknown"),
                    "hash": content_hash,
                }

                if content_hash:
                    if content_hash.startswith("blake3:"):
                        blake3_count += 1
                        sample["status"] = "✅ BLAKE3"
                    elif content_hash.startswith("sha256:"):
                        sha256_count += 1
                        sample["status"] = "⚠️ SHA256 (old)"
                    else:
                        sample["status"] = "❌ Invalid format"
                else:
                    missing_count += 1
                    sample["status"] = "❌ Missing"

                samples.append(sample)

            return {
                "total_sampled": total_sampled,
                "blake3_count": blake3_count,
                "sha256_count": sha256_count,
                "missing_count": missing_count,
                "blake3_percentage": (
                    (blake3_count / total_sampled * 100) if total_sampled > 0 else 0
                ),
                "samples": samples,
            }
        except Exception as e:
            return {"error": str(e)}

    def verify_embeddings(self, sample_size: int = 5) -> Dict[str, Any]:
        """Verify embeddings are present and correct dimensions."""
        try:
            response = requests.post(
                f"{self.qdrant_url}/collections/{self.collection_name}/points/scroll",
                json={
                    "limit": sample_size,
                    "with_payload": ["project_name", "relative_path"],
                    "with_vector": True,
                },
            )
            response.raise_for_status()
            points = response.json()["result"]["points"]

            results = []
            for point in points:
                vector = point.get("vector", [])
                payload = point.get("payload", {})

                # Check if vector is zero
                is_zero = all(v == 0.0 for v in vector) if vector else True

                results.append(
                    {
                        "project": payload.get("project_name", "unknown"),
                        "path": payload.get("relative_path", "unknown")[:50] + "...",
                        "dimension": len(vector),
                        "is_zero": is_zero,
                        "status": "❌ Zero vector" if is_zero else "✅ Valid",
                    }
                )

            total = len(results)
            zero_count = sum(1 for r in results if r["is_zero"])

            return {
                "total_sampled": total,
                "zero_vectors": zero_count,
                "valid_vectors": total - zero_count,
                "expected_dimension": 1536,
                "actual_dimension": results[0]["dimension"] if results else 0,
                "samples": results,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_memgraph_stats(self) -> Dict[str, Any]:
        """Get Memgraph knowledge graph statistics."""
        try:
            driver = GraphDatabase.driver(self.memgraph_uri)
            with driver.session() as session:
                # Total nodes
                total_result = session.run("MATCH (n) RETURN count(n) as count")
                total_nodes = total_result.single()["count"]

                # Document nodes
                doc_result = session.run("MATCH (d:Document) RETURN count(d) as count")
                doc_nodes = doc_result.single()["count"]

                # File nodes
                file_result = session.run("MATCH (f:File) RETURN count(f) as count")
                file_nodes = file_result.single()["count"]

                # Entity nodes (if any)
                entity_result = session.run("MATCH (e:Entity) RETURN count(e) as count")
                entity_nodes = entity_result.single()["count"]

            driver.close()

            return {
                "total_nodes": total_nodes,
                "document_nodes": doc_nodes,
                "file_nodes": file_nodes,
                "entity_nodes": entity_nodes,
                "status": (
                    "✅ Healthy"
                    if doc_nodes > 0 or file_nodes > 0
                    else "⚠️ No Document/File nodes"
                ),
            }
        except Exception as e:
            return {"error": str(e), "status": "❌ Error"}

    def get_consumer_metrics(self) -> Dict[str, Any]:
        """Get consumer processing metrics."""
        metrics = {}
        consumer_ports = [8090, 8091, 8092, 8063]

        for port in consumer_ports:
            try:
                response = requests.get(f"http://localhost:{port}/metrics", timeout=2)
                response.raise_for_status()
                data = response.json()

                consumer_name = f"consumer-{port}"
                consumer_data = data.get("consumer", {})

                metrics[consumer_name] = {
                    "lag": consumer_data.get("lag", {}),
                    "processed": consumer_data.get("messages_processed", 0),
                    "status": "✅ Running",
                }
            except Exception as e:
                metrics[f"consumer-{port}"] = {"status": f"❌ Error: {str(e)}"}

        return metrics

    def print_report(self):
        """Print comprehensive status report."""
        print("\n" + "=" * 80)
        print(
            f"ARCHON INGESTION STATUS REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print("=" * 80)

        # 1. Overall Progress
        print("\n📊 OVERALL PROGRESS")
        print("-" * 80)
        total_docs = self.get_documents_count()
        progress_pct = (
            (total_docs / self.expected_total_files * 100)
            if self.expected_total_files > 0
            else 0
        )

        print(
            f"Total Documents in Qdrant: {total_docs:,} / {self.expected_total_files:,} ({progress_pct:.1f}%)"
        )

        if total_docs == 0:
            print("❌ WARNING: No documents found in Qdrant!")
            print("   This indicates ingestion has not started or failed completely.")
        elif total_docs < 100:
            print(
                "⚠️  WARNING: Very few documents found. Ingestion may have just started."
            )

        # 2. Per-Project Counts
        print("\n📁 DOCUMENTS PER PROJECT")
        print("-" * 80)
        project_counts = self.get_project_counts()

        for project in self.expected_projects:
            count = project_counts.get(project, 0)
            status = "✅" if isinstance(count, int) and count > 0 else "❌"
            print(f"{status} {project:<20} {count:>10}")

        # 3. BLAKE3 Hash Verification
        print("\n🔐 BLAKE3 HASH VERIFICATION (Sample: 10 documents)")
        print("-" * 80)
        blake3_results = self.verify_blake3_hashes(sample_size=10)

        if "error" in blake3_results:
            print(f"❌ Error: {blake3_results['error']}")
        else:
            print(
                f"BLAKE3 hashes:  {blake3_results['blake3_count']}/{blake3_results['total_sampled']} ({blake3_results['blake3_percentage']:.1f}%)"
            )
            print(
                f"SHA256 hashes:  {blake3_results['sha256_count']}/{blake3_results['total_sampled']}"
            )
            print(
                f"Missing hashes: {blake3_results['missing_count']}/{blake3_results['total_sampled']}"
            )

            if blake3_results["blake3_percentage"] < 100:
                print("\n⚠️  WARNING: Not all documents have BLAKE3 hashes!")
                print("Sample documents:")
                for sample in blake3_results["samples"][:5]:
                    print(f"  {sample['status']} {sample['project']}/{sample['path']}")
                    print(f"     Hash: {sample['hash']}")

        # 4. Embedding Verification
        print("\n🔢 EMBEDDING VERIFICATION (Sample: 5 documents)")
        print("-" * 80)
        embedding_results = self.verify_embeddings(sample_size=5)

        if "error" in embedding_results:
            print(f"❌ Error: {embedding_results['error']}")
        else:
            print(f"Expected dimension: {embedding_results['expected_dimension']}")
            print(f"Actual dimension:   {embedding_results['actual_dimension']}")
            print(
                f"Valid vectors:      {embedding_results['valid_vectors']}/{embedding_results['total_sampled']}"
            )
            print(
                f"Zero vectors:       {embedding_results['zero_vectors']}/{embedding_results['total_sampled']}"
            )

            if embedding_results["zero_vectors"] > 0:
                print(
                    "\n❌ WARNING: Found zero vectors! This indicates embedding generation failure."
                )

            if (
                embedding_results["actual_dimension"]
                != embedding_results["expected_dimension"]
            ):
                print(
                    f"\n❌ WARNING: Dimension mismatch! Expected {embedding_results['expected_dimension']}, got {embedding_results['actual_dimension']}"
                )

        # 5. Memgraph Knowledge Graph
        print("\n🕸️  MEMGRAPH KNOWLEDGE GRAPH")
        print("-" * 80)
        memgraph_stats = self.get_memgraph_stats()

        if "error" in memgraph_stats:
            print(f"❌ Error: {memgraph_stats['error']}")
        else:
            print(f"Total nodes:    {memgraph_stats['total_nodes']:,}")
            print(f"Document nodes: {memgraph_stats['document_nodes']:,}")
            print(f"File nodes:     {memgraph_stats['file_nodes']:,}")
            print(f"Entity nodes:   {memgraph_stats['entity_nodes']:,}")
            print(f"Status: {memgraph_stats['status']}")

        # 6. Consumer Status
        print("\n⚙️  CONSUMER STATUS")
        print("-" * 80)
        consumer_metrics = self.get_consumer_metrics()

        for consumer_name, data in consumer_metrics.items():
            print(f"\n{consumer_name}:")
            print(f"  Status: {data.get('status', 'Unknown')}")

            if "lag" in data:
                lag = data["lag"]
                if lag:
                    total_lag = sum(lag.values()) if isinstance(lag, dict) else 0
                    print(f"  Total lag: {total_lag:,} messages")
                    if isinstance(lag, dict):
                        for partition, count in lag.items():
                            print(f"    {partition}: {count:,}")
                else:
                    print(f"  Lag: 0 (caught up)")

            if "processed" in data:
                print(f"  Processed: {data['processed']:,} messages")

        # 7. Overall Assessment
        print("\n" + "=" * 80)
        print("OVERALL ASSESSMENT")
        print("=" * 80)

        issues = []

        if total_docs == 0:
            issues.append("❌ CRITICAL: No documents in Qdrant")

        if total_docs > 0 and total_docs < self.expected_total_files * 0.1:
            issues.append(f"⚠️  WARNING: Only {progress_pct:.1f}% complete")

        if (
            not isinstance(blake3_results, dict)
            or blake3_results.get("blake3_percentage", 0) < 100
        ):
            issues.append("⚠️  WARNING: Not all documents have BLAKE3 hashes")

        if (
            not isinstance(embedding_results, dict)
            or embedding_results.get("zero_vectors", 0) > 0
        ):
            issues.append(
                "❌ CRITICAL: Found zero vectors (embedding generation failing)"
            )

        if not isinstance(memgraph_stats, dict) or (
            memgraph_stats.get("document_nodes", 0) == 0
            and memgraph_stats.get("file_nodes", 0) == 0
        ):
            issues.append("⚠️  WARNING: No Document/File nodes in Memgraph")

        if not issues:
            print("\n✅ All checks passed! Ingestion is proceeding correctly.")
            print(
                f"   Progress: {total_docs:,}/{self.expected_total_files:,} ({progress_pct:.1f}%)"
            )
        else:
            print("\n⚠️  Issues found:")
            for issue in issues:
                print(f"   {issue}")

        print("\n" + "=" * 80)

    def watch(self, interval: int = 30):
        """Watch ingestion progress continuously."""
        print(f"Watching ingestion progress (updating every {interval} seconds)")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                self.print_report()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nStopped monitoring.")


def main():
    parser = argparse.ArgumentParser(description="Monitor Archon ingestion status")
    parser.add_argument(
        "--watch", action="store_true", help="Continuously monitor and update status"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Update interval in seconds (default: 30)",
    )

    args = parser.parse_args()

    monitor = IngestionMonitor()

    if args.watch:
        monitor.watch(interval=args.interval)
    else:
        monitor.print_report()


if __name__ == "__main__":
    main()
