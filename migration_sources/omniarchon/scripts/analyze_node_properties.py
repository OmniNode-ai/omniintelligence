#!/usr/bin/env python3
"""
Detailed analysis of node properties and schema structure
Focus on understanding PLACEHOLDER vs REAL nodes
"""

import json

from neo4j import GraphDatabase

MEMGRAPH_URI = "bolt://localhost:7687"


def print_node_details(node, title):
    """Pretty print node details"""
    print(f"\n{title}")
    print("=" * 60)
    print(f"Labels: {list(node.labels)}")
    props = dict(node)
    print(f"Properties ({len(props)} total):")
    for key, value in sorted(props.items()):
        if isinstance(value, str) and len(value) > 100:
            print(f"  {key:20s}: {value[:100]}...")
        elif isinstance(value, dict):
            print(f"  {key:20s}: {json.dumps(value, indent=2)[:200]}...")
        else:
            print(f"  {key:20s}: {value}")


def main():
    print("=" * 80)
    print("DETAILED NODE PROPERTIES ANALYSIS")
    print("=" * 80)

    driver = GraphDatabase.driver(MEMGRAPH_URI, auth=None)

    try:
        with driver.session() as session:
            # ================================================================
            # 1. REAL FILE NODE (file_* pattern)
            # ================================================================
            print("\n" + "=" * 80)
            print("1. REAL FILE NODE ANALYSIS (file_* pattern)")
            print("=" * 80)

            result = session.run(
                """
                MATCH (f:FILE)
                WHERE f.entity_id STARTS WITH 'file_'
                RETURN f
                LIMIT 3
            """
            )

            for idx, record in enumerate(result, 1):
                node = record["f"]
                print_node_details(node, f"REAL FILE NODE #{idx}")

            # ================================================================
            # 2. PLACEHOLDER FILE NODES (colon pattern)
            # ================================================================
            print("\n" + "=" * 80)
            print("2. PLACEHOLDER FILE NODES (colon pattern)")
            print("=" * 80)

            # Type 1: Import placeholders (file:project:module)
            result = session.run(
                """
                MATCH (f:FILE)
                WHERE f.entity_id CONTAINS ':'
                  AND NOT f.entity_id CONTAINS 'archon://'
                RETURN f
                LIMIT 5
            """
            )

            import_nodes = list(result)
            print(f"\nFound {len(import_nodes)} import placeholder nodes")
            for idx, record in enumerate(import_nodes, 1):
                node = record["f"]
                print_node_details(node, f"IMPORT PLACEHOLDER #{idx}")

            # Type 2: Path placeholders (file:project:archon://...)
            result = session.run(
                """
                MATCH (f:FILE)
                WHERE f.entity_id CONTAINS 'archon://'
                RETURN f
                LIMIT 3
            """
            )

            path_nodes = list(result)
            print(f"\nFound {len(path_nodes)} path placeholder nodes")
            for idx, record in enumerate(path_nodes, 1):
                node = record["f"]
                print_node_details(node, f"PATH PLACEHOLDER #{idx}")

            # ================================================================
            # 3. ENTITY NODES
            # ================================================================
            print("\n" + "=" * 80)
            print("3. ENTITY NODE ANALYSIS")
            print("=" * 80)

            result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.entity_id STARTS WITH 'entity_'
                RETURN e
                LIMIT 3
            """
            )

            for idx, record in enumerate(result, 1):
                node = record["e"]
                print_node_details(node, f"ENTITY NODE #{idx}")

            # Special case: Entity nodes used as simple names
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE NOT e.entity_id STARTS WITH 'entity_'
                RETURN e
                LIMIT 5
            """
            )

            simple_entities = list(result)
            if simple_entities:
                print(f"\nFound {len(simple_entities)} simple name Entity nodes")
                for idx, record in enumerate(simple_entities[:3], 1):
                    node = record["e"]
                    print_node_details(node, f"SIMPLE ENTITY #{idx}")

            # ================================================================
            # 4. RELATIONSHIP ANALYSIS WITH FULL CONTEXT
            # ================================================================
            print("\n" + "=" * 80)
            print("4. RELATIONSHIP CONTEXT ANALYSIS")
            print("=" * 80)

            # Entity -> Entity relationships
            result = session.run(
                """
                MATCH (source:Entity)-[r:RELATES]->(target:Entity)
                RETURN source, r, target
                LIMIT 3
            """
            )

            for idx, record in enumerate(result, 1):
                source = record["source"]
                rel = record["r"]
                target = record["target"]

                print(f"\n{'=' * 60}")
                print(f"RELATIONSHIP #{idx}: Entity -> Entity")
                print(f"{'=' * 60}")

                print_node_details(source, "SOURCE Entity")
                print(f"\nRELATIONSHIP: {type(rel).__name__}")
                rel_props = dict(rel)
                for key, value in sorted(rel_props.items()):
                    if isinstance(value, str) and len(value) > 100:
                        print(f"  {key:20s}: {value[:100]}...")
                    else:
                        print(f"  {key:20s}: {value}")

                print_node_details(target, "TARGET Entity")

            # Entity -> FILE relationships
            result = session.run(
                """
                MATCH (source:Entity)-[r:IMPORTS]->(target:FILE)
                RETURN source, r, target
                LIMIT 3
            """
            )

            import_rels = list(result)
            if import_rels:
                for idx, record in enumerate(import_rels, 1):
                    source = record["source"]
                    rel = record["r"]
                    target = record["target"]

                    print(f"\n{'=' * 60}")
                    print(f"IMPORT RELATIONSHIP #{idx}: Entity -> FILE")
                    print(f"{'=' * 60}")

                    print_node_details(source, "SOURCE Entity")
                    print(f"\nRELATIONSHIP: IMPORTS")
                    rel_props = dict(rel)
                    for key, value in sorted(rel_props.items()):
                        print(f"  {key:20s}: {value}")

                    print_node_details(target, "TARGET FILE")
            else:
                print("\n⚠️  No Entity->FILE IMPORTS relationships found")

            # FILE -> FILE relationships (if any)
            result = session.run(
                """
                MATCH (source:FILE)-[r]-(target:FILE)
                RETURN source, type(r) as rel_type, target
                LIMIT 3
            """
            )

            file_rels = list(result)
            if file_rels:
                print(f"\nFound {len(file_rels)} FILE<->FILE relationships")
                for idx, record in enumerate(file_rels, 1):
                    print(
                        f"\n  {idx}. {record['source']['entity_id']} -{record['rel_type']}-> {record['target']['entity_id']}"
                    )
            else:
                print("\n⚠️  No FILE<->FILE relationships found")

            # ================================================================
            # 5. PROPERTY COMPLETENESS ANALYSIS
            # ================================================================
            print("\n" + "=" * 80)
            print("5. PROPERTY COMPLETENESS COMPARISON")
            print("=" * 80)

            # Compare property counts
            result = session.run(
                """
                MATCH (f:FILE)
                WHERE f.entity_id STARTS WITH 'file_'
                WITH f, size(keys(f)) as prop_count
                RETURN AVG(prop_count) as avg_props, MIN(prop_count) as min_props, MAX(prop_count) as max_props
            """
            )

            record = result.single()
            print(f"\nREAL FILE nodes (file_* pattern):")
            print(f"  Average properties: {record['avg_props']:.1f}")
            print(f"  Min properties: {record['min_props']}")
            print(f"  Max properties: {record['max_props']}")

            result = session.run(
                """
                MATCH (f:FILE)
                WHERE f.entity_id CONTAINS ':'
                WITH f, size(keys(f)) as prop_count
                RETURN AVG(prop_count) as avg_props, MIN(prop_count) as min_props, MAX(prop_count) as max_props
            """
            )

            record = result.single()
            print(f"\nPLACEHOLDER FILE nodes (colon pattern):")
            print(f"  Average properties: {record['avg_props']:.1f}")
            print(f"  Min properties: {record['min_props']}")
            print(f"  Max properties: {record['max_props']}")

            # ================================================================
            # 6. IDENTIFY ORPHANED NODES
            # ================================================================
            print("\n" + "=" * 80)
            print("6. ORPHANED NODE DETECTION")
            print("=" * 80)

            # FILE nodes with no relationships
            result = session.run(
                """
                MATCH (f:FILE)
                WHERE NOT EXISTS((f)-[]-())
                WITH f.entity_id as entity_id, f.entity_id STARTS WITH 'file_' as is_real
                RETURN is_real, count(*) as count
            """
            )

            for record in result:
                node_type = "REAL" if record["is_real"] else "PLACEHOLDER"
                print(
                    f"  {node_type} FILE nodes with no relationships: {record['count']}"
                )

            # Entity nodes with no relationships
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE NOT EXISTS((e)-[]-())
                RETURN count(*) as count
            """
            )

            orphan_entities = result.single()["count"]
            print(f"  Entity nodes with no relationships: {orphan_entities}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        driver.close()

    print("\n" + "=" * 80)
    print("DETAILED ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
