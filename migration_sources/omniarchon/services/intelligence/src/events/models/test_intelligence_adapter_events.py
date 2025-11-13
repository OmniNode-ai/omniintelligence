"""
Quick validation test for Intelligence Adapter Event Contracts.

Verifies:
- Event creation
- Payload validation
- Serialization
- Deserialization
- Topic routing

Run: python test_intelligence_adapter_events.py
"""

import json
from uuid import UUID, uuid4

# Import event contracts
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


def test_request_payload_creation():
    """Test request payload creation and validation."""
    print("\n" + "=" * 80)
    print("Test 1: Request Payload Creation")
    print("=" * 80)

    payload = ModelCodeAnalysisRequestPayload(
        source_path="src/services/intelligence/quality_service.py",
        content=None,
        language="python",
        operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
        options={"include_metrics": True, "depth": "comprehensive"},
        project_id="omniarchon",
        user_id="system",
    )

    print(f"✅ Request payload created successfully")
    print(f"   Source Path: {payload.source_path}")
    print(f"   Language: {payload.language}")
    print(f"   Operation: {payload.operation_type.value}")
    print(f"   Options: {payload.options}")

    # Test validation
    try:
        invalid_payload = ModelCodeAnalysisRequestPayload(
            source_path="",  # Empty - should fail
            language="python",
        )
        print("❌ Validation should have failed for empty source_path")
        return False
    except ValueError as e:
        print(f"✅ Validation correctly rejected empty source_path")

    return True


def test_completed_payload_creation():
    """Test completion payload creation and validation."""
    print("\n" + "=" * 80)
    print("Test 2: Completed Payload Creation")
    print("=" * 80)

    payload = ModelCodeAnalysisCompletedPayload(
        source_path="src/test.py",
        quality_score=0.87,
        onex_compliance=0.92,
        issues_count=3,
        recommendations_count=5,
        processing_time_ms=1234.5,
        operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
        complexity_score=0.45,
        maintainability_score=0.78,
        results_summary={"total_lines": 245, "pattern_matches": ["onex_effect"]},
        cache_hit=False,
    )

    print(f"✅ Completion payload created successfully")
    print(f"   Quality Score: {payload.quality_score:.2f}")
    print(f"   ONEX Compliance: {payload.onex_compliance:.2f}")
    print(f"   Issues: {payload.issues_count}")
    print(f"   Recommendations: {payload.recommendations_count}")
    print(f"   Processing Time: {payload.processing_time_ms:.2f}ms")

    # Test validation (score must be 0.0-1.0)
    try:
        invalid_payload = ModelCodeAnalysisCompletedPayload(
            source_path="test.py",
            quality_score=1.5,  # Invalid - should fail
            onex_compliance=0.9,
            issues_count=0,
            recommendations_count=0,
            processing_time_ms=100.0,
            operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        )
        print("❌ Validation should have failed for quality_score > 1.0")
        return False
    except Exception as e:
        print(f"✅ Validation correctly rejected quality_score > 1.0")

    return True


def test_failed_payload_creation():
    """Test failure payload creation."""
    print("\n" + "=" * 80)
    print("Test 3: Failed Payload Creation")
    print("=" * 80)

    payload = ModelCodeAnalysisFailedPayload(
        operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        source_path="src/broken/file.py",
        error_message="Failed to parse Python code: unexpected EOF",
        error_code=EnumAnalysisErrorCode.PARSING_ERROR,
        retry_allowed=False,
        retry_count=0,
        processing_time_ms=456.7,
        error_details={"exception_type": "SyntaxError", "line_number": 42},
        suggested_action="Verify source code syntax is valid",
    )

    print(f"✅ Failure payload created successfully")
    print(f"   Error Code: {payload.error_code.value}")
    print(f"   Error Message: {payload.error_message}")
    print(f"   Retry Allowed: {payload.retry_allowed}")
    print(f"   Suggested Action: {payload.suggested_action}")

    return True


def test_event_envelope_creation():
    """Test event envelope creation."""
    print("\n" + "=" * 80)
    print("Test 4: Event Envelope Creation")
    print("=" * 80)

    # Create request event
    request_event = create_request_event(
        source_path="src/api/endpoints.py",
        language="python",
        operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        options={"include_metrics": True},
    )

    print(f"✅ Request event envelope created")
    print(f"   Event ID: {request_event['event_id']}")
    print(f"   Event Type: {request_event['event_type']}")
    print(f"   Correlation ID: {request_event['correlation_id']}")

    # Verify structure
    assert "event_id" in request_event
    assert "event_type" in request_event
    assert "correlation_id" in request_event
    assert "payload" in request_event
    assert "source" in request_event

    # Create completion event
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

    print(f"✅ Completion event envelope created")
    print(f"   Correlation ID: {completed_event['correlation_id']}")
    print(
        f"   Matches request: {completed_event['correlation_id'] == str(correlation_id)}"
    )

    # Verify correlation
    assert completed_event["correlation_id"] == str(correlation_id)

    return True


def test_topic_routing():
    """Test Kafka topic routing."""
    print("\n" + "=" * 80)
    print("Test 5: Kafka Topic Routing")
    print("=" * 80)

    # Test all event types
    topics = {
        "REQUEST": IntelligenceAdapterEventHelpers.get_kafka_topic(
            EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED, "development"
        ),
        "COMPLETED": IntelligenceAdapterEventHelpers.get_kafka_topic(
            EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED, "development"
        ),
        "FAILED": IntelligenceAdapterEventHelpers.get_kafka_topic(
            EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED, "development"
        ),
    }

    for event_type, topic in topics.items():
        print(f"   {event_type}: {topic}")
        assert topic.startswith("dev.archon-intelligence.intelligence.")
        assert topic.endswith(".v1")

    print(f"✅ All topic names correctly formatted")

    # Test production environment
    prod_topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
        EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED, "production"
    )
    print(f"\n   Production topic: {prod_topic}")
    assert prod_topic.startswith("production.")

    return True


def test_serialization_deserialization():
    """Test event serialization and deserialization."""
    print("\n" + "=" * 80)
    print("Test 6: Serialization/Deserialization")
    print("=" * 80)

    # Create event
    original_event = create_request_event(
        source_path="src/test.py",
        language="python",
        operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
    )

    # Serialize to JSON
    json_str = json.dumps(original_event, default=str)
    print(f"✅ Event serialized to JSON ({len(json_str)} bytes)")

    # Deserialize
    deserialized_event = json.loads(json_str)
    print(f"✅ Event deserialized from JSON")

    # Type-safe deserialization
    event_type, typed_payload = IntelligenceAdapterEventHelpers.deserialize_event(
        deserialized_event
    )

    print(f"   Event Type: {event_type}")
    print(f"   Payload Type: {type(typed_payload).__name__}")
    print(f"   Source Path: {typed_payload.source_path}")

    assert event_type == EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value
    assert isinstance(typed_payload, ModelCodeAnalysisRequestPayload)
    assert typed_payload.source_path == "src/test.py"

    print(f"✅ Type-safe deserialization successful")

    return True


def test_correlation_tracking():
    """Test correlation ID tracking through event flow."""
    print("\n" + "=" * 80)
    print("Test 7: Correlation ID Tracking")
    print("=" * 80)

    # Create request
    request = create_request_event(
        source_path="src/test.py",
        language="python",
    )
    correlation_id = UUID(request["correlation_id"])

    print(f"   Request Correlation ID: {correlation_id}")

    # Create completion (same correlation ID)
    completed = create_completed_event(
        source_path="src/test.py",
        quality_score=0.9,
        onex_compliance=0.85,
        issues_count=0,
        recommendations_count=2,
        processing_time_ms=100.0,
        operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        correlation_id=correlation_id,
    )

    print(f"   Completion Correlation ID: {completed['correlation_id']}")

    # Create failure (same correlation ID)
    failed = create_failed_event(
        operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        source_path="src/test.py",
        error_message="Test error",
        error_code=EnumAnalysisErrorCode.INTERNAL_ERROR,
        correlation_id=correlation_id,
    )

    print(f"   Failure Correlation ID: {failed['correlation_id']}")

    # Verify all use same correlation ID
    assert completed["correlation_id"] == str(correlation_id)
    assert failed["correlation_id"] == str(correlation_id)

    print(f"✅ Correlation ID tracking successful across all event types")

    return True


def run_all_tests():
    """Run all validation tests."""
    print("\n" + "=" * 80)
    print("Intelligence Adapter Event Contracts - Validation Tests")
    print("=" * 80)

    tests = [
        test_request_payload_creation,
        test_completed_payload_creation,
        test_failed_payload_creation,
        test_event_envelope_creation,
        test_topic_routing,
        test_serialization_deserialization,
        test_correlation_tracking,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            result = test()
            if result or result is None:
                passed += 1
            else:
                failed += 1
                print(f"❌ Test failed: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"❌ Test error in {test.__name__}: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed == 0:
        print("\n✅ All validation tests passed!")
        print("\n📦 Intelligence Adapter Event Contracts are production ready!")
    else:
        print(f"\n❌ {failed} test(s) failed")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
