#!/usr/bin/env python3
"""
Additional detailed inspection of Memgraph data structures
"""

import json

from neo4j import GraphDatabase

MEMGRAPH_URI = "bolt://localhost:7687"


def main():
    driver = GraphDatabase.driver(MEMGRAPH_URI, auth=None)

    try:
        with driver.session() as session:
            # 1. Inspect nested properties structure
            print("=" * 80)
            print("1. NESTED PROPERTIES STRUCTURE ANALYSIS")
            print("=" * 80)

            result = session.run(
                """
                MATCH (n:document)
                RETURN n.properties as props
                LIMIT 5
            """
            )

            for idx, record in enumerate(result, 1):
                props = record["props"]
                print(f"\n--- Document {idx} nested properties ---")
                if isinstance(props, dict):
                    print(json.dumps(props, indent=2))
                else:
                    print(f"Type: {type(props)}")
                    print(props)

            # 2. Check for metadata fields in nested properties
            print("\n" + "=" * 80)
            print("2. METADATA FIELDS IN NESTED PROPERTIES")
            print("=" * 80)

            result = session.run(
                """
                MATCH (n:document)
                WHERE n.properties IS NOT NULL
                RETURN n.properties as props
                LIMIT 1
            """
            )

            record = result.single()
            if record:
                props = record["props"]
                print("\nSample metadata structure:")
                print(json.dumps(props, indent=2))

                if isinstance(props, dict) and "metadata" in props:
                    print("\n✅ Metadata field exists in properties")
                    print(f"Metadata keys: {list(props.get('metadata', {}).keys())}")
                else:
                    print("\n⚠️  No metadata field in properties")

            # 3. Sample Entity nodes
            print("\n" + "=" * 80)
            print("3. SAMPLE ENTITY NODES")
            print("=" * 80)

            result = session.run(
                """
                MATCH (n:Entity)
                RETURN n
                LIMIT 3
            """
            )

            for idx, record in enumerate(result, 1):
                node = record["n"]
                print(f"\n--- Entity {idx} ---")
                print(f"Labels: {list(node.labels)}")
                print("Properties:")
                for key, value in dict(node).items():
                    if isinstance(value, dict):
                        print(f"  {key}: {json.dumps(value, indent=4)}")
                    else:
                        print(f"  {key}: {value}")

            # 4. Check for content_hash in nested properties
            print("\n" + "=" * 80)
            print("4. SEARCHING FOR CONTENT_HASH IN NESTED PROPERTIES")
            print("=" * 80)

            # Try to find if content_hash exists anywhere in properties
            result = session.run(
                """
                MATCH (n:document)
                WHERE n.properties IS NOT NULL
                RETURN n.properties as props
                LIMIT 10
            """
            )

            has_content_hash = False
            has_blake3_hash = False

            for record in result:
                props = record["props"]
                if isinstance(props, dict):
                    if "content_hash" in props:
                        has_content_hash = True
                        print(f"✅ Found content_hash in nested properties")
                        print(f"   Value: {props['content_hash']}")
                        break
                    if "blake3_hash" in props:
                        has_blake3_hash = True
                        print(f"✅ Found blake3_hash in nested properties")
                        print(f"   Value: {props['blake3_hash']}")
                        break
                    if "metadata" in props and isinstance(props["metadata"], dict):
                        meta = props["metadata"]
                        if "content_hash" in meta:
                            has_content_hash = True
                            print(f"✅ Found content_hash in metadata")
                            print(f"   Value: {meta['content_hash']}")
                            break
                        if "blake3_hash" in meta:
                            has_blake3_hash = True
                            print(f"✅ Found blake3_hash in metadata")
                            print(f"   Value: {meta['blake3_hash']}")
                            break

            if not has_content_hash and not has_blake3_hash:
                print("❌ No content_hash or blake3_hash found in nested properties")
                print("\nThis means BLAKE3 hashing is NOT being stored in Memgraph")

            # 5. Check project names in metadata
            print("\n" + "=" * 80)
            print("5. PROJECT NAMES IN METADATA")
            print("=" * 80)

            result = session.run(
                """
                MATCH (n:document)
                WHERE n.properties IS NOT NULL
                WITH n.properties as props
                RETURN DISTINCT props.metadata.project_name as project_name, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """
            )

            projects = list(result)
            if projects:
                print("Projects found in metadata:")
                for record in projects:
                    print(f"  {record['project_name']}: {record['count']} documents")
            else:
                print("No project names found in metadata")

            # 6. Check for file_path in metadata
            print("\n" + "=" * 80)
            print("6. FILE PATH STRUCTURE")
            print("=" * 80)

            result = session.run(
                """
                MATCH (n:document)
                WHERE n.properties IS NOT NULL
                RETURN n.properties.metadata.file_path as file_path
                LIMIT 5
            """
            )

            paths = list(result)
            if paths:
                print("Sample file paths from metadata:")
                for idx, record in enumerate(paths, 1):
                    print(f"  {idx}. {record['file_path']}")
            else:
                print("No file paths found in metadata")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        driver.close()


if __name__ == "__main__":
    main()
