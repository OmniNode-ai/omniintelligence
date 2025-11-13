"""
Unit tests for external API response validation.

Tests cover:
- Valid responses from intelligence, Supabase, and Memgraph services
- Malformed responses (missing fields, wrong types, invalid values)
- Edge cases (empty arrays, null values, boundary conditions)
- Security scenarios (injection attempts, oversized data)
"""

from datetime import datetime

import pytest
from models.external_api_models import (
    ExternalAPIValidationError,
    IntelligenceDocumentProcessingResponse,
    IntelligenceEntityResponse,
    IntelligenceExtractionResponse,
    IntelligenceHealthResponse,
    MemgraphQueryResult,
    MemgraphSingleRecordResult,
    SupabaseQueryResultData,
    SupabaseRowData,
    validate_intelligence_response,
    validate_memgraph_result,
    validate_supabase_result,
)
from pydantic import ValidationError

# ============================================================================
# Intelligence Service Response Validation Tests
# ============================================================================


class TestIntelligenceEntityResponse:
    """Test validation of individual entity responses."""

    def test_valid_entity_response(self):
        """Test valid entity response passes validation."""
        data = {
            "entity_id": "entity_123",
            "entity_type": "function",
            "name": "process_data",
            "confidence_score": 0.95,
            "properties": {"language": "python", "complexity": 5},
        }
        entity = IntelligenceEntityResponse.model_validate(data)
        assert entity.entity_id == "entity_123"
        assert entity.confidence_score == 0.95

    def test_entity_missing_required_field(self):
        """Test validation fails when required field is missing."""
        data = {
            "entity_id": "entity_123",
            # Missing entity_type
            "name": "process_data",
            "confidence_score": 0.95,
        }
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceEntityResponse.model_validate(data)
        assert "entity_type" in str(exc_info.value)

    def test_entity_invalid_confidence_score(self):
        """Test validation fails when confidence score is out of range."""
        data = {
            "entity_id": "entity_123",
            "entity_type": "function",
            "name": "process_data",
            "confidence_score": 1.5,  # Invalid: > 1.0
        }
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceEntityResponse.model_validate(data)
        assert "confidence_score" in str(exc_info.value)

    def test_entity_negative_confidence_score(self):
        """Test validation fails when confidence score is negative."""
        data = {
            "entity_id": "entity_123",
            "entity_type": "function",
            "name": "process_data",
            "confidence_score": -0.1,  # Invalid: < 0.0
        }
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceEntityResponse.model_validate(data)
        assert "confidence_score" in str(exc_info.value)

    def test_entity_empty_string_fields(self):
        """Test validation fails when required string fields are empty."""
        data = {
            "entity_id": "",  # Empty string
            "entity_type": "function",
            "name": "process_data",
            "confidence_score": 0.95,
        }
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceEntityResponse.model_validate(data)
        assert "entity_id" in str(exc_info.value)

    def test_entity_whitespace_only_fields(self):
        """Test validation fails when string fields contain only whitespace."""
        data = {
            "entity_id": "entity_123",
            "entity_type": "   ",  # Whitespace only
            "name": "process_data",
            "confidence_score": 0.95,
        }
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceEntityResponse.model_validate(data)
        assert "entity_type" in str(exc_info.value)

    def test_entity_wrong_type(self):
        """Test validation fails when field has wrong type."""
        data = {
            "entity_id": 123,  # Should be string
            "entity_type": "function",
            "name": "process_data",
            "confidence_score": 0.95,
        }
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceEntityResponse.model_validate(data)
        assert "entity_id" in str(exc_info.value)

    def test_entity_extra_fields_forbidden(self):
        """Test that extra fields are forbidden in strict mode."""
        data = {
            "entity_id": "entity_123",
            "entity_type": "function",
            "name": "process_data",
            "confidence_score": 0.95,
            "extra_field": "should_be_rejected",  # Extra field
        }
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceEntityResponse.model_validate(data)
        assert (
            "extra_field" in str(exc_info.value).lower()
            or "extra" in str(exc_info.value).lower()
        )


class TestIntelligenceExtractionResponse:
    """Test validation of extraction endpoint responses."""

    def test_valid_extraction_response(self):
        """Test valid extraction response passes validation."""
        data = {
            "entities": [
                {
                    "entity_id": "entity_1",
                    "entity_type": "function",
                    "name": "func_1",
                    "confidence_score": 0.9,
                }
            ],
            "entities_extracted": 1,
            "status": "success",
        }
        response = IntelligenceExtractionResponse.model_validate(data)
        assert len(response.entities) == 1
        assert response.entities_extracted == 1

    def test_extraction_response_empty_entities(self):
        """Test valid extraction response with no entities."""
        data = {"entities": [], "entities_extracted": 0, "status": "success"}
        response = IntelligenceExtractionResponse.model_validate(data)
        assert len(response.entities) == 0
        assert response.entities_extracted == 0

    def test_extraction_response_count_mismatch(self):
        """Test validation fails when entity count doesn't match array length."""
        data = {
            "entities": [
                {
                    "entity_id": "entity_1",
                    "entity_type": "function",
                    "name": "func_1",
                    "confidence_score": 0.9,
                }
            ],
            "entities_extracted": 5,  # Mismatch: actual is 1
            "status": "success",
        }
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceExtractionResponse.model_validate(data)
        assert "entities_extracted" in str(exc_info.value)

    def test_extraction_response_invalid_entity(self):
        """Test validation fails when entity in array is invalid."""
        data = {
            "entities": [
                {
                    "entity_id": "entity_1",
                    # Missing required fields
                    "name": "func_1",
                }
            ],
            "status": "success",
        }
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceExtractionResponse.model_validate(data)
        assert "entity_type" in str(exc_info.value) or "confidence_score" in str(
            exc_info.value
        )

    def test_extraction_response_negative_count(self):
        """Test validation fails when entity count is negative."""
        data = {"entities": [], "entities_extracted": -1, "status": "success"}
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceExtractionResponse.model_validate(data)
        assert "entities_extracted" in str(exc_info.value)

    def test_extraction_response_minimal_valid(self):
        """Test minimal valid extraction response (only entities array)."""
        data = {"entities": []}
        response = IntelligenceExtractionResponse.model_validate(data)
        assert len(response.entities) == 0
        assert response.status is None  # Optional field


class TestIntelligenceDocumentProcessingResponse:
    """Test validation of document processing endpoint responses."""

    def test_valid_document_processing_response(self):
        """Test valid document processing response passes validation."""
        data = {
            "entities_extracted": 10,
            "status": "completed",
            "document_id": "doc_123",
            "project_id": "proj_456",
        }
        response = IntelligenceDocumentProcessingResponse.model_validate(data)
        assert response.entities_extracted == 10
        assert response.status == "completed"

    def test_document_processing_missing_required_field(self):
        """Test validation fails when required field is missing."""
        data = {
            # Missing entities_extracted
            "status": "completed",
        }
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceDocumentProcessingResponse.model_validate(data)
        assert "entities_extracted" in str(exc_info.value)

    def test_document_processing_empty_status(self):
        """Test validation fails when status is empty string."""
        data = {"entities_extracted": 10, "status": ""}
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceDocumentProcessingResponse.model_validate(data)
        assert "status" in str(exc_info.value)

    def test_document_processing_with_error(self):
        """Test valid document processing response with error field."""
        data = {
            "entities_extracted": 0,
            "status": "failed",
            "error": "Document processing timeout",
        }
        response = IntelligenceDocumentProcessingResponse.model_validate(data)
        assert response.error == "Document processing timeout"


class TestIntelligenceHealthResponse:
    """Test validation of health check responses."""

    def test_valid_health_response(self):
        """Test valid health response passes validation."""
        data = {"status": "healthy", "service": "intelligence", "version": "1.0.0"}
        response = IntelligenceHealthResponse.model_validate(data)
        assert response.status == "healthy"

    def test_health_response_invalid_status(self):
        """Test validation fails for invalid status value."""
        data = {"status": "unknown_status"}
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceHealthResponse.model_validate(data)
        assert "status" in str(exc_info.value)

    def test_health_response_case_insensitive(self):
        """Test health status validation is case-insensitive."""
        data = {"status": "HEALTHY"}
        response = IntelligenceHealthResponse.model_validate(data)
        assert response.status == "healthy"  # Normalized to lowercase

    def test_health_response_degraded(self):
        """Test valid degraded health status."""
        data = {"status": "degraded", "uptime_seconds": 3600.5}
        response = IntelligenceHealthResponse.model_validate(data)
        assert response.status == "degraded"

    def test_health_response_negative_uptime(self):
        """Test validation fails for negative uptime."""
        data = {"status": "healthy", "uptime_seconds": -100.0}
        with pytest.raises(ValidationError) as exc_info:
            IntelligenceHealthResponse.model_validate(data)
        assert "uptime_seconds" in str(exc_info.value)


# ============================================================================
# Supabase Response Validation Tests
# ============================================================================


class TestSupabaseQueryResultData:
    """Test validation of Supabase query result data."""

    def test_valid_supabase_result(self):
        """Test valid Supabase result passes validation."""
        data = {
            "data": [{"id": "1", "name": "Test"}, {"id": "2", "name": "Test2"}],
            "count": 2,
        }
        result = SupabaseQueryResultData.model_validate(data)
        assert len(result.data) == 2
        assert result.count == 2

    def test_supabase_result_empty_data(self):
        """Test valid Supabase result with empty data array."""
        data = {"data": [], "count": 0}
        result = SupabaseQueryResultData.model_validate(data)
        assert len(result.data) == 0
        assert result.count == 0

    def test_supabase_result_count_less_than_data(self):
        """Test validation fails when count is less than data length."""
        data = {"data": [{"id": "1"}, {"id": "2"}], "count": 1}
        with pytest.raises(ValidationError) as exc_info:
            SupabaseQueryResultData.model_validate(data)
        assert "count" in str(exc_info.value)

    def test_supabase_result_count_greater_than_data(self):
        """Test valid when count is greater than data length (pagination)."""
        data = {"data": [{"id": "1"}], "count": 100}  # Total count > page size
        result = SupabaseQueryResultData.model_validate(data)
        assert result.count == 100  # Valid for pagination

    def test_supabase_result_with_error(self):
        """Test valid Supabase result with error information."""
        data = {"data": [], "error": {"message": "Query failed", "code": "ERR_001"}}
        result = SupabaseQueryResultData.model_validate(data)
        assert result.error is not None

    def test_supabase_result_negative_count(self):
        """Test validation fails when count is negative."""
        data = {"data": [], "count": -1}
        with pytest.raises(ValidationError) as exc_info:
            SupabaseQueryResultData.model_validate(data)
        assert "count" in str(exc_info.value)


class TestSupabaseRowData:
    """Test validation of Supabase row data."""

    def test_valid_supabase_row(self):
        """Test valid Supabase row passes validation."""
        data = {
            "id": "row_123",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T12:00:00Z",
            "custom_field": "custom_value",
        }
        row = SupabaseRowData.model_validate(data)
        assert row.id == "row_123"

    def test_supabase_row_missing_id(self):
        """Test validation fails when id is missing."""
        data = {"created_at": "2024-01-15T10:30:00Z"}
        with pytest.raises(ValidationError) as exc_info:
            SupabaseRowData.model_validate(data)
        assert "id" in str(exc_info.value)

    def test_supabase_row_invalid_timestamp(self):
        """Test validation fails when timestamp is invalid format."""
        data = {
            "id": "row_123",
            "created_at": "not-a-timestamp",
        }
        with pytest.raises(ValidationError) as exc_info:
            SupabaseRowData.model_validate(data)
        assert "created_at" in str(exc_info.value)

    def test_supabase_row_integer_id(self):
        """Test valid Supabase row with integer ID."""
        data = {"id": 123, "created_at": "2024-01-15T10:30:00Z"}
        row = SupabaseRowData.model_validate(data)
        assert row.id == 123

    def test_supabase_row_no_updated_at(self):
        """Test valid Supabase row without updated_at (optional field)."""
        data = {"id": "row_123", "created_at": "2024-01-15T10:30:00Z"}
        row = SupabaseRowData.model_validate(data)
        assert row.updated_at is None


# ============================================================================
# Memgraph Response Validation Tests
# ============================================================================


class TestMemgraphQueryResult:
    """Test validation of Memgraph query results."""

    def test_valid_memgraph_result(self):
        """Test valid Memgraph result passes validation."""
        data = {
            "records": [
                {"id": "node_1", "label": "Person", "name": "Alice"},
                {"id": "node_2", "label": "Person", "name": "Bob"},
            ]
        }
        result = MemgraphQueryResult.model_validate(data)
        assert len(result.records) == 2

    def test_memgraph_result_empty_records(self):
        """Test valid Memgraph result with empty records array."""
        data = {"records": []}
        result = MemgraphQueryResult.model_validate(data)
        assert len(result.records) == 0

    def test_memgraph_result_non_dict_record(self):
        """Test validation fails when record is not a dictionary."""
        data = {"records": ["not_a_dict", {"id": "node_1"}]}
        with pytest.raises(ValidationError) as exc_info:
            MemgraphQueryResult.model_validate(data)
        assert "record" in str(exc_info.value).lower()

    def test_memgraph_result_with_summary(self):
        """Test valid Memgraph result with execution summary."""
        data = {
            "records": [{"id": "node_1"}],
            "summary": {"execution_time_ms": 45, "nodes_created": 1},
        }
        result = MemgraphQueryResult.model_validate(data)
        assert result.summary is not None


class TestMemgraphSingleRecordResult:
    """Test validation of Memgraph single record results."""

    def test_valid_single_record(self):
        """Test valid single record result passes validation."""
        data = {"record": {"id": "node_123", "name": "Test Node"}}
        result = MemgraphSingleRecordResult.model_validate(data)
        assert result.record["id"] == "node_123"

    def test_single_record_null(self):
        """Test valid single record result with null (no result)."""
        data = {"record": None}
        result = MemgraphSingleRecordResult.model_validate(data)
        assert result.record is None

    def test_single_record_non_dict(self):
        """Test validation fails when single record is not a dict."""
        data = {"record": "not_a_dict"}
        with pytest.raises(ValidationError) as exc_info:
            MemgraphSingleRecordResult.model_validate(data)
        assert "record" in str(exc_info.value).lower()


# ============================================================================
# Validation Utility Function Tests
# ============================================================================


class TestValidateIntelligenceResponse:
    """Test intelligence response validation utility function."""

    def test_validate_extraction_response(self):
        """Test validation of extraction endpoint response."""
        data = {"entities": [], "status": "success"}
        result = validate_intelligence_response(data, "/extract/code")
        assert isinstance(result, IntelligenceExtractionResponse)

    def test_validate_document_processing_response(self):
        """Test validation of document processing endpoint response."""
        data = {"entities_extracted": 5, "status": "completed"}
        result = validate_intelligence_response(data, "/process/document")
        assert isinstance(result, IntelligenceDocumentProcessingResponse)

    def test_validate_health_response(self):
        """Test validation of health endpoint response."""
        data = {"status": "healthy"}
        result = validate_intelligence_response(data, "/health")
        assert isinstance(result, IntelligenceHealthResponse)

    def test_validate_unknown_endpoint(self):
        """Test validation fails for unknown endpoint."""
        data = {"some": "data"}
        with pytest.raises(ValueError) as exc_info:
            validate_intelligence_response(data, "/unknown/endpoint")
        assert "unknown" in str(exc_info.value).lower()

    def test_validate_invalid_response_data(self):
        """Test validation fails for invalid response data."""
        data = {"entities": "not_an_array"}  # Invalid type
        with pytest.raises(ValueError) as exc_info:
            validate_intelligence_response(data, "/extract/code")
        assert "validation failed" in str(exc_info.value).lower()


class TestValidateSupabaseResult:
    """Test Supabase result validation utility function."""

    def test_validate_result_object(self):
        """Test validation of Supabase result object."""

        class MockResult:
            def __init__(self):
                self.data = [{"id": "1"}]
                self.count = 1

        result = validate_supabase_result(MockResult())
        assert len(result.data) == 1

    def test_validate_result_dict(self):
        """Test validation of Supabase result dictionary."""
        data = {"data": [{"id": "1"}], "count": 1}
        result = validate_supabase_result(data)
        assert len(result.data) == 1

    def test_validate_with_expected_fields(self):
        """Test validation with expected fields check."""
        data = {"data": [{"id": "1", "name": "Test"}]}
        result = validate_supabase_result(data, expected_fields=["id", "name"])
        assert len(result.data) == 1

    def test_validate_missing_expected_fields(self):
        """Test validation fails when expected fields are missing."""
        data = {"data": [{"id": "1"}]}  # Missing "name" field
        with pytest.raises(ValueError) as exc_info:
            validate_supabase_result(data, expected_fields=["id", "name"])
        assert "missing expected fields" in str(exc_info.value).lower()


class TestValidateMemgraphResult:
    """Test Memgraph result validation utility function."""

    def test_validate_dict_records(self):
        """Test validation of dictionary records."""
        records = [{"id": "node_1"}, {"id": "node_2"}]
        result = validate_memgraph_result(records)
        assert len(result.records) == 2

    def test_validate_with_expected_keys(self):
        """Test validation with expected keys check."""
        records = [{"id": "node_1", "name": "Node"}]
        result = validate_memgraph_result(records, expected_keys=["id", "name"])
        assert len(result.records) == 1

    def test_validate_missing_expected_keys(self):
        """Test validation fails when expected keys are missing."""
        records = [{"id": "node_1"}]  # Missing "name" key
        with pytest.raises(ValueError) as exc_info:
            validate_memgraph_result(records, expected_keys=["id", "name"])
        assert "missing expected keys" in str(exc_info.value).lower()


# ============================================================================
# Security and Edge Case Tests
# ============================================================================


class TestSecurityValidation:
    """Test validation against security threats."""

    def test_sql_injection_in_string_field(self):
        """Test that SQL injection attempts in string fields are validated (not sanitized)."""
        # Note: Pydantic validates types/structure, not content
        # SQL injection prevention should be handled at database query level
        data = {
            "entity_id": "entity'; DROP TABLE users; --",
            "entity_type": "malicious",
            "name": "test",
            "confidence_score": 0.9,
        }
        entity = IntelligenceEntityResponse.model_validate(data)
        # Validation passes (type is correct), but database layer should sanitize
        assert entity.entity_id == "entity'; DROP TABLE users; --"

    def test_xss_attempt_in_string_field(self):
        """Test that XSS attempts in string fields pass validation."""
        # Note: XSS prevention should be handled at rendering/output layer
        data = {
            "entity_id": "entity_123",
            "entity_type": "<script>alert('xss')</script>",
            "name": "test",
            "confidence_score": 0.9,
        }
        entity = IntelligenceEntityResponse.model_validate(data)
        # Validation passes (type is correct), but output layer should escape
        assert "<script>" in entity.entity_type

    def test_extremely_large_array(self):
        """Test validation handles extremely large arrays."""
        # Create a large array (but not so large it causes memory issues in test)
        large_array = [
            {
                "entity_id": f"entity_{i}",
                "entity_type": "function",
                "name": f"func_{i}",
                "confidence_score": 0.9,
            }
            for i in range(1000)
        ]
        data = {"entities": large_array, "entities_extracted": 1000}
        response = IntelligenceExtractionResponse.model_validate(data)
        assert len(response.entities) == 1000

    def test_unicode_characters_in_fields(self):
        """Test validation handles unicode characters correctly."""
        data = {
            "entity_id": "entity_测试_123",
            "entity_type": "函数",
            "name": "тест_function_🔥",
            "confidence_score": 0.95,
        }
        entity = IntelligenceEntityResponse.model_validate(data)
        assert "测试" in entity.entity_id
        assert "🔥" in entity.name


class TestEdgeCases:
    """Test edge cases in validation."""

    def test_boundary_confidence_scores(self):
        """Test confidence score boundary values."""
        # Test 0.0 (minimum)
        data = {
            "entity_id": "entity_1",
            "entity_type": "function",
            "name": "test",
            "confidence_score": 0.0,
        }
        entity = IntelligenceEntityResponse.model_validate(data)
        assert entity.confidence_score == 0.0

        # Test 1.0 (maximum)
        data["confidence_score"] = 1.0
        entity = IntelligenceEntityResponse.model_validate(data)
        assert entity.confidence_score == 1.0

    def test_very_long_string_fields(self):
        """Test validation handles very long string values."""
        long_string = "a" * 10000
        data = {
            "entity_id": long_string,
            "entity_type": "function",
            "name": "test",
            "confidence_score": 0.9,
        }
        entity = IntelligenceEntityResponse.model_validate(data)
        assert len(entity.entity_id) == 10000

    def test_nested_properties(self):
        """Test validation handles deeply nested properties."""
        data = {
            "entity_id": "entity_1",
            "entity_type": "function",
            "name": "test",
            "confidence_score": 0.9,
            "properties": {
                "level1": {"level2": {"level3": {"level4": {"value": "deep_value"}}}}
            },
        }
        entity = IntelligenceEntityResponse.model_validate(data)
        assert (
            entity.properties["level1"]["level2"]["level3"]["level4"]["value"]
            == "deep_value"
        )

    def test_empty_properties_dict(self):
        """Test validation handles empty properties dictionary."""
        data = {
            "entity_id": "entity_1",
            "entity_type": "function",
            "name": "test",
            "confidence_score": 0.9,
            "properties": {},
        }
        entity = IntelligenceEntityResponse.model_validate(data)
        assert entity.properties == {}

    def test_null_values_in_optional_fields(self):
        """Test validation handles null values in optional fields."""
        data = {
            "entities": [],
            "entities_extracted": None,  # Optional field with null
            "status": None,  # Optional field with null
        }
        response = IntelligenceExtractionResponse.model_validate(data)
        assert response.entities_extracted is None
        assert response.status is None
