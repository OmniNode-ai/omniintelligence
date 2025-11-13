#!/usr/bin/env python3
"""
Test script for OmniNode Bridge MCP Tools

Tests the health check and basic functionality of the three OmniNode Bridge services:
1. OnexTree (port 8058)
2. Metadata Stamping (port 8057)
3. Workflow Coordinator (port 8006)
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_onextree_health():
    """Test OnexTree service health check."""
    print("\n" + "=" * 60)
    print("Testing OnexTree Health Check")
    print("=" * 60)

    try:
        from src.mcp_server.clients.onex_tree_client import OnexTreeClient

        async with OnexTreeClient(base_url="http://localhost:8058") as client:
            health = await client.check_health()
            print(f"✓ OnexTree Health Check: {health}")

            if health.get("healthy"):
                print("  Status: HEALTHY ✓")
                print(f"  Response Time: {health.get('response_time_ms', 'N/A')}ms")
                if "service_metrics" in health:
                    metrics = health["service_metrics"]
                    print(f"  Tree Loaded: {metrics.get('tree_loaded', 'N/A')}")
                    print(f"  Total Files: {metrics.get('total_files', 'N/A')}")
            else:
                print("  Status: UNHEALTHY ✗")
                print(f"  Error: {health.get('error', 'Unknown')}")

            return health.get("healthy", False)

    except Exception as e:
        print(f"✗ OnexTree Health Check Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_metadata_stamping_client():
    """Test Metadata Stamping service client."""
    print("\n" + "=" * 60)
    print("Testing Metadata Stamping Service")
    print("=" * 60)

    try:
        from src.mcp_server.clients.metadata_stamping_client import (
            MetadataStampingClient,
        )

        async with MetadataStampingClient(base_url="http://localhost:8057") as client:
            # Test basic health check
            health = await client.check_health()
            print(f"✓ Metadata Stamping Health: {health}")

            if health.get("healthy"):
                print("  Status: HEALTHY ✓")
                print(f"  Response Time: {health.get('response_time_ms', 'N/A')}ms")
            else:
                print("  Status: UNHEALTHY ✗")
                print(f"  Error: {health.get('error', 'Unknown')}")

            # Note: The service might not have a /health endpoint
            # Let's try to get metrics instead
            try:
                metrics = await client.get_metrics()
                print(f"✓ Service Metrics: {metrics}")
                return True
            except Exception as me:
                print(f"  Metrics endpoint not available: {me}")
                # Service is running but might not have all endpoints
                return health.get("healthy", False)

    except Exception as e:
        print(f"✗ Metadata Stamping Test Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_workflow_coordinator_health():
    """Test Workflow Coordinator service health check."""
    print("\n" + "=" * 60)
    print("Testing Workflow Coordinator Health Check")
    print("=" * 60)

    try:
        from src.mcp_server.clients.workflow_coordinator_client import (
            WorkflowCoordinatorClient,
        )

        async with WorkflowCoordinatorClient(
            base_url="http://localhost:8006"
        ) as client:
            health = await client.check_health()
            print(f"✓ Workflow Coordinator Health: {health}")

            if health.get("healthy"):
                print("  Status: HEALTHY ✓")
                print(f"  Response Time: {health.get('response_time_ms', 'N/A')}ms")
            else:
                print("  Status: UNHEALTHY ✗")
                print(f"  Error: {health.get('error', 'Unknown')}")

            # Get client metrics
            metrics = client.get_metrics()
            print("\n  Client Metrics:")
            print(f"    Total Requests: {metrics.get('total_requests', 0)}")
            print(f"    Success Rate: {metrics.get('success_rate', 0):.2%}")
            print(
                f"    Circuit Breaker: {metrics.get('circuit_breaker_state', 'unknown')}"
            )

            return health.get("healthy", False)

    except Exception as e:
        print(f"✗ Workflow Coordinator Health Check Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_workflow_coordinator_list():
    """Test listing active workflows."""
    print("\n" + "=" * 60)
    print("Testing Workflow Coordinator - List Active Workflows")
    print("=" * 60)

    try:
        from src.mcp_server.clients.workflow_coordinator_client import (
            WorkflowCoordinatorClient,
        )

        async with WorkflowCoordinatorClient(
            base_url="http://localhost:8006"
        ) as client:
            workflows = await client.list_active_workflows()
            print(f"✓ Active Workflows Response: {workflows}")
            print(f"  Total Active Workflows: {len(workflows.workflows)}")

            if workflows.workflows:
                for wf in workflows.workflows[:3]:  # Show first 3
                    print(f"    - {wf.workflow_name} ({wf.workflow_id}): {wf.status}")
            else:
                print("    No active workflows")

            return True

    except Exception as e:
        print(f"✗ List Workflows Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("OmniNode Bridge MCP Tools - Test Suite")
    print("=" * 60)

    results = {
        "OnexTree Health": await test_onextree_health(),
        "Metadata Stamping": await test_metadata_stamping_client(),
        "Workflow Coordinator Health": await test_workflow_coordinator_health(),
        "Workflow Coordinator List": await test_workflow_coordinator_list(),
    }

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    print(f"\nTotal: {passed}/{total} tests passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
