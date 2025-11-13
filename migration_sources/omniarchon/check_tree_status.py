#!/usr/bin/env python3
"""Quick script to check file tree status in Memgraph."""

import os

from neo4j import GraphDatabase

# Connect to Memgraph
driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)


def run_query(query, description):
    """Run a Cypher query and print results."""
    print(f"\n{'='*70}")
    print(f"📊 {description}")
    print(f"{'='*70}")

    with driver.session() as session:
        result = session.run(query)
        records = list(result)

        if not records:
            print("❌ No results found")
            return

        # Print header
        if records:
            keys = records[0].keys()
            header = " | ".join(f"{k:20s}" for k in keys)
            print(header)
            print("-" * len(header))

            # Print rows
            for record in records:
                row = " | ".join(f"{str(record[k]):20s}" for k in keys)
                print(row)

        print(f"\nTotal: {len(records)} rows")


# Query 1: Check PROJECT nodes
run_query(
    """
    MATCH (p:PROJECT)
    RETURN p.name AS project_name,
           p.entity_id AS entity_id,
           p.path AS path
    ORDER BY project_name
    """,
    "PROJECT Nodes",
)

# Query 2: Count files by project_name
run_query(
    """
    MATCH (f:FILE)
    WHERE f.project_name IS NOT NULL
    RETURN f.project_name AS project_name,
           COUNT(*) AS file_count
    ORDER BY file_count DESC
    """,
    "Files by Project Name",
)

# Query 3: Count DIRECTORY nodes by project
run_query(
    """
    MATCH (d:DIRECTORY)
    OPTIONAL MATCH (p:PROJECT)-[:CONTAINS*]->(d)
    RETURN COALESCE(p.name, 'ORPHANED') AS project,
           COUNT(DISTINCT d) AS dir_count
    ORDER BY dir_count DESC
    """,
    "Directory Nodes by Project",
)

# Query 4: Count CONTAINS relationships by type
run_query(
    """
    MATCH (source)-[r:CONTAINS]->(target)
    RETURN labels(source)[0] AS source_type,
           labels(target)[0] AS target_type,
           COUNT(*) AS relationship_count
    ORDER BY relationship_count DESC
    """,
    "CONTAINS Relationships by Type",
)

# Query 5: List all PROJECT nodes
run_query(
    """
    MATCH (p:PROJECT)
    RETURN p.name AS project_name,
           p.entity_id AS entity_id
    ORDER BY project_name
    """,
    "All PROJECT Nodes in Database",
)

# Query 6: Count files connected to tree for each project
run_query(
    """
    MATCH (p:PROJECT)-[:CONTAINS*]->(f:FILE)
    RETURN p.name AS project,
           COUNT(DISTINCT f) AS files_in_tree
    ORDER BY files_in_tree DESC
    """,
    "Files Connected to Tree by Project",
)

# Query 7: Sample files from each project (first 3)
run_query(
    """
    MATCH (f:FILE)
    WHERE f.project_name IN ['omniclaude', 'omnibase_core', 'omninode_bridge']
    RETURN f.project_name AS project,
           f.path AS sample_path
    ORDER BY project, f.path
    LIMIT 9
    """,
    "Sample File Paths from Non-Tree Projects",
)

driver.close()
print("\n" + "=" * 70)
print("✅ Analysis complete")
print("=" * 70)
