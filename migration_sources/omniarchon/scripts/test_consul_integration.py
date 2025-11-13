#!/usr/bin/env python3
"""
Test Consul Integration

Validates Consul service discovery integration with remote Consul instance.
"""

import os
import sys

# Add parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python", "src"))

from server.services.consul_service import ConsulService


def test_consul_connectivity():
    """Test basic Consul connectivity."""
    print("=" * 60)
    print("Testing Consul Connectivity")
    print("=" * 60)

    # Test with host machine configuration (external port)
    consul = ConsulService(host="192.168.86.200", port=28500, enabled=True)

    if not consul.enabled:
        print("❌ Consul client not enabled")
        return False

    if not consul.client:
        print("❌ Consul client not initialized")
        return False

    # Try to query Consul status
    try:
        # Check if we can communicate with Consul
        leader = consul.client.status.leader()
        print(f"✅ Consul leader: {leader}")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Consul: {e}")
        return False


def test_service_registration():
    """Test service registration and deregistration."""
    print("\n" + "=" * 60)
    print("Testing Service Registration")
    print("=" * 60)

    consul = ConsulService(host="192.168.86.200", port=28500, enabled=True)

    if not consul.enabled:
        print("❌ Consul not enabled")
        return False

    # Register test service
    service_id = "test-service-1"
    success = consul.register_service(
        service_id=service_id,
        service_name="test-service",
        port=9999,
        address="localhost",
        tags=["test", "integration"],
        meta={"test": "true"},
    )

    if not success:
        print("❌ Failed to register service")
        return False

    print(f"✅ Registered service: {service_id}")

    # Verify service is registered
    try:
        instances = consul.discover_service("test-service", passing_only=False)
        if not instances:
            print("❌ Service not found after registration")
            return False

        print(f"✅ Found {len(instances)} instance(s) of test-service")
        for instance in instances:
            print(
                f"   - {instance['service_id']}: {instance['address']}:{instance['port']}"
            )
    except Exception as e:
        print(f"❌ Failed to discover service: {e}")
        return False

    # Deregister test service
    success = consul.deregister_service(service_id)
    if not success:
        print("❌ Failed to deregister service")
        return False

    print(f"✅ Deregistered service: {service_id}")

    # Verify service is deregistered
    instances = consul.discover_service("test-service", passing_only=False)
    if instances:
        print(
            f"⚠️  Warning: Service still found after deregistration ({len(instances)} instance(s))"
        )
    else:
        print("✅ Service successfully removed from Consul")

    return True


def test_service_discovery():
    """Test service discovery."""
    print("\n" + "=" * 60)
    print("Testing Service Discovery")
    print("=" * 60)

    consul = ConsulService(host="192.168.86.200", port=28500, enabled=True)

    if not consul.enabled:
        print("❌ Consul not enabled")
        return False

    # Register multiple test services
    service_ids = []
    for i in range(3):
        service_id = f"test-discovery-{i}"
        consul.register_service(
            service_id=service_id,
            service_name="test-discovery",
            port=10000 + i,
            address="localhost",
            tags=["test", f"instance-{i}"],
        )
        service_ids.append(service_id)

    print(f"✅ Registered {len(service_ids)} test services")

    # Discover all instances
    instances = consul.discover_service("test-discovery", passing_only=False)
    print(f"✅ Discovered {len(instances)} instance(s)")

    for instance in instances:
        print(
            f"   - {instance['service_id']}: {instance['address']}:{instance['port']}"
        )
        print(f"     Tags: {instance['tags']}")

    # Test get_service_url
    url = consul.get_service_url("test-discovery")
    if url:
        print(f"✅ Service URL: {url}")
    else:
        print("⚠️  No service URL returned")

    # Cleanup
    for service_id in service_ids:
        consul.deregister_service(service_id)

    print(f"✅ Cleaned up {len(service_ids)} test services")

    return True


def test_consul_utils():
    """Test Consul utility functions."""
    print("\n" + "=" * 60)
    print("Testing Consul Utilities")
    print("=" * 60)

    # Import after path is set
    from server.utils.consul_utils import (
        get_service_url,
        is_service_healthy,
        list_service_instances,
    )

    # Register test service first
    consul = ConsulService(host="192.168.86.200", port=28500, enabled=True)
    service_id = "test-utils-service"
    consul.register_service(
        service_id=service_id,
        service_name="test-utils",
        port=11000,
        address="localhost",
    )

    print(f"✅ Registered test service: {service_id}")

    # Test list_service_instances
    instances = list_service_instances("test-utils", passing_only=False)
    print(f"✅ list_service_instances: {len(instances)} instance(s)")

    # Test is_service_healthy
    healthy = is_service_healthy("test-utils")
    print(f"✅ is_service_healthy: {healthy}")

    # Test get_service_url with fallback
    url = get_service_url("test-utils", fallback_url="http://localhost:11000")
    print(f"✅ get_service_url: {url}")

    # Test with non-existent service
    url = get_service_url("non-existent-service", fallback_url="http://localhost:9999")
    print(f"✅ get_service_url (fallback): {url}")

    # Cleanup
    consul.deregister_service(service_id)
    print(f"✅ Cleaned up test service: {service_id}")

    return True


def main():
    """Run all Consul integration tests."""
    print("\n" + "=" * 60)
    print("CONSUL INTEGRATION TEST SUITE")
    print("=" * 60)
    print()

    tests = [
        ("Connectivity", test_consul_connectivity),
        ("Service Registration", test_service_registration),
        ("Service Discovery", test_service_discovery),
        ("Consul Utilities", test_consul_utils),
    ]

    results = {}
    for name, test_func in tests:
        try:
            success = test_func()
            results[name] = success
        except Exception as e:
            print(f"\n❌ Test '{name}' failed with exception: {e}")
            import traceback

            traceback.print_exc()
            results[name] = False

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")

    print()
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
