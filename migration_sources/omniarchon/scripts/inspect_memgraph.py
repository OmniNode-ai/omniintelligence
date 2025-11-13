#!/usr/bin/env python3
"""
Comprehensive Memgraph Knowledge Graph Inspection

Connects to Memgraph and retrieves:
- Node counts by label
- Relationship counts by type
- Sample nodes with full properties
- Data quality assessment
"""

import json
import sys
from datetime import datetime, timedelta

from neo4j import GraphDatabase

MEMGRAPH_URI = "bolt://localhost:7687"


def format_value(value):
    """Format value for display"""
    from neo4j.time import DateTime

    if isinstance(value, DateTime):
        return value.iso_format()
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, indent=2, default=str)
        except:
            return str(value)
    return str(value)


def main():
    print("=" * 80)
    print("MEMGRAPH KNOWLEDGE GRAPH INSPECTION")
    print("=" * 80)
    print(f"\nConnecting to: {MEMGRAPH_URI}\n")

    driver = GraphDatabase.driver(MEMGRAPH_URI, auth=None)

    try:
        with driver.session() as session:
            # 1. TOTAL NODE COUNT
            print("\n" + "=" * 80)
            print("1. TOTAL NODE COUNT")
            print("=" * 80)
            result = session.run("MATCH (n) RETURN count(n) as total_nodes")
            record = result.single()
            total_nodes = record["total_nodes"]
            print(f"Total nodes: {total_nodes}")

            # 2. TOTAL RELATIONSHIP COUNT
            print("\n" + "=" * 80)
            print("2. TOTAL RELATIONSHIP COUNT")
            print("=" * 80)
            result = session.run(
                "MATCH ()-[r]->() RETURN count(r) as total_relationships"
            )
            record = result.single()
            total_rels = record["total_relationships"]
            print(f"Total relationships: {total_rels}")

            # 3. NODE LABELS
            print("\n" + "=" * 80)
            print("3. NODE LABELS PRESENT")
            print("=" * 80)
            try:
                result = session.run(
                    "CALL mg.get_all_labels() YIELD label RETURN label"
                )
                labels = [record["label"] for record in result]
                print(f"Labels found: {labels}")
            except Exception as e:
                print(f"Could not get labels via procedure: {e}")
                print("Trying alternative method...")
                result = session.run(
                    """
                    MATCH (n)
                    WITH DISTINCT labels(n) as node_labels
                    UNWIND node_labels as label
                    RETURN DISTINCT label
                """
                )
                labels = [record["label"] for record in result]
                print(f"Labels found: {labels}")

            # 4. NODE COUNTS BY LABEL
            print("\n" + "=" * 80)
            print("4. NODE COUNTS BY LABEL")
            print("=" * 80)
            for label in labels:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                count = result.single()["count"]
                print(f"  {label}: {count} nodes")

            # 5. RELATIONSHIP TYPES
            print("\n" + "=" * 80)
            print("5. RELATIONSHIP TYPES PRESENT")
            print("=" * 80)
            try:
                result = session.run(
                    "CALL mg.get_all_edge_types() YIELD edge_type RETURN edge_type"
                )
                edge_types = [record["edge_type"] for record in result]
                print(f"Edge types found: {edge_types}")
            except Exception as e:
                print(f"Could not get edge types via procedure: {e}")
                print("Trying alternative method...")
                result = session.run(
                    """
                    MATCH ()-[r]->()
                    RETURN DISTINCT type(r) as relationship_type
                """
                )
                edge_types = [record["relationship_type"] for record in result]
                print(f"Edge types found: {edge_types}")

            # 6. RELATIONSHIP COUNTS BY TYPE
            print("\n" + "=" * 80)
            print("6. RELATIONSHIP COUNTS BY TYPE")
            print("=" * 80)
            for edge_type in edge_types:
                result = session.run(
                    f"MATCH ()-[r:{edge_type}]->() RETURN count(r) as count"
                )
                count = result.single()["count"]
                print(f"  {edge_type}: {count} relationships")

            # 7. SEARCH FOR TEST PROJECT DATA
            print("\n" + "=" * 80)
            print("7. TEST PROJECT DATA")
            print("=" * 80)
            result = session.run(
                """
                MATCH (n)
                WHERE n.project_name IS NOT NULL
                  AND (n.project_name CONTAINS 'test' OR n.project_name CONTAINS 'optimized')
                RETURN n.project_name as project_name, count(*) as count
            """
            )
            test_projects = list(result)
            if test_projects:
                print("Projects matching 'test' or 'optimized':")
                for record in test_projects:
                    print(f"  {record['project_name']}: {record['count']} nodes")
            else:
                print("No test/optimized projects found")

            # 8. RECENT DOCUMENTS (last 3 days)
            print("\n" + "=" * 80)
            print("8. RECENT DOCUMENTS (LAST 3 DAYS)")
            print("=" * 80)
            three_days_ago = datetime.now() - timedelta(days=3)
            timestamp = three_days_ago.isoformat()
            result = session.run(
                """
                MATCH (n)
                WHERE n.indexed_at IS NOT NULL
                  AND n.indexed_at > $timestamp
                RETURN count(*) as recent_count
            """,
                timestamp=timestamp,
            )
            recent_count = result.single()["recent_count"]
            print(f"Documents indexed in last 3 days: {recent_count}")

            # 9. SAMPLE DOCUMENT NODES WITH FULL PROPERTIES
            print("\n" + "=" * 80)
            print("9. SAMPLE DOCUMENT NODES (FULL PROPERTIES)")
            print("=" * 80)

            # Check for both Document and document labels
            doc_label = None
            if "Document" in labels:
                doc_label = "Document"
            elif "document" in labels:
                doc_label = "document"

            if doc_label:
                print(f"Found document label: '{doc_label}'")
                result = session.run(
                    f"""
                    MATCH (n:{doc_label})
                    RETURN n
                    LIMIT 3
                """
                )

                sample_docs = list(result)
                if sample_docs:
                    for idx, record in enumerate(sample_docs, 1):
                        node = record["n"]
                        print(f"\n--- {doc_label} {idx} ---")
                        print(f"Labels: {list(node.labels)}")
                        print("Properties:")
                        for key, value in dict(node).items():
                            print(f"  {key}: {format_value(value)}")
                else:
                    print(f"No {doc_label} nodes found")
            else:
                print(
                    "No 'Document' or 'document' label found. Showing sample from first available label..."
                )
                if labels:
                    first_label = labels[0]
                    result = session.run(
                        f"""
                        MATCH (n:{first_label})
                        RETURN n
                        LIMIT 3
                    """
                    )

                    sample_nodes = list(result)
                    for idx, record in enumerate(sample_nodes, 1):
                        node = record["n"]
                        print(f"\n--- {first_label} {idx} ---")
                        print(f"Labels: {list(node.labels)}")
                        print("Properties:")
                        for key, value in dict(node).items():
                            print(f"  {key}: {format_value(value)}")

            # 10. PROPERTY ANALYSIS FOR DOCUMENT NODES
            print("\n" + "=" * 80)
            print("10. DOCUMENT NODE PROPERTY ANALYSIS")
            print("=" * 80)

            if doc_label:
                result = session.run(
                    f"""
                    MATCH (n:{doc_label})
                    WITH keys(n) as property_keys
                    UNWIND property_keys as property_key
                    RETURN DISTINCT property_key, count(*) as node_count
                    ORDER BY node_count DESC
                """
                )

                properties = list(result)
                if properties:
                    print(f"Properties found on {doc_label} nodes:")
                    for record in properties:
                        print(
                            f"  {record['property_key']}: present on {record['node_count']} nodes"
                        )

                    # Check for specific properties
                    print("\nChecking for key properties:")
                    key_props = [
                        "content_hash",
                        "blake3_hash",
                        "file_path",
                        "content",
                        "project_name",
                        "indexed_at",
                        "language",
                    ]
                    for prop in key_props:
                        result = session.run(
                            f"""
                            MATCH (n:{doc_label})
                            WHERE n.{prop} IS NOT NULL
                            RETURN count(*) as count
                        """
                        )
                        count = result.single()["count"]
                        total_result = session.run(
                            f"MATCH (n:{doc_label}) RETURN count(*) as total"
                        )
                        total = total_result.single()["total"]
                        percentage = (count / total * 100) if total > 0 else 0
                        print(f"  {prop}: {count}/{total} ({percentage:.1f}%)")
                else:
                    print("Could not analyze properties")
            else:
                print("No Document or document label found")

            # 11. SAMPLE RELATIONSHIPS
            print("\n" + "=" * 80)
            print("11. SAMPLE RELATIONSHIPS")
            print("=" * 80)

            if total_rels > 0:
                result = session.run(
                    """
                    MATCH (a)-[r]->(b)
                    RETURN labels(a) as source_labels,
                           type(r) as relationship_type,
                           properties(r) as relationship_props,
                           labels(b) as target_labels
                    LIMIT 5
                """
                )

                rels = list(result)
                if rels:
                    for idx, record in enumerate(rels, 1):
                        print(f"\n--- Relationship {idx} ---")
                        print(f"Source: {record['source_labels']}")
                        print(f"Type: {record['relationship_type']}")
                        # Convert properties to JSON-safe format
                        props = record["relationship_props"]
                        props_formatted = {k: format_value(v) for k, v in props.items()}
                        print(f"Properties: {json.dumps(props_formatted, indent=2)}")
                        print(f"Target: {record['target_labels']}")
                else:
                    print("No relationships found")
            else:
                print("No relationships in graph")

            # 12. DATA QUALITY ASSESSMENT
            print("\n" + "=" * 80)
            print("12. DATA QUALITY ASSESSMENT")
            print("=" * 80)

            issues = []

            if total_nodes == 0:
                issues.append("❌ CRITICAL: No nodes in graph")
            else:
                print(f"✅ Graph contains {total_nodes} nodes")

            if total_rels == 0:
                issues.append("⚠️  WARNING: No relationships in graph (isolated nodes)")
            else:
                print(f"✅ Graph contains {total_rels} relationships")

            if not doc_label:
                issues.append("❌ CRITICAL: No 'Document' or 'document' label found")
            else:
                print(f"✅ Document label exists: '{doc_label}'")

            if doc_label:
                # Check for content_hash
                result = session.run(
                    f"""
                    MATCH (n:{doc_label})
                    WHERE n.content_hash IS NOT NULL OR n.blake3_hash IS NOT NULL
                    RETURN count(*) as count
                """
                )
                hash_count = result.single()["count"]

                result = session.run(f"MATCH (n:{doc_label}) RETURN count(*) as total")
                total_docs = result.single()["total"]

                if hash_count == 0:
                    issues.append(
                        f"⚠️  WARNING: No content hashes found on {doc_label} nodes"
                    )
                elif hash_count < total_docs:
                    issues.append(
                        f"⚠️  WARNING: Only {hash_count}/{total_docs} documents have content hashes"
                    )
                else:
                    print(f"✅ All {total_docs} documents have content hashes")

            if issues:
                print("\n\nISSUES FOUND:")
                for issue in issues:
                    print(f"  {issue}")
            else:
                print("\n✅ No major issues detected")

            # 13. SUMMARY
            print("\n" + "=" * 80)
            print("13. SUMMARY")
            print("=" * 80)
            print(f"Total Nodes: {total_nodes}")
            print(f"Total Relationships: {total_rels}")
            print(f"Labels: {len(labels)}")
            print(f"Relationship Types: {len(edge_types)}")
            print(
                f"\nGraph Status: {'HEALTHY' if total_nodes > 0 and not any('CRITICAL' in i for i in issues) else 'NEEDS ATTENTION'}"
            )

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        driver.close()

    print("\n" + "=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
