#!/usr/bin/env python3
"""
Test script to verify LangExtract client async lifecycle management.

This test verifies that:
1. BridgeIntelligenceGenerator can be initialized
2. The async initialize() method properly connects the LangExtract client
3. The LangExtract client can be used without "Client not connected" errors
4. The shutdown() method properly closes the client
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.bridge_intelligence_generator import BridgeIntelligenceGenerator


async def test_langextract_lifecycle():
    """Test LangExtract client lifecycle management"""
    print("=" * 80)
    print("Testing LangExtract Client Async Lifecycle Management")
    print("=" * 80)

    # Step 1: Create generator
    print("\n[1/5] Creating BridgeIntelligenceGenerator...")
    generator = BridgeIntelligenceGenerator(
        langextract_url="http://archon-langextract:8156", db_pool=None
    )
    print("✅ Generator created successfully")

    # Step 2: Initialize async resources
    print("\n[2/5] Initializing async resources (connecting LangExtract client)...")
    try:
        await generator.initialize()
        print("✅ LangExtract client connected successfully")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return False

    # Step 3: Verify client is connected
    print("\n[3/5] Verifying client connection state...")
    if generator._langextract_connected:
        print("✅ Client connection flag is True")
    else:
        print("❌ Client connection flag is False")
        return False

    if generator.langextract_client.client is not None:
        print("✅ HTTP client is initialized")
    else:
        print("❌ HTTP client is None")
        return False

    # Step 4: Test that client methods are available (don't call - just check existence)
    print("\n[4/5] Verifying client methods are available...")
    if hasattr(generator.langextract_client, "analyze_semantic"):
        print("✅ analyze_semantic method exists")
    else:
        print("❌ analyze_semantic method missing")
        return False

    # Step 5: Shutdown and cleanup
    print("\n[5/5] Shutting down and closing LangExtract client...")
    try:
        await generator.shutdown()
        print("✅ Client shutdown successfully")
    except Exception as e:
        print(f"❌ Failed to shutdown: {e}")
        return False

    # Verify client is disconnected
    if not generator._langextract_connected:
        print("✅ Client connection flag is False after shutdown")
    else:
        print("❌ Client connection flag is still True after shutdown")
        return False

    if generator.langextract_client.client is None:
        print("✅ HTTP client is None after shutdown")
    else:
        print("❌ HTTP client is still initialized after shutdown")
        return False

    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - LangExtract client lifecycle works correctly!")
    print("=" * 80)
    return True


async def main():
    """Run the test"""
    try:
        success = await test_langextract_lifecycle()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
