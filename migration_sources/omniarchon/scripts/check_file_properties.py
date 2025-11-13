#!/usr/bin/env python3
"""Check all properties of FILE nodes in Memgraph"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INTELLIGENCE_SERVICE_DIR = PROJECT_ROOT / "services" / "intelligence"
sys.path.insert(0, str(INTELLIGENCE_SERVICE_DIR))

from storage.memgraph_adapter import MemgraphKnowledgeAdapter


async def main():
    memgraph_uri = "bolt://localhost:7687"
    adapter = MemgraphKnowledgeAdapter(uri=memgraph_uri, username=None, password=None)
    await adapter.initialize()

    query = """
    MATCH (f:FILE {project_name: 'omniarchon'})
    RETURN f
    LIMIT 1
    """

    async with adapter.driver.session() as session:
        result = await session.run(query)
        records = await result.data()

        if records:
            file_node = records[0]["f"]
            print("\nFILE node properties:")
            print("=" * 70)
            for key, value in file_node.items():
                print(f"{key}: {value}")
                if isinstance(value, str) and len(value) > 200:
                    print(f"  (truncated, length: {len(value)})")
            print("=" * 70)

    await adapter.close()


if __name__ == "__main__":
    asyncio.run(main())
