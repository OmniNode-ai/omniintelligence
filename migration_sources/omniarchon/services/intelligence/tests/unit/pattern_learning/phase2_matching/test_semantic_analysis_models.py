"""
Comprehensive Test Suite for Semantic Analysis Models

Tests cover:
- Pydantic model validation and serialization
- Field constraints and types
- Edge cases and invalid inputs
- Default values and optional fields
- Model relationships and nesting
- JSON serialization/deserialization
- Model examples and documentation

Target: >90% code coverage for model_semantic_analysis.py (36 statements)
"""

import pytest
from archon_services.pattern_learning.phase2_matching.model_semantic_analysis import (
    SemanticAnalysisRequest,
    SemanticAnalysisResult,
    SemanticConcept,
    SemanticDomain,
    SemanticPattern,
    SemanticTheme,
)
from pydantic import ValidationError

# ============================================================================
# SemanticConcept Tests
# ============================================================================


class TestSemanticConcept:
    """Test SemanticConcept model validation and serialization."""

    def test_valid_concept_creation(self):
        """Test creating a valid SemanticConcept."""
        concept = SemanticConcept(
            concept="authentication", score=0.92, context="security"
        )

        assert concept.concept == "authentication"
        assert concept.score == 0.92
        assert concept.context == "security"

    def test_concept_without_context(self):
        """Test SemanticConcept without optional context."""
        concept = SemanticConcept(concept="api_endpoint", score=0.87)

        assert concept.concept == "api_endpoint"
        assert concept.score == 0.87
        assert concept.context is None

    def test_concept_score_validation(self):
        """Test score must be between 0.0 and 1.0."""
        # Valid scores
        SemanticConcept(concept="test", score=0.0)
        SemanticConcept(concept="test", score=0.5)
        SemanticConcept(concept="test", score=1.0)

        # Invalid scores
        with pytest.raises(ValidationError):
            SemanticConcept(concept="test", score=-0.1)

        with pytest.raises(ValidationError):
            SemanticConcept(concept="test", score=1.1)

    def test_concept_name_validation(self):
        """Test concept name must not be empty."""
        with pytest.raises(ValidationError):
            SemanticConcept(concept="", score=0.5)

    def test_concept_serialization(self):
        """Test JSON serialization."""
        concept = SemanticConcept(concept="test_concept", score=0.75, context="testing")

        json_data = concept.model_dump()

        assert json_data["concept"] == "test_concept"
        assert json_data["score"] == 0.75
        assert json_data["context"] == "testing"


# ============================================================================
# SemanticTheme Tests
# ============================================================================


class TestSemanticTheme:
    """Test SemanticTheme model validation and serialization."""

    def test_valid_theme_creation(self):
        """Test creating a valid SemanticTheme."""
        theme = SemanticTheme(
            theme="api_security",
            weight=0.85,
            related_concepts=["authentication", "authorization"],
        )

        assert theme.theme == "api_security"
        assert theme.weight == 0.85
        assert len(theme.related_concepts) == 2

    def test_theme_without_concepts(self):
        """Test SemanticTheme with empty related_concepts."""
        theme = SemanticTheme(theme="general", weight=0.5)

        assert theme.theme == "general"
        assert theme.related_concepts == []

    def test_theme_weight_validation(self):
        """Test weight must be between 0.0 and 1.0."""
        # Valid weights
        SemanticTheme(theme="test", weight=0.0)
        SemanticTheme(theme="test", weight=1.0)

        # Invalid weights
        with pytest.raises(ValidationError):
            SemanticTheme(theme="test", weight=-0.1)

        with pytest.raises(ValidationError):
            SemanticTheme(theme="test", weight=1.5)

    def test_theme_name_validation(self):
        """Test theme name must not be empty."""
        with pytest.raises(ValidationError):
            SemanticTheme(theme="", weight=0.5)


# ============================================================================
# SemanticDomain Tests
# ============================================================================


class TestSemanticDomain:
    """Test SemanticDomain model validation and serialization."""

    def test_valid_domain_creation(self):
        """Test creating a valid SemanticDomain."""
        domain = SemanticDomain(
            domain="api_design", confidence=0.91, subdomain="security"
        )

        assert domain.domain == "api_design"
        assert domain.confidence == 0.91
        assert domain.subdomain == "security"

    def test_domain_without_subdomain(self):
        """Test SemanticDomain without optional subdomain."""
        domain = SemanticDomain(domain="debugging", confidence=0.75)

        assert domain.domain == "debugging"
        assert domain.subdomain is None

    def test_domain_confidence_validation(self):
        """Test confidence must be between 0.0 and 1.0."""
        # Valid confidence
        SemanticDomain(domain="test", confidence=0.0)
        SemanticDomain(domain="test", confidence=1.0)

        # Invalid confidence
        with pytest.raises(ValidationError):
            SemanticDomain(domain="test", confidence=-0.1)

        with pytest.raises(ValidationError):
            SemanticDomain(domain="test", confidence=1.1)

    def test_domain_name_validation(self):
        """Test domain name must not be empty."""
        with pytest.raises(ValidationError):
            SemanticDomain(domain="", confidence=0.5)


# ============================================================================
# SemanticPattern Tests
# ============================================================================


class TestSemanticPattern:
    """Test SemanticPattern model validation and serialization."""

    def test_valid_pattern_creation(self):
        """Test creating a valid SemanticPattern."""
        pattern = SemanticPattern(
            pattern_type="best-practice",
            description="JWT-based authentication pattern",
            strength=0.88,
            indicators=["token", "bearer", "jwt"],
        )

        assert pattern.pattern_type == "best-practice"
        assert pattern.description == "JWT-based authentication pattern"
        assert pattern.strength == 0.88
        assert len(pattern.indicators) == 3

    def test_pattern_without_indicators(self):
        """Test SemanticPattern with empty indicators."""
        pattern = SemanticPattern(
            pattern_type="workflow",
            description="Standard workflow pattern",
            strength=0.65,
        )

        assert pattern.indicators == []

    def test_pattern_strength_validation(self):
        """Test strength must be between 0.0 and 1.0."""
        # Valid strength
        SemanticPattern(pattern_type="test", description="Test pattern", strength=0.0)
        SemanticPattern(pattern_type="test", description="Test pattern", strength=1.0)

        # Invalid strength
        with pytest.raises(ValidationError):
            SemanticPattern(pattern_type="test", description="Test", strength=-0.1)

        with pytest.raises(ValidationError):
            SemanticPattern(pattern_type="test", description="Test", strength=1.1)

    def test_pattern_type_validation(self):
        """Test pattern_type must not be empty."""
        with pytest.raises(ValidationError):
            SemanticPattern(pattern_type="", description="Test", strength=0.5)


# ============================================================================
# SemanticAnalysisResult Tests
# ============================================================================


class TestSemanticAnalysisResult:
    """Test SemanticAnalysisResult model validation and serialization."""

    def test_valid_result_creation(self):
        """Test creating a valid SemanticAnalysisResult with all fields."""
        result = SemanticAnalysisResult(
            concepts=[SemanticConcept(concept="auth", score=0.9)],
            themes=[SemanticTheme(theme="security", weight=0.8)],
            domains=[SemanticDomain(domain="api", confidence=0.85)],
            patterns=[
                SemanticPattern(
                    pattern_type="best-practice", description="Test", strength=0.7
                )
            ],
            language="en",
            processing_time_ms=245.3,
            metadata={"version": "1.0.0"},
        )

        assert len(result.concepts) == 1
        assert len(result.themes) == 1
        assert len(result.domains) == 1
        assert len(result.patterns) == 1
        assert result.language == "en"
        assert result.processing_time_ms == 245.3
        assert result.metadata["version"] == "1.0.0"

    def test_minimal_result_creation(self):
        """Test creating SemanticAnalysisResult with minimal fields."""
        result = SemanticAnalysisResult()

        assert result.concepts == []
        assert result.themes == []
        assert result.domains == []
        assert result.patterns == []
        assert result.language == "en"
        assert result.processing_time_ms is None
        assert result.metadata == {}

    def test_result_with_custom_language(self):
        """Test SemanticAnalysisResult with non-English language."""
        result = SemanticAnalysisResult(language="es")

        assert result.language == "es"

    def test_result_serialization(self):
        """Test full JSON serialization."""
        result = SemanticAnalysisResult(
            concepts=[SemanticConcept(concept="test", score=0.5)],
            themes=[SemanticTheme(theme="testing", weight=0.6)],
            language="en",
            processing_time_ms=100.5,
        )

        json_data = result.model_dump()

        assert len(json_data["concepts"]) == 1
        assert json_data["concepts"][0]["concept"] == "test"
        assert len(json_data["themes"]) == 1
        assert json_data["language"] == "en"
        assert json_data["processing_time_ms"] == 100.5

    def test_result_from_example_data(self):
        """Test creating result from example data in schema."""
        example_data = {
            "concepts": [
                {"concept": "authentication", "score": 0.92, "context": "security"}
            ],
            "themes": [
                {
                    "theme": "api_security",
                    "weight": 0.85,
                    "related_concepts": ["authentication", "authorization"],
                }
            ],
            "domains": [
                {"domain": "api_design", "confidence": 0.91, "subdomain": "security"}
            ],
            "patterns": [
                {
                    "pattern_type": "best-practice",
                    "description": "JWT-based authentication pattern",
                    "strength": 0.88,
                    "indicators": ["token", "bearer", "jwt"],
                }
            ],
            "language": "en",
            "processing_time_ms": 245.3,
            "metadata": {"model_version": "1.0.0", "confidence_threshold": 0.7},
        }

        result = SemanticAnalysisResult(**example_data)

        assert len(result.concepts) == 1
        assert result.concepts[0].concept == "authentication"
        assert len(result.themes) == 1
        assert len(result.domains) == 1
        assert len(result.patterns) == 1


# ============================================================================
# SemanticAnalysisRequest Tests
# ============================================================================


class TestSemanticAnalysisRequest:
    """Test SemanticAnalysisRequest model validation and serialization."""

    def test_valid_request_creation(self):
        """Test creating a valid SemanticAnalysisRequest."""
        request = SemanticAnalysisRequest(
            content="Implement JWT authentication for REST API endpoints",
            context="api_development",
            language="en",
            min_confidence=0.7,
        )

        assert request.content == "Implement JWT authentication for REST API endpoints"
        assert request.context == "api_development"
        assert request.language == "en"
        assert request.min_confidence == 0.7

    def test_minimal_request_creation(self):
        """Test creating request with only required fields."""
        request = SemanticAnalysisRequest(content="Test content")

        assert request.content == "Test content"
        assert request.context is None
        assert request.language == "en"
        assert request.min_confidence == 0.7

    def test_request_content_validation(self):
        """Test content must not be empty."""
        with pytest.raises(ValidationError):
            SemanticAnalysisRequest(content="")

    def test_request_min_confidence_validation(self):
        """Test min_confidence must be between 0.0 and 1.0."""
        # Valid confidence
        SemanticAnalysisRequest(content="test", min_confidence=0.0)
        SemanticAnalysisRequest(content="test", min_confidence=1.0)

        # Invalid confidence
        with pytest.raises(ValidationError):
            SemanticAnalysisRequest(content="test", min_confidence=-0.1)

        with pytest.raises(ValidationError):
            SemanticAnalysisRequest(content="test", min_confidence=1.1)

    def test_request_serialization(self):
        """Test JSON serialization."""
        request = SemanticAnalysisRequest(
            content="Test content", context="testing", language="es", min_confidence=0.8
        )

        json_data = request.model_dump()

        assert json_data["content"] == "Test content"
        assert json_data["context"] == "testing"
        assert json_data["language"] == "es"
        assert json_data["min_confidence"] == 0.8

    def test_request_from_example_data(self):
        """Test creating request from example data in schema."""
        example_data = {
            "content": "Implement JWT authentication for REST API endpoints",
            "context": "api_development",
            "language": "en",
            "min_confidence": 0.7,
        }

        request = SemanticAnalysisRequest(**example_data)

        assert request.content == "Implement JWT authentication for REST API endpoints"
        assert request.context == "api_development"


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================


class TestModelIntegration:
    """Test model integration and complex scenarios."""

    def test_result_with_many_items(self):
        """Test SemanticAnalysisResult with many concepts/themes/etc."""
        # Create 50 concepts with valid scores (0.5 to 0.99)
        concepts = [
            SemanticConcept(concept=f"concept_{i}", score=0.5 + (i * 0.01))
            for i in range(50)
        ]

        result = SemanticAnalysisResult(concepts=concepts)

        assert len(result.concepts) == 50
        assert result.concepts[0].score == 0.5
        assert result.concepts[49].score == 0.99

    def test_nested_model_validation(self):
        """Test validation propagates through nested models."""
        # Invalid nested concept should fail
        with pytest.raises(ValidationError):
            SemanticAnalysisResult(
                concepts=[{"concept": "test", "score": 1.5}]  # Invalid score
            )

    def test_model_json_roundtrip(self):
        """Test serialization and deserialization roundtrip."""
        original = SemanticAnalysisResult(
            concepts=[SemanticConcept(concept="test", score=0.9, context="ctx")],
            themes=[
                SemanticTheme(theme="theme1", weight=0.8, related_concepts=["a", "b"])
            ],
            language="fr",
            processing_time_ms=123.45,
            metadata={"key": "value"},
        )

        # Serialize
        json_data = original.model_dump()

        # Deserialize
        restored = SemanticAnalysisResult(**json_data)

        # Compare
        assert restored.concepts[0].concept == original.concepts[0].concept
        assert restored.themes[0].theme == original.themes[0].theme
        assert restored.language == original.language
        assert restored.processing_time_ms == original.processing_time_ms
        assert restored.metadata == original.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
