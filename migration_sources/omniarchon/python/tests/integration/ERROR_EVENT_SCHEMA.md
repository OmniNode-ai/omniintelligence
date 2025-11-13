# Error Event Schema Expectations

**Version**: 1.0.0
**Created**: 2025-10-23
**Purpose**: Define error event structures and validation requirements for integration tests

---

## Overview

This document specifies the error event schema expectations for all integration tests in the Archon project. These schemas ensure consistent error handling and validation across all services and test suites.

## Table of Contents

1. [Event Envelope Error Structure](#event-envelope-error-structure)
2. [API Error Response Structure](#api-error-response-structure)
3. [Rollback Event Structure](#rollback-event-structure)
4. [Exception Handling Standards](#exception-handling-standards)
5. [Error Codes Reference](#error-codes-reference)
6. [Validation Utilities](#validation-utilities)
7. [Examples](#examples)

---

## 1. Event Envelope Error Structure

Error events following the ModelEventEnvelope pattern for event-driven systems.

### Required Fields

```json
{
  "event_id": "UUID (v4)",
  "event_type": "omninode.{domain}.{pattern}.{operation}.v{version}",
  "correlation_id": "UUID (v4)",
  "causation_id": "UUID (v4) | null",
  "timestamp": "ISO 8601 datetime with UTC timezone",
  "version": "semantic version (e.g., 1.0.0)",
  "source": {
    "service": "string (service name)",
    "instance_id": "string (instance identifier)",
    "hostname": "string (optional)"
  },
  "metadata": {
    "trace_id": "32 hex digits (OpenTelemetry format)",
    "span_id": "16 hex digits (OpenTelemetry format)",
    "user_id": "string (optional)",
    "tenant_id": "string (optional)",
    "extra": {}
  },
  "payload": {
    "status": "FAILED",
    "error_code": "string from CoreErrorCode enum",
    "error_message": "string (descriptive error message)",
    "stack_trace": "string (optional, for exceptions)",
    "error_context": "dict (optional, additional metadata)"
  }
}
```

### Field Specifications

#### Event Envelope Fields

- **event_id**: UUID v4 format, uniquely identifies the event
- **event_type**: Must match pattern `^omninode\.[a-z_]+\.(request|response|event|audit)\.[a-z_]+\.v\d+$`
- **correlation_id**: UUID v4 format, links related events in a flow
- **causation_id**: UUID v4 format or null, identifies the event that caused this one
- **timestamp**: ISO 8601 format with millisecond precision and UTC timezone
- **version**: Semantic versioning format `^\d+\.\d+\.\d+$`

#### Error Payload Fields

- **status**: MUST be "FAILED" for error events (alternatives: "failed", "ERROR", "error")
- **error_code**: MUST be one of the valid CoreErrorCode values (see Error Codes Reference)
- **error_message**: MUST be non-empty string, descriptive and actionable
- **stack_trace** (optional): Present for exceptions, must contain valid traceback information
- **error_context** (optional): Dictionary with additional debugging context

### Validation Requirements

✅ **REQUIRED Validations**:
- Event envelope structure follows ModelEventEnvelope pattern
- All required fields are present
- Field types match specifications
- Event type matches naming pattern
- Status is a valid failure status
- Error code is from CoreErrorCode enum
- Error message is non-empty and descriptive

⚠️  **OPTIONAL Validations** (when applicable):
- Stack trace contains valid traceback indicators
- Error context provides useful debugging information
- Correlation ID links to related events

---

## 2. API Error Response Structure

HTTP error responses from REST API endpoints.

### Format 1: Simple Detail String

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Format 2: Structured Detail

```json
{
  "detail": {
    "error": "Error message",
    "error_code": "ERROR_CODE_STRING",
    "suggestion": "Actionable suggestion for resolution"
  }
}
```

### Format 3: Structured Error Object

```json
{
  "success": false,
  "error": {
    "type": "error_type (e.g., validation_error, connection_error)",
    "message": "Error message",
    "details": {
      "field": "Additional context",
      "exception_type": "ExceptionClassName"
    },
    "suggestion": "Actionable suggestion",
    "http_status": 500
  }
}
```

### HTTP Status Codes

- **4xx Client Errors**:
  - `400`: Bad request, invalid parameters
  - `401`: Authentication failed
  - `403`: Authorization failed
  - `404`: Resource not found
  - `409`: Conflict with current state
  - `422`: Validation error

- **5xx Server Errors**:
  - `500`: Internal server error
  - `502`: Backend service unavailable
  - `503`: Service temporarily unavailable
  - `504`: Gateway timeout

### Validation Requirements

✅ **REQUIRED Validations**:
- Status code is >= 400
- Response body is valid JSON
- Contains error information (detail, error, or success field)
- Error message is non-empty string
- Error message describes the issue

⚠️  **OPTIONAL Validations** (when applicable):
- Structured errors include type and details
- Suggestion field provides actionable guidance
- HTTP status matches error type

---

## 3. Rollback Event Structure

Events for optimistic update rollback scenarios.

### Creation Failure Rollback

```json
{
  "type": "knowledge_item_creation_failed",
  "data": {
    "item_id": "string (item being rolled back)",
    "error": "string (reason for failure)",
    "rollback": true,
    "session_id": "string (session identifier)"
  },
  "timestamp": "ISO 8601 datetime"
}
```

### Update Conflict Rollback

```json
{
  "type": "knowledge_item_update_conflict",
  "data": {
    "item_id": "string (item being rolled back)",
    "conflict_reason": "string (detailed conflict description)",
    "server_state": {
      "id": "string",
      // ... current server state
    },
    "rollback_to_server": true,
    "session_id": "string (session identifier)"
  },
  "timestamp": "ISO 8601 datetime"
}
```

### Field Specifications

- **rollback / rollback_to_server**: Boolean flag, MUST be true
- **item_id**: MUST be present, identifies the item being rolled back
- **error / conflict_reason**: MUST be present, describes why rollback is needed
- **server_state** (for conflicts): MUST include current server state for rollback

### Validation Requirements

✅ **REQUIRED Validations**:
- Rollback flag is present and true
- Item ID is present and valid
- Error/conflict reason is descriptive
- Event type indicates failure/conflict

⚠️  **OPTIONAL Validations** (when applicable):
- Server state provided for conflict resolution
- Session ID links to original optimistic update

---

## 4. Exception Handling Standards

Standards for exception handling and validation.

### Exception Properties

```python
try:
    # Operation that may fail
    result = perform_operation()
except Exception as e:
    # Exception should have:
    # - Non-empty message: str(e) != ""
    # - Appropriate type: isinstance(e, ExpectedException)
    # - Cause chain: e.__cause__ (for chained exceptions)
    pass
```

### Validation Requirements

✅ **REQUIRED Validations**:
- Exception is caught and handled
- Exception message is non-empty
- Exception type matches expected type (when specified)
- Message contains expected keywords

⚠️  **OPTIONAL Validations** (when applicable):
- Exception has __cause__ for chained exceptions
- Exception includes context attributes

---

## 5. Error Codes Reference

### CoreErrorCode Enum Values

| Error Code | Description | HTTP Status | Use Case |
|------------|-------------|-------------|----------|
| `AUTHENTICATION_FAILED` | Authentication failed | 401 | Invalid credentials, expired tokens |
| `AUTHORIZATION_FAILED` | Authorization failed | 403 | Insufficient permissions |
| `VALIDATION_ERROR` | Input validation failed | 422 | Invalid request parameters |
| `INTERNAL_ERROR` | Internal server error | 500 | Unexpected server-side errors |
| `SERVICE_UNAVAILABLE` | Service unavailable | 503 | Backend service down |
| `INVALID_REQUEST` | Invalid request format | 400 | Malformed request |
| `RESOURCE_NOT_FOUND` | Resource not found | 404 | Requested resource doesn't exist |
| `RATE_LIMIT_EXCEEDED` | Rate limit exceeded | 429 | Too many requests |

### Error Code Usage Guidelines

- Use most specific error code available
- Include descriptive error_message with context
- Provide error_context for debugging when possible
- Chain exceptions properly for root cause analysis

---

## 6. Validation Utilities

### ErrorAssertions Class

Comprehensive validation utilities available in `tests/integration/error_assertions.py`.

#### Key Methods

```python
from tests.integration.error_assertions import ErrorAssertions

# Validate error event envelope
ErrorAssertions.assert_error_event(
    event,
    expected_status="FAILED",
    expected_error_code="VALIDATION_ERROR",
    should_have_stack_trace=True
)

# Validate API error response
ErrorAssertions.assert_api_error_response(
    response,
    expected_status_code=500,
    expected_error_message_contains="Database connection failed"
)

# Validate exception handling
ErrorAssertions.assert_exception_handling(
    exception,
    expected_exception_type=ValueError,
    expected_message_contains="Invalid input"
)

# Validate rollback event
ErrorAssertions.assert_rollback_event(
    event,
    expected_item_id="item_123",
    expected_rollback_reason="Backend service error"
)
```

#### Convenience Functions

```python
from tests.integration.error_assertions import (
    assert_circuit_breaker_error,
    assert_service_unavailable_error,
    assert_api_error_with_detail,
    assert_rollback_event,
)

# Circuit breaker error
assert_circuit_breaker_error(exception)

# Service unavailable error
assert_service_unavailable_error(exception, "intelligence")

# API error with detail
assert_api_error_with_detail(response, 500, "Failed to fetch")

# Rollback event
assert_rollback_event(event, expected_item_id="123")
```

---

## 7. Examples

### Example 1: Circuit Breaker Error Validation

```python
@pytest.mark.asyncio
async def test_circuit_breaker_open_error(service):
    """Test circuit breaker blocks requests when open."""
    # Make service unavailable to trip circuit breaker
    service.set_health(ServiceHealth.UNAVAILABLE)

    # Trip the circuit breaker
    for _ in range(6):
        try:
            await service.search_documents("test")
        except Exception:
            pass

    # Verify circuit is open and requests are blocked
    try:
        await service.search_documents("blocked")
        pytest.fail("Should have been blocked")
    except Exception as e:
        # Enhanced error validation
        assert_circuit_breaker_error(e, "Circuit breaker is OPEN")
        ErrorAssertions.assert_exception_handling(
            e,
            expected_exception_type=Exception,
            expected_message_contains="service unavailable"
        )
```

### Example 2: API Error Response Validation

```python
def test_api_endpoint_error_handling(client):
    """Test API error response format and content."""
    # Make request that will fail
    response = client.get("/api/endpoint", params={"invalid": True})

    # Comprehensive error response validation
    ErrorAssertions.assert_api_error_response(
        response,
        expected_status_code=422,
        expected_error_message_contains="Invalid parameter",
        validate_json_structure=True
    )

    # Additional validation
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], (str, dict))
```

### Example 3: Rollback Event Validation

```python
@pytest.mark.asyncio
async def test_optimistic_update_rollback(websocket, service):
    """Test optimistic update rollback on failure."""
    # Send optimistic update
    await websocket.send_event("item_creating", {
        "item": test_item,
        "optimistic": True
    })

    # Simulate backend failure
    service.create_item.side_effect = Exception("Backend error")

    try:
        await service.create_item(test_item)
    except Exception as e:
        # Send rollback event
        await websocket.send_event("item_creation_failed", {
            "item_id": test_item["id"],
            "error": str(e),
            "rollback": True
        })

    # Validate rollback event
    events = websocket.get_client_events()
    rollback_event = events[-1]

    assert_rollback_event(
        rollback_event,
        expected_item_id=test_item["id"],
        expected_rollback_reason="Backend error"
    )

    # Additional validation
    assert rollback_event["data"]["rollback"] is True
    assert len(rollback_event["data"]["error"]) > 0
```

### Example 4: Event Envelope Error Validation

```python
def test_event_envelope_error_structure(event_queue):
    """Test error event follows envelope pattern."""
    # Trigger error event
    error_event = event_queue.get_next_error_event()

    # Comprehensive envelope validation
    ErrorAssertions.assert_error_event(
        error_event,
        expected_status="FAILED",
        expected_error_code="SERVICE_UNAVAILABLE",
        expected_error_message_contains="Connection refused",
        should_have_stack_trace=True,
        validate_envelope_structure=True
    )

    # Validate specific fields
    assert error_event["payload"]["status"] == "FAILED"
    assert "error_code" in error_event["payload"]
    assert "stack_trace" in error_event["payload"]
```

---

## Best Practices

### 1. Always Use Validation Utilities

✅ **DO**:
```python
ErrorAssertions.assert_api_error_response(response, expected_status_code=500)
```

❌ **DON'T**:
```python
assert response.status_code == 500
assert "error" in response.json()
```

### 2. Validate Error Message Content

✅ **DO**:
```python
ErrorAssertions.assert_exception_handling(
    exception,
    expected_message_contains="Database connection failed"
)
```

❌ **DON'T**:
```python
assert "error" in str(exception)
```

### 3. Check Error Event Structure

✅ **DO**:
```python
assert_rollback_event(
    event,
    expected_item_id=item_id,
    should_have_original_state=True
)
```

❌ **DON'T**:
```python
assert event["data"]["rollback"] == True
```

### 4. Provide Descriptive Failure Messages

✅ **DO**:
```python
assert error_msg, f"Expected error message, got empty string for {endpoint}"
```

❌ **DON'T**:
```python
assert error_msg
```

---

## Testing Checklist

When writing error handling tests, ensure you:

- [ ] Use ErrorAssertions helper methods
- [ ] Validate error status codes and types
- [ ] Check error message content and clarity
- [ ] Verify error context provides debugging info
- [ ] Test error propagation through layers
- [ ] Validate rollback events for optimistic updates
- [ ] Check exception chaining for root cause
- [ ] Ensure error responses are consistent
- [ ] Test error scenarios for all failure paths
- [ ] Document expected error behavior in docstrings

---

## Maintenance

### Version History

- **1.0.0** (2025-10-23): Initial error event schema documentation
  - Defined event envelope error structure
  - Documented API error response formats
  - Specified rollback event requirements
  - Added validation utilities reference

### Future Enhancements

- [ ] Add error rate limiting validation
- [ ] Define error aggregation patterns
- [ ] Specify error recovery workflows
- [ ] Add distributed tracing integration
- [ ] Define error analytics requirements

---

## References

- [ModelEventEnvelope](../../src/events/models/model_event_envelope.py) - Event envelope implementation
- [OnexError](../../src/server/exceptions/onex_error.py) - Error class definitions
- [MCPErrorFormatter](../../src/mcp_server/utils/error_handling.py) - MCP error formatting
- [ErrorAssertions](./error_assertions.py) - Validation utilities
- [EVENT_BUS_ARCHITECTURE.md](../../docs/EVENT_BUS_ARCHITECTURE.md) - Event bus specification

---

**Questions or Issues?** Contact the Archon development team or file an issue on GitHub.
