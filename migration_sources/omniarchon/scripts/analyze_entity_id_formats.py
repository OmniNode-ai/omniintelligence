#!/usr/bin/env python3
"""
Analyze entity_id formats in Memgraph database
Focuses on understanding actual entity_id patterns used across nodes and relationships
"""

import json
from collections import Counter, defaultdict

from neo4j import GraphDatabase

MEMGRAPH_URI = "bolt://localhost:7687"


def main():
    print("=" * 80)
    print("MEMGRAPH ENTITY_ID FORMAT ANALYSIS")
    print("=" * 80)
    print(f"\nConnecting to: {MEMGRAPH_URI}\n")

    driver = GraphDatabase.driver(MEMGRAPH_URI, auth=None)

    try:
        with driver.session() as session:
            # ================================================================
            # 1. FILE NODE ENTITY_ID ANALYSIS
            # ================================================================
            print("\n" + "=" * 80)
            print("1. FILE NODE ENTITY_ID FORMATS")
            print("=" * 80)

            # Get sample FILE entity_ids
            result = session.run(
                """
                MATCH (f:FILE)
                RETURN f.entity_id as entity_id,
                       f.path as path,
                       f.project_name as project_name,
                       f.name as name
                LIMIT 50
            """
            )

            file_entity_ids = []
            print("\nSample FILE entity_ids:")
            for idx, record in enumerate(result, 1):
                entity_id = record["entity_id"]
                file_entity_ids.append(entity_id)
                if idx <= 10:  # Show first 10
                    print(
                        f"  {idx:2d}. {entity_id:30s} | {record['name']:40s} | {record['project_name']}"
                    )

            # Analyze patterns
            print(f"\nTotal FILE nodes sampled: {len(file_entity_ids)}")

            # Check for different patterns
            file_prefix = sum(1 for eid in file_entity_ids if eid.startswith("file_"))
            has_colon = sum(1 for eid in file_entity_ids if ":" in eid)

            print(f"  - Starts with 'file_': {file_prefix}")
            print(f"  - Contains ':' (colon): {has_colon}")

            # ================================================================
            # 2. ENTITY NODE ENTITY_ID ANALYSIS
            # ================================================================
            print("\n" + "=" * 80)
            print("2. ENTITY NODE ENTITY_ID FORMATS")
            print("=" * 80)

            result = session.run(
                """
                MATCH (e:Entity)
                RETURN e.entity_id as entity_id,
                       e.entity_type as entity_type,
                       e.name as name
                LIMIT 50
            """
            )

            entity_entity_ids = []
            print("\nSample Entity entity_ids:")
            for idx, record in enumerate(result, 1):
                entity_id = record["entity_id"]
                entity_entity_ids.append(entity_id)
                if idx <= 10:  # Show first 10
                    entity_type = record.get("entity_type", "N/A")
                    name = record.get("name", "N/A")
                    print(
                        f"  {idx:2d}. {entity_id:50s} | Type: {entity_type:15s} | Name: {name}"
                    )

            print(f"\nTotal Entity nodes sampled: {len(entity_entity_ids)}")

            # Analyze Entity entity_id patterns
            entity_prefixes = defaultdict(int)
            for eid in entity_entity_ids:
                if ":" in eid:
                    prefix = eid.split(":")[0]
                    entity_prefixes[prefix] += 1

            if entity_prefixes:
                print("\nEntity entity_id prefix patterns (colon-separated):")
                for prefix, count in sorted(
                    entity_prefixes.items(), key=lambda x: x[1], reverse=True
                ):
                    print(f"  {prefix}: {count} nodes")
            else:
                print("\n⚠️  No colon-separated entity_ids found in Entity nodes")

            # ================================================================
            # 3. RELATIONSHIP SOURCE/TARGET ENTITY_ID ANALYSIS
            # ================================================================
            print("\n" + "=" * 80)
            print("3. RELATIONSHIP ENTITY_ID REFERENCES")
            print("=" * 80)

            result = session.run(
                """
                MATCH (source)-[r]->(target)
                RETURN labels(source) as source_labels,
                       source.entity_id as source_entity_id,
                       type(r) as rel_type,
                       labels(target) as target_labels,
                       target.entity_id as target_entity_id
                LIMIT 50
            """
            )

            rel_data = []
            print("\nSample relationships with entity_ids:")
            for idx, record in enumerate(result, 1):
                rel_data.append(record)
                if idx <= 10:
                    print(f"\n  --- Relationship {idx} ---")
                    print(
                        f"  Source: {record['source_labels']} | {record['source_entity_id']}"
                    )
                    print(f"  Type:   {record['rel_type']}")
                    print(
                        f"  Target: {record['target_labels']} | {record['target_entity_id']}"
                    )

            # Analyze relationship patterns
            print(f"\nTotal relationships sampled: {len(rel_data)}")

            source_by_label = defaultdict(set)
            target_by_label = defaultdict(set)

            for record in rel_data:
                source_label = (
                    record["source_labels"][0] if record["source_labels"] else "UNKNOWN"
                )
                target_label = (
                    record["target_labels"][0] if record["target_labels"] else "UNKNOWN"
                )

                source_by_label[source_label].add(record["source_entity_id"])
                target_by_label[target_label].add(record["target_entity_id"])

            print("\nSource entity_id patterns by label:")
            for label, entity_ids in source_by_label.items():
                print(f"  {label}: {len(entity_ids)} unique entity_ids")
                sample = list(entity_ids)[:3]
                for eid in sample:
                    print(f"    - {eid}")

            print("\nTarget entity_id patterns by label:")
            for label, entity_ids in target_by_label.items():
                print(f"  {label}: {len(entity_ids)} unique entity_ids")
                sample = list(entity_ids)[:3]
                for eid in sample:
                    print(f"    - {eid}")

            # ================================================================
            # 4. FULL ENTITY_ID DISTRIBUTION
            # ================================================================
            print("\n" + "=" * 80)
            print("4. COMPLETE ENTITY_ID PATTERN DISTRIBUTION")
            print("=" * 80)

            result = session.run(
                """
                MATCH (n)
                WHERE n.entity_id IS NOT NULL
                RETURN n.entity_id as entity_id, labels(n) as labels
            """
            )

            all_entity_ids = []
            label_counts = defaultdict(int)

            for record in result:
                entity_id = record["entity_id"]
                label = record["labels"][0] if record["labels"] else "UNKNOWN"
                all_entity_ids.append((entity_id, label))
                label_counts[label] += 1

            print(f"\nTotal nodes with entity_id: {len(all_entity_ids)}")
            print("\nNode counts by label:")
            for label, count in sorted(
                label_counts.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {label}: {count} nodes")

            # Pattern analysis
            print("\n" + "=" * 80)
            print("5. ENTITY_ID FORMAT PATTERNS")
            print("=" * 80)

            # Categorize by pattern
            patterns = {
                "file_*": [],  # file_ prefix with hash
                "project:type:hash": [],  # project:type:hash format
                "other_colon": [],  # other colon-separated
                "other": [],  # other formats
            }

            for entity_id, label in all_entity_ids:
                if entity_id.startswith("file_"):
                    patterns["file_*"].append((entity_id, label))
                elif ":" in entity_id:
                    parts = entity_id.split(":")
                    if len(parts) == 3:
                        patterns["project:type:hash"].append((entity_id, label))
                    else:
                        patterns["other_colon"].append((entity_id, label))
                else:
                    patterns["other"].append((entity_id, label))

            print("\nEntity_id pattern distribution:")
            for pattern_name, items in patterns.items():
                if items:
                    print(f"\n{pattern_name}: {len(items)} nodes")
                    # Show samples
                    samples = items[:5]
                    for entity_id, label in samples:
                        print(f"  - [{label}] {entity_id}")

            # ================================================================
            # 6. PLACEHOLDER NODE DETECTION
            # ================================================================
            print("\n" + "=" * 80)
            print("6. PLACEHOLDER NODE DETECTION")
            print("=" * 80)

            result = session.run(
                """
                MATCH (n)
                WHERE n.entity_id CONTAINS ':'
                RETURN n.entity_id as entity_id,
                       labels(n) as labels,
                       properties(n) as props
                LIMIT 20
            """
            )

            placeholder_nodes = list(result)

            if placeholder_nodes:
                print(
                    f"\nFound {len(placeholder_nodes)} nodes with colon in entity_id (sample):"
                )
                for idx, record in enumerate(placeholder_nodes, 1):
                    entity_id = record["entity_id"]
                    labels = record["labels"]
                    props = record["props"]

                    print(f"\n  --- Node {idx} ---")
                    print(f"  Labels: {labels}")
                    print(f"  Entity ID: {entity_id}")
                    print(f"  Properties: {list(props.keys())}")

                    # Check if it looks like a placeholder
                    is_placeholder = (
                        "placeholder" in str(props).lower() or len(props) <= 3
                    )
                    if is_placeholder:
                        print("  ⚠️  Possible PLACEHOLDER node (minimal properties)")
            else:
                print("\n✅ No nodes with colon-separated entity_ids found")

            # ================================================================
            # 7. CROSS-REFERENCE CHECK
            # ================================================================
            print("\n" + "=" * 80)
            print("7. CROSS-REFERENCE VALIDATION")
            print("=" * 80)

            # Check if FILE nodes are referenced in relationships
            result = session.run(
                """
                MATCH (f:FILE)
                WITH f.entity_id as file_entity_id
                LIMIT 10
                MATCH (n)
                WHERE n.entity_id = file_entity_id
                OPTIONAL MATCH (n)-[r]-(connected)
                RETURN file_entity_id,
                       labels(n) as labels,
                       count(r) as relationship_count
            """
            )

            print("\nFILE node relationship connectivity:")
            for record in result:
                file_id = record["file_entity_id"]
                rel_count = record["relationship_count"]
                print(f"  {file_id}: {rel_count} relationships")

            # Check if Entity nodes reference FILE nodes
            result = session.run(
                """
                MATCH (e:Entity)-[r]->(target)
                WHERE target:FILE
                RETURN e.entity_id as entity_id,
                       target.entity_id as target_file_id,
                       type(r) as rel_type
                LIMIT 10
            """
            )

            entity_to_file_rels = list(result)
            if entity_to_file_rels:
                print(
                    f"\n✅ Found {len(entity_to_file_rels)} Entity->FILE relationships (sample):"
                )
                for record in entity_to_file_rels[:5]:
                    print(
                        f"  {record['entity_id']} -[{record['rel_type']}]-> {record['target_file_id']}"
                    )
            else:
                print("\n⚠️  No Entity->FILE relationships found")

            # ================================================================
            # SUMMARY
            # ================================================================
            print("\n" + "=" * 80)
            print("SUMMARY")
            print("=" * 80)

            print("\n📊 Key Findings:")
            print(f"  • Total nodes: {len(all_entity_ids)}")
            print(f"  • FILE nodes: {label_counts.get('FILE', 0)}")
            print(f"  • Entity nodes: {label_counts.get('Entity', 0)}")
            print(f"  • file_* pattern: {len(patterns['file_*'])} nodes")
            print(
                f"  • project:type:hash pattern: {len(patterns['project:type:hash'])} nodes"
            )
            print(f"  • Other colon patterns: {len(patterns['other_colon'])} nodes")
            print(f"  • Other formats: {len(patterns['other'])} nodes")

            print("\n🔑 Entity_id Format Standards:")
            if patterns["file_*"]:
                sample_file = patterns["file_*"][0][0]
                print(f"  FILE nodes use: 'file_<hash>' (e.g., {sample_file})")

            if patterns["project:type:hash"]:
                sample_proj = patterns["project:type:hash"][0][0]
                print(f"  Project nodes use: 'project:type:hash' (e.g., {sample_proj})")

            if patterns["other"]:
                sample_other = patterns["other"][0][0]
                print(f"  Other entities use: custom format (e.g., {sample_other})")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        driver.close()

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
