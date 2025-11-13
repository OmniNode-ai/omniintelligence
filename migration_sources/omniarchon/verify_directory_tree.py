#!/usr/bin/env python3
"""Verify directory tree structure in Memgraph."""

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

        # PROJECT nodes
        run_query(
            driver,
            "MATCH (p:PROJECT) RETURN p.name AS name, p.path AS path",
            "PROJECT Nodes",
        )

        # DIRECTORY count
        run_query(
            driver,
            "MATCH (d:DIRECTORY) RETURN count(d) AS directory_count",
            "Total DIRECTORY Nodes",
        )

        # Files in tree via DIRECTORY
        run_query(
            driver,
            "MATCH (d:DIRECTORY)-[:CONTAINS]->(f:FILE) RETURN count(DISTINCT f) AS files_via_directories",
            "Files Linked via DIRECTORY",
        )

        # Files directly under PROJECT
        run_query(
            driver,
            "MATCH (p:PROJECT)-[:CONTAINS]->(f:FILE) RETURN count(f) AS files_at_root",
            "Files Directly Under PROJECT",
        )

        # Total files in tree (1-2 levels deep)
        run_query(
            driver,
            "MATCH (p:PROJECT)-[:CONTAINS*1..2]->(f:FILE) RETURN count(DISTINCT f) AS total_files_in_tree",
            "Total Files in Tree (via PROJECT)",
        )

        # Orphan files (not linked to any DIRECTORY or PROJECT)
        run_query(
            driver,
            "MATCH (f:FILE) OPTIONAL MATCH (n)-[:CONTAINS]->(f) WITH f, n WHERE n IS NULL RETURN count(f) AS orphan_count",
            "Orphan Files (not in tree)",
        )

        # Sample directory paths
        run_query(
            driver,
            "MATCH (d:DIRECTORY) RETURN d.path LIMIT 15",
            "Sample DIRECTORY Paths",
        )

        # Sample tree structure (PROJECT -> DIRECTORY -> FILE)
        run_query(
            driver,
            """
            MATCH (p:PROJECT)-[:CONTAINS]->(d:DIRECTORY)-[:CONTAINS]->(f:FILE)
            RETURN p.name AS project, d.path AS directory, f.path AS file
            LIMIT 10
            """,
            "Sample Tree Structure (PROJECT → DIRECTORY → FILE)",
        )

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
