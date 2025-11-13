#!/usr/bin/env python3
"""Verify language field and directory tree in Memgraph."""

import sys

from neo4j import GraphDatabase

MEMGRAPH_URI = "bolt://localhost:7687"


def run_query(driver, query, description):
    """Run a Cypher query and print results."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print("=" * 60)

    with driver.session() as session:
        result = session.run(query)
        records = list(result)

        if not records:
            print("No results returned")
            return []

        # Print column headers
        if records:
            headers = list(records[0].keys())
            print(" | ".join(headers))
            print("-" * 60)

            # Print rows
            for record in records:
                values = [str(record[key]) for key in headers]
                print(" | ".join(values))

        return records


def main():
    """Main verification function."""
    driver = GraphDatabase.driver(MEMGRAPH_URI)

    try:
        # Test connection
        with driver.session() as session:
            session.run("RETURN 1")
        print("✅ Connected to Memgraph")

        # Total FILE nodes
        run_query(
            driver, "MATCH (f:FILE) RETURN count(f) AS total_files", "Total FILE Nodes"
        )

        # Language distribution
        run_query(
            driver,
            "MATCH (f:FILE) RETURN f.language AS language, count(*) AS count ORDER BY count DESC LIMIT 10",
            "Top 10 Languages by File Count",
        )

        # Known vs unknown languages
        known_result = run_query(
            driver,
            "MATCH (f:FILE) WHERE f.language <> 'unknown' AND f.language IS NOT NULL RETURN count(*) AS known_count",
            "Files with Known Language",
        )

        unknown_result = run_query(
            driver,
            "MATCH (f:FILE) WHERE f.language = 'unknown' OR f.language IS NULL RETURN count(*) AS unknown_count",
            "Files with Unknown Language",
        )

        # Python files
        run_query(
            driver,
            "MATCH (f:FILE {language: 'python'}) RETURN count(*) AS python_count",
            "Python Files Count",
        )

        # Sample files with language
        run_query(
            driver,
            "MATCH (f:FILE) WHERE f.language <> 'unknown' AND f.language IS NOT NULL RETURN f.path, f.language LIMIT 15",
            "Sample Files with Language Field",
        )

        # Calculate percentage
        if known_result and unknown_result:
            known = known_result[0]["known_count"]
            unknown = unknown_result[0]["unknown_count"]
            total = known + unknown
            if total > 0:
                percentage = (known / total) * 100
                print(f"\n{'='*60}")
                print(
                    f"Language Field Coverage: {known}/{total} files ({percentage:.1f}%)"
                )
                print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
