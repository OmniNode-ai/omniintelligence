"""
Intelligence Adapter Event Contracts - Usage Examples

Demonstrates how to use the Intelligence Adapter event schemas for:
- Publishing events to Kafka
- Consuming events from Kafka
- Event flow patterns (request → completed/failed)
- Error handling and retry logic

Created: 2025-10-21
Reference: intelligence_adapter_events.py
"""

import json
from typing import Any, Optional
from uuid import UUID, uuid4

from intelligence_adapter_events import (
    EnumAnalysisErrorCode,
    EnumAnalysisOperationType,
    EnumCodeAnalysisEventType,
    IntelligenceAdapterEventHelpers,
    ModelCodeAnalysisCompletedPayload,
    ModelCodeAnalysisFailedPayload,
    ModelCodeAnalysisRequestPayload,
    create_completed_event,
    create_failed_event,
    create_request_event,
)

# ============================================================================
# Example 1: Publishing CODE_ANALYSIS_REQUESTED Event
# ============================================================================


def example_publish_analysis_request():
    """
    Example: Publish code analysis request event to Kafka.

    Flow:
    1. Create request payload
    2. Generate event envelope
    3. Serialize to JSON
    4. Publish to Kafka topic
    """
    print("\n" + "=" * 80)
    print("Example 1: Publishing CODE_ANALYSIS_REQUESTED Event")
    print("=" * 80)

    # Step 1: Create request payload
    payload = ModelCodeAnalysisRequestPayload(
        source_path="src/services/intelligence/quality_service.py",
        content=None,  # Will read from file
        language="python",
        operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
        options={
            "include_metrics": True,
            "depth": "comprehensive",
            "quality_threshold": 0.8,
            "enable_caching": True,
        },
        project_id="omniarchon",
        user_id="system",
    )

    # Step 2: Generate correlation ID for tracking
    correlation_id = uuid4()

    # Step 3: Create event envelope
    event_envelope = IntelligenceAdapterEventHelpers.create_analysis_requested_event(
        payload=payload,
        correlation_id=correlation_id,
        source_instance="intelligence-adapter-001",
    )

    # Step 4: Determine Kafka topic
    topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
        event_type=EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED,
        environment="development",
    )

    # Step 5: Serialize to JSON (ready for Kafka)
    event_json = json.dumps(event_envelope, indent=2, default=str)

    print(f"\n📤 Publishing to topic: {topic}")
    print(f"🔗 Correlation ID: {correlation_id}")
    print(f"\n📦 Event Envelope:")
    print(event_json)

    # Step 6: Publish to Kafka (pseudo-code)
    # from kafka import KafkaProducer
    # producer = KafkaProducer(
    #     bootstrap_servers=['localhost:9092'],
    #     value_serializer=lambda v: json.dumps(v).encode('utf-8')
    # )
    # producer.send(topic, value=event_envelope)
    # producer.flush()

    print("\n✅ Event published successfully!")
    return correlation_id, event_envelope


# ============================================================================
# Example 2: Publishing CODE_ANALYSIS_COMPLETED Event
# ============================================================================


def example_publish_analysis_completed(correlation_id: UUID):
    """
    Example: Publish code analysis completed event to Kafka.

    Args:
        correlation_id: Correlation ID from original request
    """
    print("\n" + "=" * 80)
    print("Example 2: Publishing CODE_ANALYSIS_COMPLETED Event")
    print("=" * 80)

    # Step 1: Create completion payload
    payload = ModelCodeAnalysisCompletedPayload(
        source_path="src/services/intelligence/quality_service.py",
        quality_score=0.87,
        onex_compliance=0.92,
        issues_count=3,
        recommendations_count=5,
        processing_time_ms=1234.5,
        operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
        complexity_score=0.45,
        maintainability_score=0.78,
        results_summary={
            "total_lines": 245,
            "cyclomatic_complexity": 12,
            "cognitive_complexity": 18,
            "pattern_matches": ["onex_effect_pattern", "async_transaction"],
            "anti_patterns": ["god_class"],
            "security_issues": [],
        },
        cache_hit=False,
    )

    # Step 2: Create event envelope (with correlation ID from request)
    event_envelope = IntelligenceAdapterEventHelpers.create_analysis_completed_event(
        payload=payload,
        correlation_id=correlation_id,
        causation_id=None,  # Could link to request event_id
        source_instance="intelligence-adapter-001",
    )

    # Step 3: Determine Kafka topic
    topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
        event_type=EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED,
        environment="development",
    )

    # Step 4: Serialize to JSON
    event_json = json.dumps(event_envelope, indent=2, default=str)

    print(f"\n📤 Publishing to topic: {topic}")
    print(f"🔗 Correlation ID: {correlation_id}")
    print(f"\n📦 Event Envelope:")
    print(event_json)

    print("\n✅ Analysis completed event published successfully!")
    return event_envelope


# ============================================================================
# Example 3: Publishing CODE_ANALYSIS_FAILED Event
# ============================================================================


def example_publish_analysis_failed(correlation_id: UUID):
    """
    Example: Publish code analysis failed event to Kafka.

    Args:
        correlation_id: Correlation ID from original request
    """
    print("\n" + "=" * 80)
    print("Example 3: Publishing CODE_ANALYSIS_FAILED Event")
    print("=" * 80)

    # Step 1: Create failure payload
    payload = ModelCodeAnalysisFailedPayload(
        operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        source_path="src/broken/invalid_syntax.py",
        error_message="Failed to parse Python code: unexpected EOF at line 42",
        error_code=EnumAnalysisErrorCode.PARSING_ERROR,
        retry_allowed=False,
        retry_count=0,
        processing_time_ms=456.7,
        error_details={
            "exception_type": "SyntaxError",
            "line_number": 42,
            "column": 15,
            "stack_trace": "Traceback (most recent call last)...",
            "parser": "ast.parse",
        },
        suggested_action="Verify source code syntax is valid. Run `python -m py_compile src/broken/invalid_syntax.py` to validate.",
    )

    # Step 2: Create event envelope
    event_envelope = IntelligenceAdapterEventHelpers.create_analysis_failed_event(
        payload=payload,
        correlation_id=correlation_id,
        source_instance="intelligence-adapter-001",
    )

    # Step 3: Determine Kafka topic
    topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
        event_type=EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED,
        environment="development",
    )

    # Step 4: Serialize to JSON
    event_json = json.dumps(event_envelope, indent=2, default=str)

    print(f"\n📤 Publishing to topic: {topic}")
    print(f"🔗 Correlation ID: {correlation_id}")
    print(f"\n📦 Event Envelope:")
    print(event_json)

    print("\n✅ Analysis failed event published successfully!")
    return event_envelope


# ============================================================================
# Example 4: Consuming Events from Kafka
# ============================================================================


def example_consume_events():
    """
    Example: Consume and process Intelligence Adapter events from Kafka.

    Demonstrates:
    - Event deserialization
    - Type-safe payload extraction
    - Event-specific handling logic
    """
    print("\n" + "=" * 80)
    print("Example 4: Consuming Events from Kafka")
    print("=" * 80)

    # Pseudo-code for Kafka consumer
    # from kafka import KafkaConsumer
    #
    # consumer = KafkaConsumer(
    #     'dev.archon-intelligence.intelligence.code-analysis-*.v1',
    #     bootstrap_servers=['localhost:9092'],
    #     value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    # )
    #
    # for message in consumer:
    #     event_envelope = message.value
    #     process_event(event_envelope)

    # Simulate received event
    sample_event = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "omninode.intelligence.event.code_analysis_completed.v1",
        "correlation_id": "660e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2025-10-21T10:00:00.000Z",
        "version": "1.0.0",
        "source": {
            "service": "archon-intelligence",
            "instance_id": "intelligence-adapter-001",
        },
        "payload": {
            "source_path": "src/services/intelligence/quality_service.py",
            "quality_score": 0.87,
            "onex_compliance": 0.92,
            "issues_count": 3,
            "recommendations_count": 5,
            "processing_time_ms": 1234.5,
            "operation_type": "COMPREHENSIVE_ANALYSIS",
            "results_summary": {"total_lines": 245},
            "cache_hit": False,
        },
    }

    print("\n📥 Received event from Kafka:")
    print(json.dumps(sample_event, indent=2))

    # Deserialize event
    event_type, typed_payload = IntelligenceAdapterEventHelpers.deserialize_event(
        sample_event
    )

    print(f"\n🔍 Event Type: {event_type}")
    print(f"📋 Payload Type: {type(typed_payload).__name__}")

    # Type-safe handling based on event type
    if event_type == EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED.value:
        handle_analysis_completed(typed_payload)
    elif event_type == EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED.value:
        handle_analysis_failed(typed_payload)
    elif event_type == EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value:
        handle_analysis_requested(typed_payload)


def handle_analysis_requested(payload: ModelCodeAnalysisRequestPayload):
    """Handle CODE_ANALYSIS_REQUESTED event."""
    print(f"\n🚀 Handling analysis request for: {payload.source_path}")
    print(f"   Operation: {payload.operation_type.value}")
    print(f"   Language: {payload.language}")

    # Trigger analysis workflow
    # result = analyze_code(payload)
    # publish_result(result)


def handle_analysis_completed(payload: ModelCodeAnalysisCompletedPayload):
    """Handle CODE_ANALYSIS_COMPLETED event."""
    print(f"\n✅ Analysis completed for: {payload.source_path}")
    print(f"   Quality Score: {payload.quality_score:.2f}")
    print(f"   ONEX Compliance: {payload.onex_compliance:.2f}")
    print(f"   Issues: {payload.issues_count}")
    print(f"   Processing Time: {payload.processing_time_ms:.2f}ms")

    # Store results, update metrics, trigger notifications
    # store_analysis_results(payload)
    # update_quality_metrics(payload)
    # if payload.quality_score < 0.7:
    #     send_alert(payload)


def handle_analysis_failed(payload: ModelCodeAnalysisFailedPayload):
    """Handle CODE_ANALYSIS_FAILED event."""
    print(f"\n❌ Analysis failed for: {payload.source_path}")
    print(f"   Error: {payload.error_message}")
    print(f"   Error Code: {payload.error_code.value}")
    print(f"   Retry Allowed: {payload.retry_allowed}")

    # Log error, trigger retry if allowed, send alert
    # log_error(payload)
    # if payload.retry_allowed and payload.retry_count < 3:
    #     schedule_retry(payload)
    # else:
    #     send_error_alert(payload)


# ============================================================================
# Example 5: Convenience Functions
# ============================================================================


def example_convenience_functions():
    """
    Example: Using convenience functions for quick event creation.
    """
    print("\n" + "=" * 80)
    print("Example 5: Convenience Functions for Quick Event Creation")
    print("=" * 80)

    # Quick request event
    request_event = create_request_event(
        source_path="src/api/endpoints.py",
        language="python",
        operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        options={"include_metrics": True},
    )

    print("\n📝 Request Event (convenience function):")
    print(json.dumps(request_event, indent=2, default=str))

    # Quick completed event
    correlation_id = UUID(request_event["correlation_id"])

    completed_event = create_completed_event(
        source_path="src/api/endpoints.py",
        quality_score=0.92,
        onex_compliance=0.88,
        issues_count=1,
        recommendations_count=3,
        processing_time_ms=567.8,
        operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        correlation_id=correlation_id,
        cache_hit=False,
    )

    print("\n✅ Completed Event (convenience function):")
    print(json.dumps(completed_event, indent=2, default=str))

    # Quick failed event
    failed_event = create_failed_event(
        operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        source_path="src/broken/file.py",
        error_message="File not found",
        error_code=EnumAnalysisErrorCode.INVALID_INPUT,
        correlation_id=correlation_id,
        retry_allowed=False,
        processing_time_ms=12.3,
    )

    print("\n❌ Failed Event (convenience function):")
    print(json.dumps(failed_event, indent=2, default=str))


# ============================================================================
# Example 6: Event Flow Pattern (Complete Request-Response Cycle)
# ============================================================================


def example_complete_event_flow():
    """
    Example: Complete event flow from request to completion/failure.

    Demonstrates:
    - Publishing request event
    - Processing request (simulated)
    - Publishing result event (completed or failed)
    - Correlation ID tracking throughout flow
    """
    print("\n" + "=" * 80)
    print("Example 6: Complete Event Flow (Request → Processing → Result)")
    print("=" * 80)

    # Step 1: Publish request event
    correlation_id, request_event = example_publish_analysis_request()

    # Step 2: Simulate processing
    print("\n⏳ Processing analysis request...")
    print("   - Reading source file")
    print("   - Parsing code")
    print("   - Running quality checks")
    print("   - Analyzing ONEX compliance")
    print("   - Generating recommendations")

    # Step 3: Publish result event (success or failure)
    import random

    success = random.choice([True, True, False])  # 67% success rate

    if success:
        example_publish_analysis_completed(correlation_id)
    else:
        example_publish_analysis_failed(correlation_id)

    print("\n🎯 Complete event flow demonstrated successfully!")


# ============================================================================
# Example 7: Error Handling and Retry Logic
# ============================================================================


def example_error_handling_and_retry():
    """
    Example: Error handling and retry logic for failed analysis.

    Demonstrates:
    - Detecting failures
    - Retry eligibility checks
    - Exponential backoff
    - Maximum retry limits
    """
    print("\n" + "=" * 80)
    print("Example 7: Error Handling and Retry Logic")
    print("=" * 80)

    correlation_id = uuid4()

    # Simulate multiple retry attempts
    max_retries = 3

    for retry_count in range(max_retries + 1):
        print(f"\n🔄 Attempt {retry_count + 1}/{max_retries + 1}")

        # Determine retry eligibility
        retry_allowed = retry_count < max_retries

        # Create failed event
        failed_event = create_failed_event(
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            source_path="src/flaky/service.py",
            error_message=f"External service timeout (attempt {retry_count + 1})",
            error_code=EnumAnalysisErrorCode.TIMEOUT,
            correlation_id=correlation_id,
            retry_allowed=retry_allowed,
            processing_time_ms=30000.0,  # 30 second timeout
            error_details={
                "attempt": retry_count + 1,
                "max_retries": max_retries,
                "backoff_seconds": 2**retry_count,  # Exponential backoff
            },
        )

        # Extract payload for inspection
        _, payload = IntelligenceAdapterEventHelpers.deserialize_event(failed_event)

        print(f"   Error: {payload.error_message}")
        print(f"   Retry Allowed: {payload.retry_allowed}")
        print(f"   Backoff: {2**retry_count} seconds")

        if not retry_allowed:
            print("\n❌ Max retries exceeded. Giving up.")
            break

        # Simulate retry delay (exponential backoff)
        print(f"   ⏰ Waiting {2**retry_count} seconds before retry...")

    print("\n🛑 Error handling and retry logic demonstrated!")


# ============================================================================
# Main Execution
# ============================================================================


def main():
    """Run all usage examples."""
    print("\n" + "=" * 80)
    print("Intelligence Adapter Event Contracts - Usage Examples")
    print("=" * 80)

    # Run examples
    example_publish_analysis_request()
    correlation_id = uuid4()
    example_publish_analysis_completed(correlation_id)
    example_publish_analysis_failed(correlation_id)
    example_consume_events()
    example_convenience_functions()
    example_complete_event_flow()
    example_error_handling_and_retry()

    print("\n" + "=" * 80)
    print("✅ All examples completed successfully!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
