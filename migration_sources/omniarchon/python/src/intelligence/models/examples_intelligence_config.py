"""
Intelligence Adapter Configuration Examples.

This module demonstrates comprehensive usage patterns for ModelIntelligenceConfig
across different environments, use cases, and integration scenarios.

Usage Patterns:
    1. Environment-based Configuration (development, staging, production)
    2. Custom Configuration with Overrides
    3. Environment Variable Integration
    4. URL Helper Methods
    5. Event Topic Resolution
    6. Circuit Breaker Configuration

Run Examples:
    python -m intelligence.models.examples_intelligence_config

Created: 2025-10-21
Pattern: Configuration Examples
"""

import os
from typing import Dict

from intelligence.models.model_intelligence_config import ModelIntelligenceConfig


def example_development_config() -> None:
    """
    Example 1: Development Environment Configuration.

    Demonstrates creating configuration optimized for local development:
    - Local service URL (http://localhost:8053)
    - Short timeouts (30s) for quick feedback
    - Aggressive circuit breaker (3 failures) for early detection
    - Single input/output topics for simplicity
    - Development-prefixed topics
    """
    print("\n" + "=" * 80)
    print("Example 1: Development Environment Configuration")
    print("=" * 80)

    config = ModelIntelligenceConfig.for_environment("development")

    print(f"\n📍 Service Configuration:")
    print(f"   Base URL: {config.base_url}")
    print(f"   Timeout: {config.timeout_seconds}s")
    print(f"   Max Retries: {config.max_retries}")
    print(f"   Retry Delay: {config.retry_delay_ms}ms")

    print(f"\n🔒 Circuit Breaker:")
    print(f"   Enabled: {config.circuit_breaker_enabled}")
    print(f"   Threshold: {config.circuit_breaker_threshold} failures")
    print(f"   Recovery Timeout: {config.circuit_breaker_timeout_seconds}s")

    print(f"\n📡 Event Bus:")
    print(f"   Publishing Enabled: {config.enable_event_publishing}")
    print(f"   Consumer Group: {config.consumer_group_id}")
    print(f"   Input Topics:")
    for topic in config.input_topics:
        print(f"     - {topic}")
    print(f"   Output Topics:")
    for event_type, topic in config.output_topics.items():
        print(f"     - {event_type}: {topic}")

    print(f"\n🔗 Helper URLs:")
    print(f"   Health Check: {config.get_health_check_url()}")
    print(f"   Code Assessment: {config.get_assess_code_url()}")
    print(f"   Performance Baseline: {config.get_performance_baseline_url()}")


def example_staging_config() -> None:
    """
    Example 2: Staging Environment Configuration.

    Demonstrates staging configuration that mirrors production:
    - Container service URL (http://archon-intelligence:8053)
    - Moderate timeouts (45s) for load testing
    - Balanced circuit breaker (5 failures)
    - Multiple input topics for integration testing
    - Staging-prefixed topics
    """
    print("\n" + "=" * 80)
    print("Example 2: Staging Environment Configuration")
    print("=" * 80)

    config = ModelIntelligenceConfig.for_environment("staging")

    print(f"\n📍 Service Configuration:")
    print(f"   Base URL: {config.base_url}")
    print(f"   Timeout: {config.timeout_seconds}s")
    print(f"   Max Retries: {config.max_retries}")
    print(f"   Retry Delay: {config.retry_delay_ms}ms")

    print(f"\n🔒 Circuit Breaker:")
    print(f"   Threshold: {config.circuit_breaker_threshold} failures")
    print(f"   Recovery Timeout: {config.circuit_breaker_timeout_seconds}s")

    print(
        f"\n📡 Event Topics ({len(config.input_topics)} input, {len(config.output_topics)} output):"
    )
    print(f"   Consumer Group: {config.consumer_group_id}")


def example_production_config() -> None:
    """
    Example 3: Production Environment Configuration.

    Demonstrates production-ready configuration:
    - Container service URL for high availability
    - Extended timeouts (60s) for reliability
    - Lenient circuit breaker (10 failures) to avoid false positives
    - Multiple versioned topics for flexibility
    - Production-prefixed topics
    - Additional audit and pattern learning topics
    """
    print("\n" + "=" * 80)
    print("Example 3: Production Environment Configuration")
    print("=" * 80)

    config = ModelIntelligenceConfig.for_environment("production")

    print(f"\n📍 Service Configuration:")
    print(f"   Base URL: {config.base_url}")
    print(f"   Timeout: {config.timeout_seconds}s (max reliability)")
    print(f"   Max Retries: {config.max_retries} (max resilience)")
    print(f"   Retry Delay: {config.retry_delay_ms}ms")

    print(f"\n🔒 Circuit Breaker (Lenient for High Availability):")
    print(f"   Threshold: {config.circuit_breaker_threshold} failures")
    print(f"   Recovery Timeout: {config.circuit_breaker_timeout_seconds}s")

    print(f"\n📡 Event Topics (Production Scale):")
    print(f"   Input Topics: {len(config.input_topics)}")
    for topic in config.input_topics:
        print(f"     - {topic}")
    print(f"   Output Topics: {len(config.output_topics)}")
    for event_type in config.output_topics.keys():
        print(f"     - {event_type}")


def example_custom_config() -> None:
    """
    Example 4: Custom Configuration with Overrides.

    Demonstrates creating configuration with specific custom values:
    - Custom base URL
    - Custom timeout values
    - Custom circuit breaker settings
    - Custom topic names
    - Useful for special deployment scenarios
    """
    print("\n" + "=" * 80)
    print("Example 4: Custom Configuration with Overrides")
    print("=" * 80)

    config = ModelIntelligenceConfig(
        base_url="http://192.168.86.101:8053",
        timeout_seconds=90.0,
        max_retries=7,
        retry_delay_ms=2500,
        circuit_breaker_enabled=True,
        circuit_breaker_threshold=8,
        circuit_breaker_timeout_seconds=120.0,
        enable_event_publishing=True,
        input_topics=[
            "custom.omninode.intelligence.request.quality.v1",
            "custom.omninode.intelligence.request.performance.v1",
            "custom.omninode.intelligence.request.compliance.v1",
        ],
        output_topics={
            "quality_assessed": "custom.omninode.intelligence.event.quality_assessed.v1",
            "performance_optimized": "custom.omninode.intelligence.event.performance_optimized.v1",
            "compliance_checked": "custom.omninode.intelligence.event.compliance_checked.v1",
            "error": "custom.omninode.intelligence.event.error.v1",
            "audit": "custom.omninode.intelligence.audit.v1",
        },
        consumer_group_id="intelligence_adapter_custom",
    )

    print(f"\n✨ Custom Configuration Created")
    print(f"   Base URL: {config.base_url}")
    print(f"   Timeout: {config.timeout_seconds}s (custom extended)")
    print(f"   Circuit Breaker Threshold: {config.circuit_breaker_threshold}")
    print(f"   Input Topics: {len(config.input_topics)}")
    print(f"   Output Topics: {len(config.output_topics)}")


def example_environment_variable_config() -> None:
    """
    Example 5: Configuration from Environment Variable.

    Demonstrates automatic environment detection from ENVIRONMENT variable:
    - Reads ENVIRONMENT variable
    - Falls back to development if not set
    - Returns appropriate configuration
    - Supports environment-specific overrides via INTELLIGENCE_BASE_URL
    """
    print("\n" + "=" * 80)
    print("Example 5: Configuration from Environment Variable")
    print("=" * 80)

    # Save original environment
    original_env = os.environ.get("ENVIRONMENT")
    original_url = os.environ.get("INTELLIGENCE_BASE_URL")

    try:
        # Test case 1: Production environment
        os.environ["ENVIRONMENT"] = "production"
        os.environ["INTELLIGENCE_BASE_URL"] = "http://archon-intelligence-prod:8053"

        config = ModelIntelligenceConfig.from_environment_variable()

        print(f"\n🌍 Environment Variable Configuration:")
        print(f"   ENVIRONMENT: {os.environ['ENVIRONMENT']}")
        print(f"   INTELLIGENCE_BASE_URL: {os.environ['INTELLIGENCE_BASE_URL']}")
        print(f"   Resolved Base URL: {config.base_url}")
        print(f"   Circuit Breaker Threshold: {config.circuit_breaker_threshold}")
        print(f"   Consumer Group: {config.consumer_group_id}")

        # Test case 2: No environment set (fallback)
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("INTELLIGENCE_BASE_URL", None)

        config_fallback = ModelIntelligenceConfig.from_environment_variable()

        print(f"\n🔄 Fallback to Development:")
        print(f"   Base URL: {config_fallback.base_url}")
        print(f"   Consumer Group: {config_fallback.consumer_group_id}")

    finally:
        # Restore original environment
        if original_env:
            os.environ["ENVIRONMENT"] = original_env
        else:
            os.environ.pop("ENVIRONMENT", None)

        if original_url:
            os.environ["INTELLIGENCE_BASE_URL"] = original_url
        else:
            os.environ.pop("INTELLIGENCE_BASE_URL", None)


def example_url_helpers() -> None:
    """
    Example 6: URL Helper Methods.

    Demonstrates using helper methods to construct full API URLs:
    - Health check endpoint
    - Code assessment endpoint
    - Performance baseline endpoint
    - Automatic URL construction from base_url
    """
    print("\n" + "=" * 80)
    print("Example 6: URL Helper Methods")
    print("=" * 80)

    config = ModelIntelligenceConfig.for_environment("development")

    print(f"\n🔗 Intelligence Service API Endpoints:")
    print(f"   Base URL: {config.base_url}")
    print(f"\n   Health Check:")
    print(f"     GET {config.get_health_check_url()}")
    print(f"\n   Code Quality Assessment:")
    print(f"     POST {config.get_assess_code_url()}")
    print(f"\n   Performance Baseline:")
    print(f"     POST {config.get_performance_baseline_url()}")

    print(f"\n💡 Usage Example:")
    print(f"   import httpx")
    print(f"   async with httpx.AsyncClient() as client:")
    print(f"       response = await client.get('{config.get_health_check_url()}')")
    print(f"       health = response.json()")


def example_event_topic_resolution() -> None:
    """
    Example 7: Event Topic Resolution.

    Demonstrates resolving Kafka topics for specific event types:
    - Get output topic for event type
    - Handle unknown event types
    - Dynamic topic routing
    """
    print("\n" + "=" * 80)
    print("Example 7: Event Topic Resolution")
    print("=" * 80)

    config = ModelIntelligenceConfig.for_environment("production")

    print(f"\n📡 Event Topic Resolution:")

    # Test known event types
    event_types = [
        "quality_assessed",
        "performance_optimized",
        "compliance_checked",
        "pattern_learned",
        "error",
        "audit",
        "unknown_event",  # This will return None
    ]

    for event_type in event_types:
        topic = config.get_output_topic_for_event(event_type)
        if topic:
            print(f"   ✅ {event_type:25s} → {topic}")
        else:
            print(f"   ❌ {event_type:25s} → Not configured")

    print(f"\n💡 Usage in Event Publisher:")
    print(f"   event_type = 'quality_assessed'")
    print(f"   topic = config.get_output_topic_for_event(event_type)")
    print(f"   if topic:")
    print(f"       await kafka_producer.send(topic, event_data)")


def example_circuit_breaker_usage() -> None:
    """
    Example 8: Circuit Breaker Configuration Usage.

    Demonstrates how circuit breaker settings should be used:
    - Check if circuit breaker is enabled
    - Access threshold and timeout values
    - Integration with circuit breaker pattern
    """
    print("\n" + "=" * 80)
    print("Example 8: Circuit Breaker Configuration Usage")
    print("=" * 80)

    configs: Dict[str, ModelIntelligenceConfig] = {
        "Development": ModelIntelligenceConfig.for_environment("development"),
        "Staging": ModelIntelligenceConfig.for_environment("staging"),
        "Production": ModelIntelligenceConfig.for_environment("production"),
    }

    print(f"\n🔒 Circuit Breaker Settings by Environment:")
    print(
        f"\n   {'Environment':<15} {'Enabled':<10} {'Threshold':<12} {'Timeout (s)':<15}"
    )
    print(f"   {'-' * 15} {'-' * 10} {'-' * 12} {'-' * 15}")

    for env_name, config in configs.items():
        enabled = "Yes" if config.is_circuit_breaker_enabled() else "No"
        print(
            f"   {env_name:<15} {enabled:<10} "
            f"{config.circuit_breaker_threshold:<12} "
            f"{config.circuit_breaker_timeout_seconds:<15.1f}"
        )

    print(f"\n💡 Integration Example:")
    print(f"   from circuitbreaker import circuit")
    print(f"   ")
    print(f"   config = ModelIntelligenceConfig.from_environment_variable()")
    print(f"   ")
    print(f"   if config.is_circuit_breaker_enabled():")
    print(f"       @circuit(")
    print(f"           failure_threshold=config.circuit_breaker_threshold,")
    print(f"           recovery_timeout=config.circuit_breaker_timeout_seconds,")
    print(f"           name='intelligence_service'")
    print(f"       )")
    print(f"       async def call_intelligence_service():")
    print(f"           # Service call logic")
    print(f"           pass")


def example_validation_errors() -> None:
    """
    Example 9: Configuration Validation Errors.

    Demonstrates validation behavior with invalid configurations:
    - Invalid base URLs
    - Empty topic lists
    - Invalid topic naming conventions
    """
    print("\n" + "=" * 80)
    print("Example 9: Configuration Validation Examples")
    print("=" * 80)

    print(f"\n❌ Invalid Configuration Examples:")

    # Test 1: Invalid base URL
    print(f"\n   Test 1: Invalid base URL (missing http://)")
    try:
        config = ModelIntelligenceConfig(
            base_url="localhost:8053",  # Missing protocol
            input_topics=["dev.omninode.intelligence.request.assess.v1"],
            output_topics={"error": "dev.omninode.intelligence.event.error.v1"},
        )
        print(f"      ⚠️  Unexpected: Validation passed")
    except ValueError as e:
        print(f"      ✅ Expected validation error: {e}")

    # Test 2: Empty input topics
    print(f"\n   Test 2: Empty input topics list")
    try:
        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            input_topics=[],  # Empty list
            output_topics={"error": "dev.omninode.intelligence.event.error.v1"},
        )
        print(f"      ⚠️  Unexpected: Validation passed")
    except ValueError as e:
        print(f"      ✅ Expected validation error: {e}")

    # Test 3: Invalid topic naming convention
    print(f"\n   Test 3: Invalid topic naming (not following ONEX convention)")
    try:
        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            input_topics=["invalid_topic"],  # Missing ONEX format
            output_topics={"error": "dev.omninode.intelligence.event.error.v1"},
        )
        print(f"      ⚠️  Unexpected: Validation passed")
    except ValueError as e:
        print(f"      ✅ Expected validation error: {e}")

    # Test 4: Valid configuration
    print(f"\n   Test 4: Valid configuration")
    try:
        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053/",  # Trailing slash removed automatically
            input_topics=["dev.omninode.intelligence.request.assess.v1"],
            output_topics={"error": "dev.omninode.intelligence.event.error.v1"},
        )
        print(f"      ✅ Configuration validated successfully")
        print(f"      Base URL (normalized): {config.base_url}")
    except ValueError as e:
        print(f"      ❌ Unexpected error: {e}")


def main() -> None:
    """
    Run all configuration examples.

    Demonstrates comprehensive usage of ModelIntelligenceConfig including:
    - Environment-based configurations
    - Custom configurations
    - Environment variable integration
    - URL helper methods
    - Event topic resolution
    - Circuit breaker settings
    - Validation behavior
    """
    print("\n" + "=" * 80)
    print("ModelIntelligenceConfig - Comprehensive Usage Examples")
    print("=" * 80)
    print("\nDemonstrates configuration patterns for Intelligence Adapter Effect Node")
    print("across different environments and use cases.")

    # Run all examples
    example_development_config()
    example_staging_config()
    example_production_config()
    example_custom_config()
    example_environment_variable_config()
    example_url_helpers()
    example_event_topic_resolution()
    example_circuit_breaker_usage()
    example_validation_errors()

    print("\n" + "=" * 80)
    print("✅ All examples completed successfully!")
    print("=" * 80)
    print("\nNext Steps:")
    print(
        "   1. Choose environment-based config: config = ModelIntelligenceConfig.for_environment('production')"
    )
    print(
        "   2. Or use environment variable: config = ModelIntelligenceConfig.from_environment_variable()"
    )
    print(
        "   3. Access settings: config.base_url, config.circuit_breaker_threshold, etc."
    )
    print("   4. Use URL helpers: config.get_assess_code_url()")
    print(
        "   5. Resolve event topics: config.get_output_topic_for_event('quality_assessed')"
    )
    print("\n")


if __name__ == "__main__":
    main()
