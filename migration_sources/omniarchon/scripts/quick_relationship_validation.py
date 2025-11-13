#!/usr/bin/env python3
"""
Quick Relationship Validation

Validates that relationships in Memgraph are using hash-based entity IDs.
Expected format: blake3:<24-character-hash>
"""
import sys

from neo4j import GraphDatabase

# Memgraph connection
MEMGRAPH_URI = "bolt://localhost:7687"


def validate_relationships():
    """Check relationships for hash-based entity IDs"""
    driver = GraphDatabase.driver(MEMGRAPH_URI)

    print("=== Relationship Validation ===\n")

    with driver.session() as session:
        # Count total FILE nodes
        result = session.run("MATCH (n:FILE) RETURN count(n) as count")
        total_files = result.single()["count"]
        print(f"Total FILE nodes: {total_files}")

        # Count nodes with blake3 entity_id (format: blake3:<24-char-hash>)
        result = session.run(
            """
            MATCH (n:FILE)
            WHERE n.entity_id STARTS WITH 'blake3:'
            RETURN count(n) as count
        """
        )
        hash_nodes = result.single()["count"]
        print(f"FILE nodes with blake3 entity_id: {hash_nodes}")

        # Count relationships
        result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
        total_rels = result.single()["count"]
        print(f"\nTotal relationships: {total_rels}")

        # Sample relationships to check entity_id format
        print("\nSample relationships (first 10):")
        result = session.run(
            """
            MATCH (a:FILE)-[r]->(b:FILE)
            RETURN a.entity_id as from_id, type(r) as rel_type, b.entity_id as to_id
            LIMIT 10
        """
        )

        valid_count = 0
        invalid_count = 0

        for record in result:
            from_id = record["from_id"]
            to_id = record["to_id"]
            rel_type = record["rel_type"]

            is_valid = (
                from_id
                and from_id.startswith("blake3:")
                and to_id
                and to_id.startswith("blake3:")
            )

            status = "✅" if is_valid else "❌"
            # Display full entity_id (blake3: + 24-char hash = 31 chars total)
            print(f"{status} {rel_type}: {from_id[:35]}... -> {to_id[:35]}...")

            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1

        # Count relationships with blake3 endpoints
        result = session.run(
            """
            MATCH (a:FILE)-[r]->(b:FILE)
            WHERE a.entity_id STARTS WITH 'blake3:' AND b.entity_id STARTS WITH 'blake3:'
            RETURN count(r) as count
        """
        )
        valid_rels = result.single()["count"]

        print(f"\n=== Summary ===")
        print(
            f"FILE nodes with blake3 IDs: {hash_nodes}/{total_files} ({hash_nodes/total_files*100:.1f}%)"
        )
        print(
            f"Relationships with blake3 endpoints: {valid_rels}/{total_rels} ({valid_rels/total_rels*100:.1f}% if total_rels else 0)"
        )

        if hash_nodes == total_files and (total_rels == 0 or valid_rels == total_rels):
            print(
                "\n✅ SUCCESS: All nodes and relationships use hash-based entity IDs!"
            )
            return 0
        elif total_rels == 0:
            print(
                "\n⚠️  WARNING: No relationships found yet (processing may still be ongoing)"
            )
            return 1
        else:
            print(
                f"\n❌ FAILURE: Found {total_files - hash_nodes} nodes without blake3 IDs"
            )
            print(
                f"❌ FAILURE: Found {total_rels - valid_rels} relationships without blake3 endpoints"
            )
            return 2

    driver.close()


if __name__ == "__main__":
    sys.exit(validate_relationships())
