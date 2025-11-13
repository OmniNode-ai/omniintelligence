#!/usr/bin/env python3
"""Quick script to check file path format in Memgraph"""

import asyncio
import os
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
    RETURN f.path as path
    LIMIT 10
    """

    async with adapter.driver.session() as session:
        result = await session.run(query)
        records = await result.data()

        print(f"\nFound {len(records)} sample file paths:\n")
        for idx, record in enumerate(records, 1):
            path = record["path"]
            print(f"{idx}. {path}")
            print(f"   Type: {type(path)}")
            print(f"   Is absolute: {Path(path).is_absolute()}")
            print()

    await adapter.close()


if __name__ == "__main__":
    asyncio.run(main())
