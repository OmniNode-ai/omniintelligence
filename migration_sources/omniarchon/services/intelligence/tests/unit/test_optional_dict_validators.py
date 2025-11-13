"""
Test suite for Optional[dict[str, Any]] field validators.

This test file verifies that all Pydantic models with Optional[dict] fields
have proper validators to prevent None access errors.

Test Coverage:
- autonomous_learning_events.py: 3 models, 5 fields
- entity_models.py: 3 models, 3 fields
- response_formatters.py: 2 models, 2 fields
- qdrant_contracts.py: 3 models, 4 fields

Test Scenarios:
1. None values should pass validation
2. Valid dict values should pass validation
3. Invalid types (str, int, list) should raise ValueError
4. Empty dicts should pass validation

Created: 2025-10-23
"""

import pytest

# Import models from qdrant_contracts.py
from onex.contracts.qdrant_contracts import (
    ModelContractQdrantSearchEffect,
    ModelContractQdrantUpdateEffect,
    ModelQdrantHit,
)
from pydantic import ValidationError

# Import models from response_formatters.py
from src.api.utils.response_formatters import (
    HealthCheckResponse,
    SuccessResponse,
)

# Import models from autonomous_learning_events.py
from src.events.models.autonomous_learning_events import (
    ModelAutonomousAgentPredictRequestPayload,
    ModelAutonomousSafetyScoreRequestPayload,
    ModelAutonomousTimePredictRequestPayload,
)

# Import models from entity_models.py
from src.models.entity_models import (
    CodeRequest,
    DocumentRequest,
    PatternMatch,
)


class TestAutonomousLearningEventValidators:
    """Test validators in autonomous_learning_events.py"""

    def test_agent_predict_request_none_values(self):
        """Test that None values are accepted"""
        payload = ModelAutonomousAgentPredictRequestPayload(
            task_characteristics=None,
            context=None,
            requirements=None,
            confidence_threshold=0.7,
        )
        assert payload.task_characteristics is None
        assert payload.context is None
        assert payload.requirements is None

    def test_agent_predict_request_valid_dicts(self):
        """Test that valid dict values are accepted"""
        payload = ModelAutonomousAgentPredictRequestPayload(
            task_characteristics={"task_type": "code_generation", "complexity": 0.8},
            context={"domain": "api_development", "previous_agent": "agent-api"},
            requirements={"constraints": ["performance"], "goals": ["scalability"]},
            confidence_threshold=0.7,
        )
        assert isinstance(payload.task_characteristics, dict)
        assert isinstance(payload.context, dict)
        assert isinstance(payload.requirements, dict)

    def test_agent_predict_request_empty_dicts(self):
        """Test that empty dicts are accepted"""
        payload = ModelAutonomousAgentPredictRequestPayload(
            task_characteristics={},
            context={},
            requirements={},
            confidence_threshold=0.7,
        )
        assert payload.task_characteristics == {}
        assert payload.context == {}
        assert payload.requirements == {}

    def test_agent_predict_request_invalid_type_task_characteristics(self):
        """Test that invalid type for task_characteristics raises ValueError"""
        with pytest.raises(ValidationError) as exc_info:
            ModelAutonomousAgentPredictRequestPayload(
                task_characteristics="invalid",  # Should be dict or None
                confidence_threshold=0.7,
            )
        assert "task_characteristics must be a dict or None" in str(exc_info.value)

    def test_agent_predict_request_invalid_type_context(self):
        """Test that invalid type for context raises ValueError"""
        with pytest.raises(ValidationError) as exc_info:
            ModelAutonomousAgentPredictRequestPayload(
                context=["list", "not", "dict"],  # Should be dict or None
                confidence_threshold=0.7,
            )
        assert "context must be a dict or None" in str(exc_info.value)

    def test_time_predict_request_none_value(self):
        """Test that None value is accepted for task_characteristics"""
        payload = ModelAutonomousTimePredictRequestPayload(
            task_characteristics=None,
            agent="agent-api-architect",
        )
        assert payload.task_characteristics is None

    def test_time_predict_request_valid_dict(self):
        """Test that valid dict is accepted for task_characteristics"""
        payload = ModelAutonomousTimePredictRequestPayload(
            task_characteristics={"task_type": "api_endpoint", "estimated_lines": 100},
            agent="agent-api-architect",
        )
        assert isinstance(payload.task_characteristics, dict)

    def test_safety_score_request_none_value(self):
        """Test that None value is accepted for context"""
        payload = ModelAutonomousSafetyScoreRequestPayload(
            task_type="code_generation",
            context=None,
        )
        assert payload.context is None

    def test_safety_score_request_valid_dict(self):
        """Test that valid dict is accepted for context"""
        payload = ModelAutonomousSafetyScoreRequestPayload(
            task_type="code_generation",
            context={"file_paths": ["/src/api.py"], "dependencies": ["fastapi"]},
        )
        assert isinstance(payload.context, dict)


class TestEntityModelValidators:
    """Test validators in entity_models.py"""

    def test_document_request_none_metadata(self):
        """Test that None metadata is accepted"""
        request = DocumentRequest(
            content="Document content",
            source_path="/docs/test.md",
            metadata=None,
        )
        assert request.metadata is None

    def test_document_request_valid_metadata(self):
        """Test that valid metadata dict is accepted"""
        request = DocumentRequest(
            content="Document content",
            source_path="/docs/test.md",
            metadata={"project_id": "proj-123", "tags": ["documentation"]},
        )
        assert isinstance(request.metadata, dict)
        assert request.metadata["project_id"] == "proj-123"

    def test_document_request_empty_metadata(self):
        """Test that empty metadata dict is accepted"""
        request = DocumentRequest(
            content="Document content",
            source_path="/docs/test.md",
            metadata={},
        )
        assert request.metadata == {}

    def test_document_request_invalid_metadata_type(self):
        """Test that invalid metadata type raises ValueError"""
        with pytest.raises(ValidationError) as exc_info:
            DocumentRequest(
                content="Document content",
                source_path="/docs/test.md",
                metadata="invalid_string",  # Should be dict or None
            )
        assert "metadata must be a dict or None" in str(exc_info.value)

    def test_code_request_none_metadata(self):
        """Test that None metadata is accepted"""
        request = CodeRequest(
            content="print('Hello')",
            source_path="/src/test.py",
            metadata=None,
        )
        assert request.metadata is None

    def test_code_request_valid_metadata(self):
        """Test that valid metadata dict is accepted"""
        request = CodeRequest(
            content="print('Hello')",
            source_path="/src/test.py",
            language="python",
            metadata={"framework": "fastapi", "version": "0.1.0"},
        )
        assert isinstance(request.metadata, dict)

    def test_pattern_match_none_location(self):
        """Test that None location is accepted"""
        match = PatternMatch(
            pattern_name="anti_pattern_detected",
            pattern_type="code_smell",
            confidence=0.85,
            description="God object pattern detected",
            location=None,
        )
        assert match.location is None

    def test_pattern_match_valid_location(self):
        """Test that valid location dict is accepted"""
        match = PatternMatch(
            pattern_name="anti_pattern_detected",
            pattern_type="code_smell",
            confidence=0.85,
            description="God object pattern detected",
            location={"file": "/src/api.py", "line": 42, "column": 10},
        )
        assert isinstance(match.location, dict)
        assert match.location["line"] == 42

    def test_pattern_match_invalid_location_type(self):
        """Test that invalid location type raises ValueError"""
        with pytest.raises(ValidationError) as exc_info:
            PatternMatch(
                pattern_name="anti_pattern_detected",
                pattern_type="code_smell",
                confidence=0.85,
                description="God object pattern detected",
                location=123,  # Should be dict or None
            )
        assert "location must be a dict or None" in str(exc_info.value)


class TestResponseFormatterValidators:
    """Test validators in response_formatters.py"""

    def test_success_response_none_metadata(self):
        """Test that None metadata is accepted"""
        response = SuccessResponse(
            status="success",
            timestamp="2025-10-23T12:00:00Z",
            data={"result": "success"},
            metadata=None,
        )
        assert response.metadata is None

    def test_success_response_valid_metadata(self):
        """Test that valid metadata dict is accepted"""
        response = SuccessResponse(
            status="success",
            timestamp="2025-10-23T12:00:00Z",
            data={"result": "success"},
            metadata={"count": 10, "execution_time_ms": 45.2},
        )
        assert isinstance(response.metadata, dict)
        assert response.metadata["count"] == 10

    def test_success_response_empty_metadata(self):
        """Test that empty metadata dict is accepted"""
        response = SuccessResponse(
            status="success",
            timestamp="2025-10-23T12:00:00Z",
            data={"result": "success"},
            metadata={},
        )
        assert response.metadata == {}

    def test_success_response_invalid_metadata_type(self):
        """Test that invalid metadata type raises ValueError"""
        with pytest.raises(ValidationError) as exc_info:
            SuccessResponse(
                status="success",
                timestamp="2025-10-23T12:00:00Z",
                data={"result": "success"},
                metadata=[1, 2, 3],  # Should be dict or None
            )
        assert "metadata must be a dict or None" in str(exc_info.value)

    def test_health_check_response_none_checks(self):
        """Test that None checks is accepted"""
        response = HealthCheckResponse(
            status="healthy",
            timestamp="2025-10-23T12:00:00Z",
            service="intelligence",
            checks=None,
        )
        assert response.checks is None

    def test_health_check_response_valid_checks(self):
        """Test that valid checks dict is accepted"""
        response = HealthCheckResponse(
            status="healthy",
            timestamp="2025-10-23T12:00:00Z",
            service="intelligence",
            checks={
                "database": {"status": "healthy", "latency_ms": 5.2},
                "cache": {"status": "healthy", "hit_rate": 0.87},
            },
        )
        assert isinstance(response.checks, dict)
        assert response.checks["database"]["status"] == "healthy"

    def test_health_check_response_invalid_checks_type(self):
        """Test that invalid checks type raises ValueError"""
        with pytest.raises(ValidationError) as exc_info:
            HealthCheckResponse(
                status="healthy",
                timestamp="2025-10-23T12:00:00Z",
                service="intelligence",
                checks="invalid_string",  # Should be dict or None
            )
        assert "checks must be a dict or None" in str(exc_info.value)


class TestQdrantContractValidators:
    """Test validators in qdrant_contracts.py"""

    def test_qdrant_hit_none_payload(self):
        """Test that None payload is accepted"""
        hit = ModelQdrantHit(
            id="hit-123",
            score=0.95,
            payload=None,
        )
        assert hit.payload is None

    def test_qdrant_hit_valid_payload(self):
        """Test that valid payload dict is accepted"""
        hit = ModelQdrantHit(
            id="hit-123",
            score=0.95,
            payload={"text": "Sample text", "entity_type": "FUNCTION"},
        )
        assert isinstance(hit.payload, dict)
        assert hit.payload["entity_type"] == "FUNCTION"

    def test_qdrant_hit_empty_payload(self):
        """Test that empty payload dict is accepted"""
        hit = ModelQdrantHit(
            id="hit-123",
            score=0.95,
            payload={},
        )
        assert hit.payload == {}

    def test_qdrant_hit_invalid_payload_type(self):
        """Test that invalid payload type raises ValueError"""
        with pytest.raises(ValidationError) as exc_info:
            ModelQdrantHit(
                id="hit-123",
                score=0.95,
                payload="invalid_string",  # Should be dict or None
            )
        assert "payload must be a dict or None" in str(exc_info.value)

    def test_search_effect_none_filters_and_params(self):
        """Test that None filters and search_params are accepted"""
        contract = ModelContractQdrantSearchEffect(
            collection_name="test_collection",
            query_text="search query",
            limit=10,
            filters=None,
            search_params=None,
        )
        assert contract.filters is None
        assert contract.search_params is None

    def test_search_effect_valid_filters_and_params(self):
        """Test that valid filters and search_params dicts are accepted"""
        contract = ModelContractQdrantSearchEffect(
            collection_name="test_collection",
            query_text="search query",
            limit=10,
            filters={"must": [{"key": "entity_type", "match": {"value": "FUNCTION"}}]},
            search_params={"hnsw_ef": 128, "exact": False},
        )
        assert isinstance(contract.filters, dict)
        assert isinstance(contract.search_params, dict)
        assert contract.search_params["hnsw_ef"] == 128

    def test_search_effect_invalid_filters_type(self):
        """Test that invalid filters type raises ValueError"""
        with pytest.raises(ValidationError) as exc_info:
            ModelContractQdrantSearchEffect(
                collection_name="test_collection",
                query_text="search query",
                limit=10,
                filters=[1, 2, 3],  # Should be dict or None
            )
        assert "filters must be a dict or None" in str(exc_info.value)

    def test_search_effect_invalid_search_params_type(self):
        """Test that invalid search_params type raises ValueError"""
        with pytest.raises(ValidationError) as exc_info:
            ModelContractQdrantSearchEffect(
                collection_name="test_collection",
                query_text="search query",
                limit=10,
                search_params=123,  # Should be dict or None
            )
        assert "search_params must be a dict or None" in str(exc_info.value)

    def test_update_effect_none_payload(self):
        """Test that None payload is accepted (with text_for_embedding)"""
        contract = ModelContractQdrantUpdateEffect(
            collection_name="test_collection",
            point_id="point-123",
            payload=None,
            text_for_embedding="Sample text for embedding",
        )
        assert contract.payload is None

    def test_update_effect_valid_payload(self):
        """Test that valid payload dict is accepted"""
        contract = ModelContractQdrantUpdateEffect(
            collection_name="test_collection",
            point_id="point-123",
            payload={"text": "Updated text", "metadata": {"updated": True}},
        )
        assert isinstance(contract.payload, dict)
        assert contract.payload["metadata"]["updated"] is True

    def test_update_effect_invalid_payload_type(self):
        """Test that invalid payload type raises ValueError"""
        with pytest.raises(ValidationError) as exc_info:
            ModelContractQdrantUpdateEffect(
                collection_name="test_collection",
                point_id="point-123",
                payload="invalid_string",  # Should be dict or None
            )
        assert "payload must be a dict or None" in str(exc_info.value)

    def test_update_effect_requires_payload_or_text(self):
        """Test that at least one of payload or text_for_embedding is required"""
        with pytest.raises(ValidationError) as exc_info:
            ModelContractQdrantUpdateEffect(
                collection_name="test_collection",
                point_id="point-123",
                payload=None,
                text_for_embedding=None,
            )
        assert "Either 'payload' or 'text_for_embedding' must be provided" in str(
            exc_info.value
        )


class TestValidatorDocumentation:
    """Test that validators have proper documentation"""

    def test_validators_have_docstrings(self):
        """Verify that all validators have docstrings"""
        models_to_check = [
            ModelAutonomousAgentPredictRequestPayload,
            ModelAutonomousTimePredictRequestPayload,
            ModelAutonomousSafetyScoreRequestPayload,
            DocumentRequest,
            CodeRequest,
            PatternMatch,
            SuccessResponse,
            HealthCheckResponse,
            ModelQdrantHit,
            ModelContractQdrantSearchEffect,
            ModelContractQdrantUpdateEffect,
        ]

        for model in models_to_check:
            # Check if model has field validators
            if hasattr(model, "__pydantic_decorators__"):
                validators = model.__pydantic_decorators__.field_validators
                for field_name, decorator in validators.items():
                    # In Pydantic v2, decorator is a Decorator object with a func attribute
                    validator_func = decorator.func
                    assert (
                        validator_func.__doc__
                    ), f"{model.__name__}.{validator_func.__name__} missing docstring"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
