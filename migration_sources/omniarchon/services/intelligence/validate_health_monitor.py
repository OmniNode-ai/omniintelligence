"""
Standalone validation script for health monitor.

Tests that health monitor can be instantiated and basic functionality works.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


async def validate_health_monitor():
    """Validate health monitor functionality."""
    print("=" * 60)
    print("Health Monitor Validation")
    print("=" * 60)

    # Import health monitor directly (avoid services/__init__.py)
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "health_monitor",
            Path(__file__).parent / "src" / "services" / "health_monitor.py",
        )
        health_monitor_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(health_monitor_module)

        HealthMonitor = health_monitor_module.HealthMonitor
        HealthStatus = health_monitor_module.HealthStatus
        ServiceHealth = health_monitor_module.ServiceHealth

        print("✅ Successfully imported health monitor modules")
    except ImportError as e:
        print(f"❌ Failed to import health monitor: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Create health monitor instance
    try:
        monitor = HealthMonitor(
            qdrant_host="localhost",
            qdrant_port=6333,
            postgres_host="localhost",
            postgres_port=5436,
            postgres_database="test_db",
            postgres_user="test_user",
            postgres_password="test_password",
            kafka_bootstrap_servers="localhost:9092",
            cache_ttl=30,
        )
        print("✅ Successfully created health monitor instance")
        print(f"   - Qdrant: {monitor.qdrant_host}:{monitor.qdrant_port}")
        print(f"   - PostgreSQL: {monitor.postgres_host}:{monitor.postgres_port}")
        print(f"   - Kafka: {monitor.kafka_bootstrap_servers}")
        print(f"   - Cache TTL: {monitor.cache_ttl}s")
    except Exception as e:
        print(f"❌ Failed to create health monitor: {e}")
        return False

    # Test creating from environment
    try:
        import os

        os.environ["QDRANT_HOST"] = "test-host"
        os.environ["QDRANT_PORT"] = "6334"

        env_monitor = HealthMonitor.from_env()
        print("✅ Successfully created health monitor from environment")
        print(f"   - Qdrant host from env: {env_monitor.qdrant_host}")
        print(f"   - Qdrant port from env: {env_monitor.qdrant_port}")
    except Exception as e:
        print(f"❌ Failed to create health monitor from env: {e}")
        return False

    # Test ServiceHealth model
    try:
        from datetime import datetime, timezone

        service_health = ServiceHealth(
            service="test_service",
            status=HealthStatus.HEALTHY,
            response_time_ms=50.0,
            message="Test service is healthy",
            last_checked=datetime.now(timezone.utc),
        )
        print("✅ Successfully created ServiceHealth model")
        print(f"   - Service: {service_health.service}")
        print(f"   - Status: {service_health.status.value}")
        print(f"   - Response time: {service_health.response_time_ms}ms")
    except Exception as e:
        print(f"❌ Failed to create ServiceHealth model: {e}")
        return False

    # Test cache validity
    try:
        # Test with no cache
        assert not monitor._is_cache_valid(), "Cache should be invalid initially"
        print("✅ Cache validation works correctly")
    except Exception as e:
        print(f"❌ Cache validation failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("✅ All validation checks passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    result = asyncio.run(validate_health_monitor())
    sys.exit(0 if result else 1)
