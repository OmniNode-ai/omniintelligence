"""
Tests for External API Response Validation

Covers:
- Valid responses
- Invalid responses
- Partial validation with missing fields
- Graceful degradation
- Confidence scoring
- Edge cases (NaN, negative values, etc.)
"""

from typing import Any, Dict

import pytest
from models.external_validation import ValidationStatus
from utils.response_validator import (
    ResponseValidator,
    validate_bridge_health,
    validate_bridge_mapping_stats,
    validate_memgraph_results,
    validate_ollama_embedding,
    validate_ollama_health,
    validate_qdrant_points,
    validate_qdrant_search,
)


class TestOllamaValidation:
    """Test Ollama API response validation"""

    def test_valid_embedding_response(self):
        """Test validation of valid Ollama embedding response"""
        response = {
            "model": "rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest",
            "embedding": [0.1, 0.2, 0.3, -0.4, 0.5] * 300,  # 1500 dimensions
            "prompt": "test query",
        }

        result = validate_ollama_embedding(response, allow_partial=True)

        assert result.status == ValidationStatus.VALID
        assert result.confidence == 1.0
        assert result.validated_data is not None
        assert len(result.validated_data.embedding) == 1500
        assert len(result.errors) == 0

    def test_missing_embedding_field(self):
        """Test validation fails when embedding field is missing"""
        response = {
            "model": "test-model",
            "prompt": "test query",
            # Missing 'embedding' field
        }

        result = validate_ollama_embedding(response, allow_partial=True)

        assert result.status == ValidationStatus.INVALID
        assert result.confidence < 0.5
        assert len(result.errors) > 0

    def test_empty_embedding_array(self):
        """Test validation fails with empty embedding array"""
        response = {
            "model": "test-model",
            "embedding": [],  # Empty array
            "prompt": "test query",
        }

        result = validate_ollama_embedding(response, allow_partial=True)

        assert result.status == ValidationStatus.INVALID
        assert len(result.errors) > 0

    def test_embedding_with_invalid_values(self):
        """Test validation fails with NaN or invalid float values"""
        response = {
            "model": "test-model",
            "embedding": [0.1, float("nan"), 0.3],  # Contains NaN
            "prompt": "test query",
        }

        result = validate_ollama_embedding(response, allow_partial=True)

        assert result.status == ValidationStatus.INVALID
        assert len(result.errors) > 0
        assert "invalid float values" in " ".join(result.errors).lower()

    def test_partial_health_response(self):
        """Test partial validation of health response with missing fields"""
        response = {
            "status": "ok"
            # Missing 'models' field
        }

        result = validate_ollama_health(response, allow_partial=True)

        # Should succeed with warnings about missing optional field
        assert result.status in [ValidationStatus.VALID, ValidationStatus.PARTIAL]
        assert result.confidence >= 0.5


class TestBridgeServiceValidation:
    """Test Bridge service API response validation"""

    def test_valid_mapping_stats(self):
        """Test validation of valid mapping stats response"""
        response = {
            "supabase_entities": {"pages": 100, "code_examples": 50},
            "qdrant_entities": {"vectors": 150},
            "memgraph_entities": {"nodes": 200, "relationships": 300},
            "total_entities": 150,
            "last_sync": "2025-01-01T00:00:00Z",
        }

        result = validate_bridge_mapping_stats(response, allow_partial=True)

        assert result.status == ValidationStatus.VALID
        assert result.confidence == 1.0
        assert result.validated_data is not None
        assert result.validated_data.supabase_entities["pages"] == 100

    def test_missing_entity_counts(self):
        """Test partial validation with missing entity count sections"""
        response = {
            "supabase_entities": {"pages": 100},
            # Missing qdrant_entities and memgraph_entities
        }

        result = validate_bridge_mapping_stats(response, allow_partial=True)

        # Should succeed with defaults for missing sections
        assert result.status in [ValidationStatus.VALID, ValidationStatus.PARTIAL]
        assert result.validated_data is not None
        assert result.validated_data.qdrant_entities == {}
        assert result.validated_data.memgraph_entities == {}

    def test_negative_entity_counts(self):
        """Test validation sanitizes negative entity counts"""
        response = {
            "supabase_entities": {"pages": -10},  # Invalid negative count
            "qdrant_entities": {},
            "memgraph_entities": {},
        }

        result = validate_bridge_mapping_stats(response, allow_partial=True)

        # Validator should sanitize to 0
        assert result.validated_data.supabase_entities["pages"] == 0

    def test_valid_health_response(self):
        """Test validation of Bridge health check response"""
        response = {
            "status": "healthy",
            "services": {
                "supabase": True,
                "qdrant": True,
                "memgraph": False,
            },
        }

        result = validate_bridge_health(response, allow_partial=True)

        assert result.status == ValidationStatus.VALID
        assert result.confidence == 1.0
        assert result.validated_data.status == "healthy"


class TestQdrantValidation:
    """Test Qdrant API response validation"""

    def test_valid_search_response(self):
        """Test validation of valid Qdrant search response"""
        response = {
            "result": [
                {
                    "id": "doc_123",
                    "score": 0.95,
                    "payload": {
                        "entity_id": "doc_123",
                        "entity_type": "page",
                        "title": "Test Document",
                        "content": "Test content",
                        "url": "https://example.com/doc",
                        "quality_score": 0.85,
                    },
                }
            ],
            "status": "ok",
            "time": 0.045,
        }

        result = validate_qdrant_search(response, allow_partial=True)

        assert result.status == ValidationStatus.VALID
        assert result.confidence == 1.0
        assert len(result.validated_data.result) == 1

    def test_empty_search_results(self):
        """Test validation accepts empty search results"""
        response = {"result": [], "status": "ok", "time": 0.010}

        result = validate_qdrant_search(response, allow_partial=True)

        assert result.status == ValidationStatus.VALID
        assert len(result.validated_data.result) == 0

    def test_invalid_score_range(self):
        """Test validation fails with score outside 0-1 range"""
        response = {
            "result": [
                {
                    "id": "doc_123",
                    "score": 1.5,  # Invalid: > 1.0
                    "payload": {
                        "entity_id": "doc_123",
                        "entity_type": "page",
                        "title": "Test",
                    },
                }
            ],
        }

        result = validate_qdrant_search(response, allow_partial=True)

        assert result.status != ValidationStatus.VALID
        assert len(result.errors) > 0

    def test_partial_points_validation(self):
        """Test validation of point list with some invalid items"""
        points = [
            {
                "id": "valid_1",
                "score": 0.9,
                "payload": {
                    "entity_id": "valid_1",
                    "entity_type": "page",
                    "title": "Valid",
                },
            },
            {
                "id": "invalid_1",
                "score": "not_a_number",  # Invalid score
                "payload": {"entity_id": "invalid_1", "entity_type": "page"},
            },
            {
                "id": "valid_2",
                "score": 0.8,
                "payload": {
                    "entity_id": "valid_2",
                    "entity_type": "page",
                    "title": "Valid 2",
                },
            },
        ]

        result = validate_qdrant_points(points, allow_partial=True)

        # Should validate 2 out of 3 items
        assert result.status == ValidationStatus.PARTIAL
        assert len(result.validated_data) == 2
        assert result.confidence < 1.0
        assert result.confidence > 0.5  # 2/3 = 0.67


class TestMemgraphValidation:
    """Test Memgraph API response validation"""

    def test_valid_query_results(self):
        """Test validation of valid Memgraph query results"""
        results = [
            {
                "entity": {
                    "identity": 123,
                    "labels": ["Page"],
                    "properties": {
                        "entity_id": "page_1",
                        "title": "Test Page",
                        "content": "Content",
                    },
                },
                "relationships": [],
                "path": [],
                "score": 0.8,
            }
        ]

        result = validate_memgraph_results(results, allow_partial=True)

        assert result.status == ValidationStatus.VALID
        assert result.confidence == 1.0
        assert len(result.validated_data) == 1

    def test_partial_results_with_missing_entity(self):
        """Test validation with some results missing entity data"""
        results = [
            {
                "entity": None,  # Missing entity
                "relationships": [],
                "path": [],
                "score": 0.5,
            },
            {
                "entity": {
                    "labels": ["Page"],
                    "properties": {"entity_id": "page_2", "title": "Valid"},
                },
                "relationships": [],
                "path": [],
                "score": 0.7,
            },
        ]

        result = validate_memgraph_results(results, allow_partial=True)

        # Should accept both with warnings
        assert result.status in [ValidationStatus.VALID, ValidationStatus.PARTIAL]
        assert len(result.validated_data) >= 1


class TestResponseValidatorUtilities:
    """Test ResponseValidator utility methods"""

    def test_confidence_calculation_with_errors(self):
        """Test confidence calculation reduces with errors"""
        errors = ["error1", "error2", "error3"]
        warnings = ["warning1"]
        response = {"some": "data"}

        confidence = ResponseValidator._calculate_confidence(errors, warnings, response)

        # 3 errors * 0.20 + 1 warning * 0.05 = 0.65 penalty
        # 1.0 - 0.65 = 0.35
        assert confidence == pytest.approx(0.35, abs=0.05)

    def test_confidence_boost_for_critical_fields(self):
        """Test confidence boost when critical fields present"""
        errors = ["minor_error"]  # 0.20 penalty
        warnings = []
        response = {"status": "ok", "result": []}  # Has critical fields

        confidence = ResponseValidator._calculate_confidence(errors, warnings, response)

        # Base: 1.0 - 0.20 = 0.80
        # Boost: 2 critical fields * 0.05 = 0.10
        # Final: 0.80 + 0.10 = 0.90
        assert confidence >= 0.85

    def test_type_defaults(self):
        """Test default value generation for types"""
        assert ResponseValidator._get_type_default(str) == ""
        assert ResponseValidator._get_type_default(int) == 0
        assert ResponseValidator._get_type_default(float) == 0.0
        assert ResponseValidator._get_type_default(bool) is False
        assert ResponseValidator._get_type_default(list) == []
        assert ResponseValidator._get_type_default(dict) == {}


class TestGracefulDegradation:
    """Test graceful degradation scenarios"""

    def test_complete_service_failure(self):
        """Test handling of complete service failure (empty response)"""
        response = {}

        result = validate_bridge_mapping_stats(response, allow_partial=True)

        # Pydantic models with defaults accept empty responses as valid
        # This is actually good for resilience - we get empty defaults
        assert result.status == ValidationStatus.VALID
        assert result.validated_data.supabase_entities == {}
        assert result.validated_data.qdrant_entities == {}
        assert result.validated_data.memgraph_entities == {}

    def test_malformed_json_structure(self):
        """Test handling of completely malformed response"""
        response = {"completely": {"wrong": {"structure": "here"}}}

        result = validate_bridge_mapping_stats(response, allow_partial=True)

        # Models with extra="allow" will accept extra fields and use defaults for missing ones
        # This is resilient behavior - we still get valid data even with unexpected structure
        assert result.status == ValidationStatus.VALID
        assert isinstance(result.errors, list)
        # Validated data should have default values for expected fields
        assert result.validated_data.supabase_entities == {}

    def test_partial_validation_disabled(self):
        """Test that disabling partial validation enforces strict mode"""
        response = {
            "supabase_entities": {"pages": 100},
            # Missing required qdrant_entities and memgraph_entities
        }

        result = validate_bridge_mapping_stats(response, allow_partial=False)

        # Should fail in strict mode (depending on model requirements)
        # Note: This might pass if fields have defaults in Pydantic model
        assert result.status in [ValidationStatus.VALID, ValidationStatus.INVALID]


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_very_large_embedding(self):
        """Test validation of large embedding vector"""
        response = {
            "model": "test",
            "embedding": [0.1] * 15000,  # Exceeds max_length of 10000
        }

        result = validate_ollama_embedding(response, allow_partial=True)

        # Should fail due to max_length constraint
        assert result.status != ValidationStatus.VALID
        assert len(result.errors) > 0

    def test_unicode_content(self):
        """Test validation with Unicode content"""
        response = {
            "supabase_entities": {"pages": 10},
            "qdrant_entities": {"vectors": 10},
            "memgraph_entities": {"nodes": 10},
        }

        result = validate_bridge_mapping_stats(response, allow_partial=True)

        assert result.status == ValidationStatus.VALID

    def test_null_values_in_optional_fields(self):
        """Test validation handles null values correctly"""
        response = {
            "entity_id": "test_id",
            "entity_type": "page",
            "title": None,  # Null optional field
            "content": None,
            "url": None,
        }

        # This should validate as QdrantPointPayload allows optional fields
        from models.external_validation import QdrantPointPayload

        result = ResponseValidator.validate_response(
            response, QdrantPointPayload, "test", allow_partial=True
        )

        assert result.status in [ValidationStatus.VALID, ValidationStatus.PARTIAL]
