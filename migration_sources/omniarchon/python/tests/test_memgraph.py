#!/usr/bin/env python3
"""
Simple test script to verify Memgraph connectivity
"""

import sys

try:
    from neo4j import GraphDatabase

    # Test connection to Memgraph
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)

    with driver.session() as session:
        # Simple test query
        result = session.run("RETURN 'Hello Memgraph!' as greeting")
        record = result.single()
        print(f"✅ Connection successful: {record['greeting']}")

        # Test creating and retrieving a node
        session.run(
            "CREATE (n:Test {name: 'connectivity_test', timestamp: datetime()}) RETURN n"
        )
        result = session.run(
            "MATCH (n:Test {name: 'connectivity_test'}) RETURN n.name as name"
        )
        record = result.single()
        if record:
            print(f"✅ Node creation successful: {record['name']}")

        # Clean up test node
        session.run("MATCH (n:Test {name: 'connectivity_test'}) DELETE n")
        print("✅ Cleanup successful")

    driver.close()
    print("🎉 Memgraph connectivity test PASSED!")

except ImportError:
    print("❌ neo4j package not installed. Run: pip install neo4j")
    sys.exit(1)
except Exception as e:
    print(f"❌ Memgraph connectivity test FAILED: {e}")
    sys.exit(1)
