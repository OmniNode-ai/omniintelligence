"""
Unit tests for Codegen LangExtract Service

Tests PRD semantic analysis logic, error handling, and response transformation.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.archon_services.langextract.codegen_langextract_service import (
    CodegenLangExtractService,
)
from src.archon_services.pattern_learning.phase2_matching.exceptions_langextract import (
    LangextractTimeoutError,
    LangextractUnavailableError,
    LangextractValidationError,
)
from src.archon_services.pattern_learning.phase2_matching.model_semantic_analysis import (
    SemanticAnalysisResult,
    SemanticConcept,
    SemanticDomain,
    SemanticPattern,
    SemanticTheme,
)

# Add src directory to path for imports


class TestCodegenLangExtractService:
    """Test suite for Codegen LangExtract Service."""

    @pytest.fixture
    def mock_langextract_client(self):
        """Create mock LangExtract client."""
        client = AsyncMock()
        client.connect = AsyncMock()
        client.close = AsyncMock()
        client.get_metrics = MagicMock(return_value={"total_requests": 0})
        client.check_health = AsyncMock(
            return_value={"healthy": True, "status_code": 200}
        )
        return client

    @pytest.fixture
    def service(self, mock_langextract_client):
        """Create LangExtract service instance with mock client."""
        return CodegenLangExtractService(langextract_client=mock_langextract_client)

    @pytest.fixture
    def sample_semantic_result(self):
        """Create sample semantic analysis result from LangExtract."""
        return SemanticAnalysisResult(
            concepts=[
                SemanticConcept(
                    concept="UserService",
                    score=0.9,
                    context="REST API service for user management",
                ),
                SemanticConcept(
                    concept="authentication",
                    score=0.85,
                    context="User authentication flow",
                ),
                SemanticConcept(
                    concept="Database",
                    score=0.8,
                    context="PostgreSQL database",
                ),
            ],
            themes=[
                SemanticTheme(
                    theme="REST API",
                    weight=0.9,
                    related_concepts=["api", "rest", "endpoint"],
                ),
                SemanticTheme(
                    theme="Authentication",
                    weight=0.85,
                    related_concepts=["auth", "token", "jwt"],
                ),
            ],
            domains=[
                SemanticDomain(
                    domain="Web Services",
                    confidence=0.9,
                    subdomain="api_architecture",
                ),
            ],
            patterns=[
                SemanticPattern(
                    pattern_type="api_endpoint",
                    strength=0.9,
                    description="REST API endpoint pattern",
                    indicators=["endpoint", "rest", "api"],
                ),
                SemanticPattern(
                    pattern_type="data_storage",
                    strength=0.8,
                    description="Database persistence pattern",
                    indicators=["database", "storage", "persist"],
                ),
            ],
            language="en",
            processing_time_ms=250.5,
            metadata={},
        )

    @pytest.mark.asyncio
    async def test_analyze_prd_success(
        self, service, mock_langextract_client, sample_semantic_result
    ):
        """Test successful PRD analysis."""
        # Setup mock response
        mock_langextract_client.analyze_semantic.return_value = sample_semantic_result

        prd_content = """
        Create a REST API service for user management.
        The service should handle user authentication and store data in PostgreSQL.
        """

        result = await service.analyze_prd_semantics(prd_content)

        # Verify basic structure
        assert "concepts" in result
        assert "entities" in result
        assert "relationships" in result
        assert "domain_keywords" in result
        assert "node_type_hints" in result
        assert "confidence" in result
        assert "metadata" in result

        # Verify concepts extracted
        assert len(result["concepts"]) == 3
        assert result["concepts"][0]["name"] == "UserService"
        assert result["concepts"][0]["confidence"] == 0.9

        # Verify entities extracted (high-confidence concepts >= 0.7)
        assert len(result["entities"]) >= 2
        entity_names = [e["name"] for e in result["entities"]]
        assert "UserService" in entity_names
        assert "Database" in entity_names

        # Verify relationships extracted
        assert len(result["relationships"]) == 2

        # Verify domain keywords
        assert len(result["domain_keywords"]) == 2
        assert "REST API" in result["domain_keywords"]
        assert "Authentication" in result["domain_keywords"]

        # Verify confidence score
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["confidence"] > 0.7

        # Verify node type hints exist
        assert "effect" in result["node_type_hints"]
        assert "compute" in result["node_type_hints"]
        assert "reducer" in result["node_type_hints"]
        assert "orchestrator" in result["node_type_hints"]

        # Verify metadata
        assert result["metadata"]["processing_time_ms"] == 250.5
        assert result["metadata"]["language"] == "en"
        assert "analysis_timestamp" in result["metadata"]

    @pytest.mark.asyncio
    async def test_analyze_prd_empty_content(self, service, mock_langextract_client):
        """Test analysis with empty PRD content."""
        result = await service.analyze_prd_semantics("")

        # Should return error response
        assert result["concepts"] == []
        assert result["entities"] == []
        assert result["confidence"] == 0.0
        assert "error" in result["metadata"]

        # Client should not be called
        mock_langextract_client.analyze_semantic.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_prd_validation_error(self, service, mock_langextract_client):
        """Test handling of validation errors."""
        # Setup mock to raise validation error
        mock_langextract_client.analyze_semantic.side_effect = (
            LangextractValidationError(
                "Invalid content",
                validation_errors=["Content too short", "Missing required fields"],
            )
        )

        prd_content = "Short content"
        result = await service.analyze_prd_semantics(prd_content)

        # Should return error response with validation details
        assert result["concepts"] == []
        assert result["confidence"] == 0.0
        assert "error" in result["metadata"]
        assert "Validation error" in result["metadata"]["error"]
        assert len(result["metadata"]["validation_errors"]) == 2

    @pytest.mark.asyncio
    async def test_analyze_prd_timeout_error(self, service, mock_langextract_client):
        """Test handling of timeout errors."""
        # Setup mock to raise timeout error
        mock_langextract_client.analyze_semantic.side_effect = LangextractTimeoutError(
            "Request timed out", timeout_seconds=5.0
        )

        prd_content = "Test content"
        result = await service.analyze_prd_semantics(prd_content)

        # Should return error response
        assert result["concepts"] == []
        assert result["confidence"] == 0.0
        assert "error" in result["metadata"]
        assert "timed out" in result["metadata"]["error"]

    @pytest.mark.asyncio
    async def test_analyze_prd_service_unavailable(
        self, service, mock_langextract_client
    ):
        """Test handling of service unavailable errors."""
        # Setup mock to raise unavailable error
        mock_langextract_client.analyze_semantic.side_effect = (
            LangextractUnavailableError("Service unavailable")
        )

        prd_content = "Test content"
        result = await service.analyze_prd_semantics(prd_content)

        # Should return error response
        assert result["concepts"] == []
        assert result["confidence"] == 0.0
        assert "error" in result["metadata"]
        assert "unavailable" in result["metadata"]["error"]

    @pytest.mark.asyncio
    async def test_analyze_prd_generic_error(self, service, mock_langextract_client):
        """Test handling of generic errors."""
        # Setup mock to raise generic error
        mock_langextract_client.analyze_semantic.side_effect = Exception(
            "Unexpected error"
        )

        prd_content = "Test content"
        result = await service.analyze_prd_semantics(prd_content)

        # Should return error response
        assert result["concepts"] == []
        assert result["confidence"] == 0.0
        assert "error" in result["metadata"]

    @pytest.mark.asyncio
    async def test_node_type_hints_effect(self, service, mock_langextract_client):
        """Test node type hints for effect-heavy PRD."""
        semantic_result = SemanticAnalysisResult(
            concepts=[
                SemanticConcept(
                    concept="APIClient",
                    score=0.9,
                    context="HTTP client",
                )
            ],
            themes=[SemanticTheme(theme="API", weight=0.9, related_concepts=["api"])],
            domains=[],
            patterns=[
                SemanticPattern(
                    pattern_type="http_request",
                    strength=0.9,
                    description="HTTP request pattern",
                    indicators=["http", "request"],
                ),
                SemanticPattern(
                    pattern_type="external_api",
                    strength=0.85,
                    description="External API integration",
                    indicators=["external", "api"],
                ),
            ],
            language="en",
            processing_time_ms=100.0,
            metadata={},
        )

        mock_langextract_client.analyze_semantic.return_value = semantic_result

        prd_content = "Create an HTTP client for external API integration"
        result = await service.analyze_prd_semantics(prd_content)

        # Should have high effect score
        assert result["node_type_hints"]["effect"] > 0.3

    @pytest.mark.asyncio
    async def test_node_type_hints_compute(self, service, mock_langextract_client):
        """Test node type hints for compute-heavy PRD."""
        semantic_result = SemanticAnalysisResult(
            concepts=[
                SemanticConcept(
                    concept="DataTransformer",
                    score=0.9,
                    context="Data transformation",
                )
            ],
            themes=[
                SemanticTheme(
                    theme="Processing", weight=0.9, related_concepts=["transform"]
                )
            ],
            domains=[],
            patterns=[
                SemanticPattern(
                    pattern_type="data_transform",
                    strength=0.9,
                    description="Data transformation pattern",
                    indicators=["transform", "data"],
                ),
                SemanticPattern(
                    pattern_type="algorithm",
                    strength=0.85,
                    description="Algorithm implementation",
                    indicators=["algorithm"],
                ),
            ],
            language="en",
            processing_time_ms=100.0,
            metadata={},
        )

        mock_langextract_client.analyze_semantic.return_value = semantic_result

        prd_content = "Create a data transformer with custom algorithm"
        result = await service.analyze_prd_semantics(prd_content)

        # Should have high compute score
        assert result["node_type_hints"]["compute"] > 0.3

    @pytest.mark.asyncio
    async def test_node_type_hints_reducer(self, service, mock_langextract_client):
        """Test node type hints for reducer-heavy PRD."""
        semantic_result = SemanticAnalysisResult(
            concepts=[
                SemanticConcept(
                    concept="DataStore",
                    score=0.9,
                    context="Data storage",
                )
            ],
            themes=[
                SemanticTheme(theme="Storage", weight=0.9, related_concepts=["store"])
            ],
            domains=[],
            patterns=[
                SemanticPattern(
                    pattern_type="data_aggregate",
                    strength=0.9,
                    description="Data aggregation pattern",
                    indicators=["aggregate", "data"],
                ),
                SemanticPattern(
                    pattern_type="persist",
                    strength=0.85,
                    description="Data persistence",
                    indicators=["persist"],
                ),
            ],
            language="en",
            processing_time_ms=100.0,
            metadata={},
        )

        mock_langextract_client.analyze_semantic.return_value = semantic_result

        prd_content = "Create a data aggregator that persists results"
        result = await service.analyze_prd_semantics(prd_content)

        # Should have high reducer score
        assert result["node_type_hints"]["reducer"] > 0.3

    @pytest.mark.asyncio
    async def test_context_manager_pattern(self, mock_langextract_client):
        """Test async context manager pattern."""
        service = CodegenLangExtractService(langextract_client=mock_langextract_client)

        async with service:
            # Service should be connected
            mock_langextract_client.connect.assert_called_once()

        # Service should be closed after context exit
        mock_langextract_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_metrics(self, service, mock_langextract_client):
        """Test client metrics retrieval."""
        mock_langextract_client.get_metrics.return_value = {
            "total_requests": 10,
            "successful_requests": 8,
            "failed_requests": 2,
        }

        metrics = service.get_client_metrics()

        assert metrics["total_requests"] == 10
        assert metrics["successful_requests"] == 8
        assert metrics["failed_requests"] == 2

    @pytest.mark.asyncio
    async def test_check_service_health(self, service, mock_langextract_client):
        """Test service health check."""
        mock_langextract_client.check_health.return_value = {
            "healthy": True,
            "status_code": 200,
            "response_time_ms": 50.0,
        }

        await service.connect()
        health = await service.check_service_health()

        assert health["healthy"] is True
        assert health["status_code"] == 200

    @pytest.mark.asyncio
    async def test_analysis_types(
        self, service, mock_langextract_client, sample_semantic_result
    ):
        """Test different analysis types."""
        mock_langextract_client.analyze_semantic.return_value = sample_semantic_result

        prd_content = "Test content"

        # Test quick analysis
        result_quick = await service.analyze_prd_semantics(
            prd_content, analysis_type="quick"
        )
        assert result_quick is not None

        # Test detailed analysis
        result_detailed = await service.analyze_prd_semantics(
            prd_content, analysis_type="detailed"
        )
        assert result_detailed is not None

        # Test full analysis (default)
        result_full = await service.analyze_prd_semantics(
            prd_content, analysis_type="full"
        )
        assert result_full is not None

    @pytest.mark.asyncio
    async def test_custom_min_confidence(
        self, service, mock_langextract_client, sample_semantic_result
    ):
        """Test custom min_confidence parameter."""
        mock_langextract_client.analyze_semantic.return_value = sample_semantic_result

        prd_content = "Test content"
        await service.analyze_prd_semantics(prd_content, min_confidence=0.9)

        # Verify min_confidence was passed to client
        mock_langextract_client.analyze_semantic.assert_called_once()
        call_kwargs = mock_langextract_client.analyze_semantic.call_args[1]
        assert call_kwargs["min_confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_user_context_integration(
        self, service, mock_langextract_client, sample_semantic_result
    ):
        """Test user context integration."""
        mock_langextract_client.analyze_semantic.return_value = sample_semantic_result

        prd_content = "Test content"
        user_context = "REST API for e-commerce platform"

        await service.analyze_prd_semantics(prd_content, context=user_context)

        # Verify context was passed to client
        mock_langextract_client.analyze_semantic.assert_called_once()
        call_kwargs = mock_langextract_client.analyze_semantic.call_args[1]
        assert user_context in call_kwargs["context"]
