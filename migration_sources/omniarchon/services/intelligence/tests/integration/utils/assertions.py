#!/usr/bin/env python3
"""
Common assertion utilities for integration tests.

Provides reusable assertion functions to validate:
- Response payload structure and types
- Topic naming conventions
- Correlation ID preservation
- Routing context configuration
- Error response formats

Author: Archon Intelligence Team
Date: 2025-10-15
"""

from typing import Any, Dict, List, Optional

from events.models.model_event import ModelEvent
from events.models.model_routing_context import ModelRoutingContext


def assert_response_structure(
    payload: Dict[str, Any],
    required_fields: List[str],
    field_types: Optional[Dict[str, type]] = None,
):
    """
    Verify response payload has required structure.

    Args:
        payload: Response payload dictionary to validate
        required_fields: List of field names that must exist in payload
        field_types: Optional dict mapping field names to expected types

    Raises:
        AssertionError: If required fields are missing or types don't match

    Example:
        assert_response_structure(
            payload,
            required_fields=["concepts", "entities", "confidence"],
            field_types={"concepts": list, "confidence": float}
        )
    """
    for field in required_fields:
        assert field in payload, f"Missing required field: {field}"

    if field_types:
        for field, expected_type in field_types.items():
            if field in payload:
                assert isinstance(
                    payload[field], expected_type
                ), f"Field {field} should be {expected_type}, got {type(payload[field])}"


def assert_topic_naming(topic: str, expected_type: str):
    """
    Verify response topic follows naming convention.

    Topic format: omninode.codegen.response.<type>.v1

    Args:
        topic: Topic string to validate
        expected_type: Expected type segment (e.g., "analyze", "pattern", "mixin")

    Raises:
        AssertionError: If topic doesn't follow naming convention

    Example:
        assert_topic_naming("omninode.codegen.response.analyze.v1", "analyze")
    """
    expected_topic = f"omninode.codegen.response.{expected_type}.v1"
    assert topic == expected_topic, f"Expected topic {expected_topic}, got {topic}"
    assert topic.startswith(
        "omninode.codegen.response."
    ), "Topic missing required prefix"
    assert topic.endswith(".v1"), "Topic missing version suffix"


def assert_correlation_id_preserved(event: ModelEvent, original_correlation_id: str):
    """
    Verify correlation ID is preserved in response.

    Args:
        event: Response event to validate
        original_correlation_id: Original correlation ID from request

    Raises:
        AssertionError: If correlation ID doesn't match

    Example:
        assert_correlation_id_preserved(response_event, request.correlation_id)
    """
    assert (
        str(event.correlation_id) == original_correlation_id
    ), f"Correlation ID mismatch: expected {original_correlation_id}, got {event.correlation_id}"


def assert_routing_context(
    context: ModelRoutingContext,
    requires_persistence: bool = True,
    is_cross_service: bool = True,
):
    """
    Verify routing context structure and configuration.

    Args:
        context: Routing context to validate
        requires_persistence: Expected persistence flag (default: True)
        is_cross_service: Expected cross-service flag (default: True)

    Raises:
        AssertionError: If context doesn't match expected configuration

    Example:
        assert_routing_context(
            publish_call[1]["context"],
            requires_persistence=True,
            is_cross_service=True
        )
    """
    assert isinstance(
        context, ModelRoutingContext
    ), f"Expected ModelRoutingContext, got {type(context)}"
    assert (
        context.requires_persistence is requires_persistence
    ), f"Expected requires_persistence={requires_persistence}, got {context.requires_persistence}"
    assert (
        context.is_cross_service is is_cross_service
    ), f"Expected is_cross_service={is_cross_service}, got {context.is_cross_service}"


def assert_error_response(payload: Dict[str, Any], expected_error_substring: str):
    """
    Verify error response structure.

    Error responses should have:
    - "details" dict containing error information
    - "error" field within details with error message

    Args:
        payload: Response payload to validate
        expected_error_substring: Substring that should appear in error message

    Raises:
        AssertionError: If error structure is invalid or message doesn't match

    Example:
        assert_error_response(payload, "Missing required field")
    """
    assert "details" in payload, "Error response missing 'details' field"
    assert (
        "error" in payload["details"]
    ), "Error response missing 'error' field in details"
    error_message = payload["details"]["error"]
    assert (
        expected_error_substring in error_message
    ), f"Expected error containing '{expected_error_substring}', got: {error_message}"


def assert_publish_called_with_key(publish_call, expected_key: str):
    """
    Verify publish was called with correct key.

    Args:
        publish_call: Mock publish call args
        expected_key: Expected partition key value

    Raises:
        AssertionError: If key doesn't match

    Example:
        publish_call = mock_router.publish.call_args
        assert_publish_called_with_key(publish_call, correlation_id)
    """
    actual_key = publish_call[1]["key"]
    assert (
        actual_key == expected_key
    ), f"Expected partition key {expected_key}, got {actual_key}"


def assert_unique_correlation_ids(publish_calls, expected_count: int):
    """
    Verify all published events have unique correlation IDs.

    Args:
        publish_calls: List of publish call args from mock_router.publish.call_args_list
        expected_count: Expected number of unique correlation IDs

    Raises:
        AssertionError: If correlation IDs are not unique or count doesn't match

    Example:
        assert_unique_correlation_ids(mock_router.publish.call_args_list, 10)
    """
    published_correlation_ids = set()
    for call in publish_calls:
        event = call[1]["event"]
        published_correlation_ids.add(str(event.correlation_id))

    assert (
        len(published_correlation_ids) == expected_count
    ), f"Expected {expected_count} unique correlation IDs, got {len(published_correlation_ids)}"


def assert_metrics_tracking(
    metrics: Dict[str, Any],
    expected_events_handled: int,
    expected_events_failed: int,
    expected_handler_name: str,
):
    """
    Verify handler metrics are tracked correctly.

    Args:
        metrics: Metrics dictionary from handler.get_metrics()
        expected_events_handled: Expected number of events handled
        expected_events_failed: Expected number of failed events
        expected_handler_name: Expected handler name

    Raises:
        AssertionError: If metrics don't match expectations

    Example:
        metrics = handler.get_metrics()
        assert_metrics_tracking(metrics, 2, 0, "CodegenAnalysisHandler")
    """
    assert (
        metrics["events_handled"] == expected_events_handled
    ), f"Expected {expected_events_handled} events handled, got {metrics['events_handled']}"
    assert (
        metrics["events_failed"] == expected_events_failed
    ), f"Expected {expected_events_failed} events failed, got {metrics['events_failed']}"
    assert (
        metrics["handler_name"] == expected_handler_name
    ), f"Expected handler_name={expected_handler_name}, got {metrics['handler_name']}"

    # Verify success rate calculation
    if expected_events_handled > 0:
        expected_success_rate = (
            expected_events_handled - expected_events_failed
        ) / expected_events_handled
        assert (
            abs(metrics["success_rate"] - expected_success_rate) < 0.01
        ), f"Expected success_rate={expected_success_rate}, got {metrics['success_rate']}"

    # Verify avg_processing_time_ms exists and is positive
    assert (
        "avg_processing_time_ms" in metrics
    ), "Missing avg_processing_time_ms in metrics"
    if expected_events_handled > 0:
        assert (
            metrics["avg_processing_time_ms"] > 0
        ), "avg_processing_time_ms should be positive"
