#!/usr/bin/env python3
"""
Verify language field coverage after vLLM migration.

Checks:
1. Qdrant language field coverage
2. Memgraph language field coverage
3. Sample verification of random files
4. Consistency between Qdrant and Memgraph
"""

import json
import random
from typing import Dict, List, Tuple

import httpx
from neo4j import GraphDatabase


def check_qdrant_coverage() -> Tuple[float, int, int]:
    """Check language field coverage in Qdrant."""
    print("\n" + "=" * 60)
    print("QDRANT LANGUAGE FIELD COVERAGE")
    print("=" * 60)

    # Check which collection has the most documents
    collections_to_check = [
        "archon_vectors",
        "code_generation_patterns",
        "archon-intelligence",
    ]
    collection_name = None
    max_docs = 0

    for coll in collections_to_check:
        try:
            info = httpx.get(f"http://localhost:6333/collections/{coll}").json()
            count = info.get("result", {}).get("points_count", 0)
            print(f"Collection '{coll}': {count} documents")
            if count > max_docs:
                max_docs = count
                collection_name = coll
        except:
            pass

    if not collection_name or max_docs == 0:
        print("⚠️  No documents found in any Qdrant collection")
        return 0.0, 0, 0

    print(f"\nUsing collection: {collection_name} ({max_docs} documents)")

    try:
        # Get total document count
        collection_info = httpx.get(
            f"http://localhost:6333/collections/{collection_name}"
        ).json()
        total_documents = collection_info.get("result", {}).get("points_count", 0)
        print(f"Total documents in {collection_name}: {total_documents}")

        if total_documents == 0:
            print("⚠️  No documents found in Qdrant")
            return 0.0, 0, 0

        # Query for documents WITH language field (any value)
        response = httpx.post(
            f"http://localhost:6333/collections/{collection_name}/points/scroll",
            json={
                "limit": 10000,
                "with_payload": True,
                "filter": {
                    "must": [
                        {
                            "key": "language",
                            "match": {
                                "any": [
                                    "python",
                                    "javascript",
                                    "typescript",
                                    "markdown",
                                    "yaml",
                                    "shell",
                                    "json",
                                    "sql",
                                    "toml",
                                    "dockerfile",
                                    "text",
                                    "html",
                                    "css",
                                    "bash",
                                    "sh",
                                    "xml",
                                    "rust",
                                    "go",
                                ]
                            },
                        }
                    ]
                },
            },
        )

        result = response.json()
        documents_with_language = len(result.get("result", {}).get("points", []))

        coverage = (
            (documents_with_language / total_documents * 100)
            if total_documents > 0
            else 0
        )

        print(f"\nDocuments WITH language field: {documents_with_language}")
        print(
            f"Documents WITHOUT language field: {total_documents - documents_with_language}"
        )
        print(f"Coverage: {coverage:.2f}%")

        # Show language distribution
        language_dist = {}
        for point in result.get("result", {}).get("points", []):
            lang = point.get("payload", {}).get("language", "unknown")
            language_dist[lang] = language_dist.get(lang, 0) + 1

        print("\nLanguage Distribution:")
        for lang, count in sorted(
            language_dist.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {lang}: {count} ({count/documents_with_language*100:.1f}%)")

        return coverage, documents_with_language, total_documents

    except Exception as e:
        print(f"❌ Error checking Qdrant: {e}")
        return 0.0, 0, 0


def check_memgraph_coverage() -> Tuple[float, int, int]:
    """Check language field coverage in Memgraph."""
    print("\n" + "=" * 60)
    print("MEMGRAPH LANGUAGE FIELD COVERAGE")
    print("=" * 60)

    try:
        driver = GraphDatabase.driver("bolt://localhost:7687")
        with driver.session() as session:
            # Count total documents
            result = session.run("MATCH (d:Document) RETURN count(d) as total")
            total = result.single()["total"]
            print(f"Total documents in Memgraph: {total}")

            if total == 0:
                print("⚠️  No documents found in Memgraph")
                return 0.0, 0, 0

            # Count documents with language field
            result = session.run(
                """
                MATCH (d:Document)
                WHERE d.language IS NOT NULL AND d.language <> ''
                RETURN count(d) as with_language
            """
            )
            with_language = result.single()["with_language"]

            coverage = (with_language / total * 100) if total > 0 else 0

            print(f"\nDocuments WITH language field: {with_language}")
            print(f"Documents WITHOUT language field: {total - with_language}")
            print(f"Coverage: {coverage:.2f}%")

            # Show language distribution
            result = session.run(
                """
                MATCH (d:Document)
                WHERE d.language IS NOT NULL AND d.language <> ''
                RETURN d.language as language, count(d) as count
                ORDER BY count DESC
            """
            )

            print("\nLanguage Distribution:")
            for record in result:
                lang = record["language"]
                count = record["count"]
                print(f"  {lang}: {count} ({count/with_language*100:.1f}%)")

            return coverage, with_language, total

    except Exception as e:
        print(f"❌ Error checking Memgraph: {e}")
        return 0.0, 0, 0


def sample_verification(num_samples: int = 10) -> Dict:
    """Verify language field consistency for random sample of files."""
    print("\n" + "=" * 60)
    print(f"SAMPLE VERIFICATION ({num_samples} random files)")
    print("=" * 60)

    # Find the collection with most documents
    collections_to_check = [
        "archon_vectors",
        "code_generation_patterns",
        "archon-intelligence",
    ]
    collection_name = None
    max_docs = 0

    for coll in collections_to_check:
        try:
            info = httpx.get(f"http://localhost:6333/collections/{coll}").json()
            count = info.get("result", {}).get("points_count", 0)
            if count > max_docs:
                max_docs = count
                collection_name = coll
        except:
            pass

    if not collection_name or max_docs == 0:
        print("⚠️  No documents found for sampling")
        return {"consistent": 0, "inconsistent": 0, "samples": []}

    print(f"Using collection: {collection_name}")

    try:
        # Get random file paths from Qdrant
        response = httpx.post(
            f"http://localhost:6333/collections/{collection_name}/points/scroll",
            json={"limit": 100, "with_payload": ["file_path", "language"]},
        )

        result = response.json()
        points = result.get("result", {}).get("points", [])

        if not points:
            print("⚠️  No documents found for sampling")
            return {"consistent": 0, "inconsistent": 0, "samples": []}

        # Random sample
        sample_points = random.sample(points, min(num_samples, len(points)))

        driver = GraphDatabase.driver("bolt://localhost:7687")

        consistent = 0
        inconsistent = 0
        samples = []

        with driver.session() as session:
            for point in sample_points:
                file_path = point.get("payload", {}).get("file_path")
                qdrant_lang = point.get("payload", {}).get("language", "NONE")

                # Query Memgraph for same file
                result = session.run(
                    """
                    MATCH (d:Document {file_path: $file_path})
                    RETURN d.language as language
                """,
                    file_path=file_path,
                )

                record = result.single()
                memgraph_lang = record["language"] if record else "NOT_FOUND"

                is_consistent = qdrant_lang == memgraph_lang

                if is_consistent:
                    consistent += 1
                    status = "✅"
                else:
                    inconsistent += 1
                    status = "❌"

                print(f"{status} {file_path}")
                print(f"   Qdrant: {qdrant_lang}, Memgraph: {memgraph_lang}")

                samples.append(
                    {
                        "file_path": file_path,
                        "qdrant_language": qdrant_lang,
                        "memgraph_language": memgraph_lang,
                        "consistent": is_consistent,
                    }
                )

        print(f"\nConsistency Results:")
        print(
            f"  Consistent: {consistent}/{num_samples} ({consistent/num_samples*100:.1f}%)"
        )
        print(
            f"  Inconsistent: {inconsistent}/{num_samples} ({inconsistent/num_samples*100:.1f}%)"
        )

        return {
            "consistent": consistent,
            "inconsistent": inconsistent,
            "total_samples": num_samples,
            "samples": samples,
        }

    except Exception as e:
        print(f"❌ Error in sample verification: {e}")
        return {"consistent": 0, "inconsistent": 0, "samples": []}


def check_intelligence_logs():
    """Check intelligence service logs for language detection."""
    print("\n" + "=" * 60)
    print("INTELLIGENCE SERVICE LOGS (Language Detection)")
    print("=" * 60)

    import subprocess

    try:
        result = subprocess.run(
            ["docker", "logs", "archon-intelligence", "--tail", "100"],
            capture_output=True,
            text=True,
        )

        # Filter for language-related logs
        logs = result.stdout + result.stderr
        language_logs = [
            line for line in logs.split("\n") if "language" in line.lower()
        ]

        if language_logs:
            print(
                f"Found {len(language_logs)} language-related log entries (last 100 lines):"
            )
            for log in language_logs[-20:]:  # Show last 20
                print(f"  {log}")
        else:
            print("No language-related logs found in last 100 lines")

    except Exception as e:
        print(f"❌ Error checking logs: {e}")


def main():
    """Run complete verification."""
    print("\n" + "=" * 80)
    print("LANGUAGE FIELD COVERAGE VERIFICATION - POST vLLM MIGRATION")
    print("=" * 80)
    print("Baseline: 33.22% (pre-migration)")
    print("Target: >90% coverage")
    print("Acceptable: >60% coverage (significant improvement)")

    # 1. Check Qdrant
    qdrant_coverage, qdrant_with, qdrant_total = check_qdrant_coverage()

    # 2. Check Memgraph
    memgraph_coverage, memgraph_with, memgraph_total = check_memgraph_coverage()

    # 3. Sample verification
    sample_results = sample_verification(10)

    # 4. Check logs
    check_intelligence_logs()

    # Final Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    print(f"\n📊 Coverage Results:")
    print(
        f"  Qdrant:   {qdrant_coverage:.2f}% ({qdrant_with}/{qdrant_total} documents)"
    )
    print(
        f"  Memgraph: {memgraph_coverage:.2f}% ({memgraph_with}/{memgraph_total} documents)"
    )
    print(f"  Baseline: 33.22% (pre-migration)")

    # Coverage delta
    if qdrant_coverage > 0:
        delta = qdrant_coverage - 33.22
        print(f"  Delta:    {delta:+.2f}% {'📈' if delta > 0 else '📉'}")

    # Consistency check
    if qdrant_total > 0 and memgraph_total > 0:
        consistency_diff = abs(qdrant_coverage - memgraph_coverage)
        consistent = consistency_diff <= 5.0
        print(f"\n🔄 Consistency:")
        print(
            f"  Qdrant ↔ Memgraph: {consistency_diff:.2f}% difference {'✅' if consistent else '❌'}"
        )
        print(
            f"  Sample check: {sample_results.get('consistent', 0)}/{sample_results.get('total_samples', 0)} consistent"
        )

    # Success criteria
    print(f"\n✅ Success Criteria:")
    target_met = qdrant_coverage >= 90.0
    improvement_met = qdrant_coverage >= 60.0
    consistency_met = (
        abs(qdrant_coverage - memgraph_coverage) <= 5.0
        if qdrant_total > 0 and memgraph_total > 0
        else False
    )

    print(f"  Target (>90%):      {'✅ MET' if target_met else '❌ NOT MET'}")
    print(f"  Improvement (>60%): {'✅ MET' if improvement_met else '❌ NOT MET'}")
    print(f"  Consistency (<5%):  {'✅ MET' if consistency_met else '❌ NOT MET'}")

    # Overall verdict
    if target_met and consistency_met:
        print(f"\n🎉 EXCELLENT: Target coverage achieved with consistent data!")
    elif improvement_met and consistency_met:
        print(f"\n✅ GOOD: Significant improvement with consistent data!")
    elif improvement_met:
        print(f"\n⚠️  ACCEPTABLE: Improvement achieved but consistency issues detected")
    else:
        print(f"\n❌ NEEDS INVESTIGATION: Coverage below acceptable threshold")
        print(f"\n🔍 Recommendations:")
        print(f"  1. Check if intelligence consumers are running")
        print(f"  2. Verify events are being processed")
        print(f"  3. Check language detection in code")
        print(f"  4. Review enrichment metadata flow")


if __name__ == "__main__":
    main()
