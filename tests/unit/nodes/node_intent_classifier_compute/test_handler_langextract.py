# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for semantic enrichment handler (pure computation).

This module tests the semantic analysis handler including:
    - Domain detection from keywords
    - Concept extraction
    - Theme identification
    - Semantic to intent boost mapping
    - Edge cases and error handling

The handler is PURE COMPUTATION - no HTTP calls, no external services.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
    DEFAULT_SEMANTIC_CONFIG,
    SemanticResult,
    analyze_semantics,
    create_empty_semantic_result,
    map_semantic_to_intent_boost,
)
from omniintelligence.nodes.node_intent_classifier_compute.models import (
    ModelSemanticAnalysisConfig,
    ModelSemanticBoostsConfig,
    ModelSemanticLimitsConfig,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def default_semantic_config() -> ModelSemanticAnalysisConfig:
    """Provide default semantic config for tests."""
    return ModelSemanticAnalysisConfig()


@pytest.fixture
def custom_semantic_config() -> ModelSemanticAnalysisConfig:
    """Provide custom config with modified boosts."""
    return ModelSemanticAnalysisConfig(
        boosts=ModelSemanticBoostsConfig(
            max_boost_cap=0.5,
        ),
    )


# =============================================================================
# create_empty_semantic_result Tests
# =============================================================================


@pytest.mark.unit
class TestCreateEmptySemanticResult:
    """Tests for create_empty_semantic_result factory function."""

    def test_creates_empty_result_without_error(self) -> None:
        """Test that empty result has all required fields."""
        result = create_empty_semantic_result()

        assert result["concepts"] == []
        assert result["themes"] == []
        assert result["domains"] == []
        assert result["patterns"] == []
        assert result["domain_indicators"] == []
        assert result["topic_weights"] == {}
        assert result["processing_time_ms"] == 0.0
        assert result["error"] is None

    def test_creates_empty_result_with_error_message(self) -> None:
        """Test that error message is included when provided."""
        error_msg = "Analysis failed"
        result = create_empty_semantic_result(error=error_msg)

        assert result["error"] == error_msg
        assert result["concepts"] == []
        assert result["themes"] == []

    def test_result_structure_completeness(self) -> None:
        """Test that all expected keys are present."""
        result = create_empty_semantic_result()

        expected_keys = {
            "concepts",
            "themes",
            "domains",
            "patterns",
            "domain_indicators",
            "topic_weights",
            "processing_time_ms",
            "error",
        }
        assert set(result.keys()) == expected_keys


# =============================================================================
# analyze_semantics Tests (Pure Computation)
# =============================================================================


@pytest.mark.unit
class TestAnalyzeSemantics:
    """Tests for analyze_semantics function."""

    def test_empty_content_returns_empty_result(self) -> None:
        """Test that empty content returns empty result."""
        result = analyze_semantics("")
        assert result["concepts"] == []
        assert result["error"] is None

    def test_whitespace_content_returns_empty_result(self) -> None:
        """Test that whitespace-only content returns empty result."""
        result = analyze_semantics("   \n\t  ")
        assert result["concepts"] == []

    def test_detects_api_domain(self) -> None:
        """Test that API-related content detects api_design domain."""
        result = analyze_semantics("Create a REST API endpoint for authentication")

        assert "api_design" in result["domain_indicators"]
        assert result["topic_weights"].get("api_design", 0) > 0

    def test_detects_testing_domain(self) -> None:
        """Test that testing content detects testing domain."""
        result = analyze_semantics("Write unit tests with pytest and mocks")

        assert "testing" in result["domain_indicators"]
        assert result["topic_weights"].get("testing", 0) > 0

    def test_detects_code_generation_domain(self) -> None:
        """Test that code generation content detects correct domain."""
        result = analyze_semantics("Generate a Python function to process data")

        assert "code_generation" in result["domain_indicators"]

    def test_detects_debugging_domain(self) -> None:
        """Test that debugging content detects debugging domain."""
        result = analyze_semantics("Fix the bug in error handling")

        assert "debugging" in result["domain_indicators"]

    def test_detects_documentation_domain(self) -> None:
        """Test that documentation content detects documentation domain."""
        result = analyze_semantics("Write documentation and README for the API")

        assert "documentation" in result["domain_indicators"]

    def test_detects_multiple_domains(self) -> None:
        """Test that content with multiple domains detects all."""
        result = analyze_semantics(
            "Create an API endpoint with unit tests and documentation"
        )

        # Should detect multiple domains
        domains = result["domain_indicators"]
        assert len(domains) >= 2

    def test_context_boosts_domain(self) -> None:
        """Test that context parameter boosts specific domain."""
        result_no_context = analyze_semantics("Write code")
        result_with_context = analyze_semantics("Write code", context="testing")

        # Context should boost testing domain score if it exists
        if "testing" in result_with_context["topic_weights"]:
            testing_with_ctx = result_with_context["topic_weights"]["testing"]
            testing_no_ctx = result_no_context["topic_weights"].get("testing", 0)
            assert testing_with_ctx >= testing_no_ctx

    def test_extracts_concepts(self) -> None:
        """Test that concepts are extracted from content."""
        result = analyze_semantics("Create REST API endpoint with authentication")

        assert len(result["concepts"]) > 0
        concept_names = [c["name"] for c in result["concepts"]]
        # Should find some API-related concepts
        assert any(
            c in ["api", "rest", "endpoint", "authentication"] for c in concept_names
        )

    def test_concepts_have_confidence(self) -> None:
        """Test that concepts have confidence scores."""
        result = analyze_semantics("Generate code with testing")

        for concept in result["concepts"]:
            assert "confidence" in concept
            assert 0.0 <= concept["confidence"] <= 1.0

    def test_concepts_have_category(self) -> None:
        """Test that concepts have category assigned."""
        result = analyze_semantics("Generate code with unit tests")

        for concept in result["concepts"]:
            assert "category" in concept
            assert isinstance(concept["category"], str)

    def test_detects_themes(self) -> None:
        """Test that themes are detected from domains."""
        result = analyze_semantics("Generate code and refactor for debugging")

        # Should detect development theme (covers code_generation, refactoring, debugging)
        theme_names = [t["name"] for t in result["themes"]]
        assert "development" in theme_names

    def test_themes_have_weight(self) -> None:
        """Test that themes have weight scores."""
        result = analyze_semantics("Generate code and write tests")

        for theme in result["themes"]:
            assert "weight" in theme
            assert 0.0 <= theme["weight"] <= 1.0

    def test_processing_time_recorded(self) -> None:
        """Test that processing time is recorded."""
        result = analyze_semantics("Test content for timing")
        assert result["processing_time_ms"] >= 0.0

    def test_min_confidence_filtering(self) -> None:
        """Test that min_confidence filters low-confidence results."""
        # With high threshold, should return fewer results
        result_high = analyze_semantics(
            "Test content",
            min_confidence=0.8,
        )
        result_low = analyze_semantics(
            "Test content",
            min_confidence=0.1,
        )

        # Low threshold should return same or more domains
        assert len(result_low["domains"]) >= len(result_high["domains"])


# =============================================================================
# map_semantic_to_intent_boost Tests
# =============================================================================


@pytest.mark.unit
class TestMapSemanticToIntentBoost:
    """Tests for map_semantic_to_intent_boost function."""

    def test_empty_result_returns_empty_boosts(self) -> None:
        """Test that empty semantic result returns no boosts."""
        empty_result = create_empty_semantic_result()
        boosts = map_semantic_to_intent_boost(empty_result)
        assert boosts == {}

    def test_api_domain_maps_to_api_design(self) -> None:
        """Test that api_design domain maps to api_design intent."""
        result = analyze_semantics("Create REST API endpoint")
        boosts = map_semantic_to_intent_boost(result)

        assert "api_design" in boosts
        assert boosts["api_design"] > 0.0

    def test_testing_domain_maps_to_testing(self) -> None:
        """Test that testing domain maps to testing intent."""
        result = analyze_semantics("Write unit tests with pytest")
        boosts = map_semantic_to_intent_boost(result)

        assert "testing" in boosts
        assert boosts["testing"] > 0.0

    def test_code_generation_domain_maps_correctly(self) -> None:
        """Test that code_generation domain maps correctly."""
        result = analyze_semantics("Generate Python function to process data")
        boosts = map_semantic_to_intent_boost(result)

        assert "code_generation" in boosts
        assert boosts["code_generation"] > 0.0

    def test_debugging_domain_maps_correctly(self) -> None:
        """Test that debugging domain maps correctly."""
        result = analyze_semantics("Fix the bug in error handling")
        boosts = map_semantic_to_intent_boost(result)

        assert "debugging" in boosts
        assert boosts["debugging"] > 0.0

    def test_documentation_domain_maps_correctly(self) -> None:
        """Test that documentation domain maps correctly."""
        result = analyze_semantics("Write documentation for the API")
        boosts = map_semantic_to_intent_boost(result)

        assert "documentation" in boosts
        assert boosts["documentation"] > 0.0

    def test_boost_capped_at_max(self) -> None:
        """Test that boosts are capped at maximum value (0.30)."""
        # Create content that would generate high boosts
        result = analyze_semantics(
            "api rest endpoint http request response authentication jwt oauth"
        )
        boosts = map_semantic_to_intent_boost(result)

        # All boosts should be capped at 0.30
        for intent, boost in boosts.items():
            assert boost <= 0.30, f"Boost for {intent} ({boost}) exceeds max 0.30"

    def test_multiple_sources_combine(self) -> None:
        """Test that boosts from multiple sources combine."""
        result = analyze_semantics("Create REST API with authentication and tests")
        boosts = map_semantic_to_intent_boost(result)

        # Should have multiple intent boosts
        assert len(boosts) >= 2

    def test_unknown_domains_ignored(self) -> None:
        """Test that unmapped content produces no boosts."""
        # Content with no matching domain keywords
        result: SemanticResult = {
            "concepts": [],
            "themes": [],
            "domains": [],
            "patterns": [],
            "domain_indicators": ["unknown_domain", "random_thing"],
            "topic_weights": {"unmapped": 0.8},
            "processing_time_ms": 0.0,
            "error": None,
        }
        boosts = map_semantic_to_intent_boost(result)

        # Should return empty dict (no valid mappings)
        assert boosts == {}


# =============================================================================
# Domain Coverage Tests
# =============================================================================


@pytest.mark.unit
class TestDomainCoverage:
    """Tests for domain keyword coverage."""

    @pytest.mark.parametrize(
        "content,expected_domain",
        [
            ("Create REST API endpoint", "api_design"),
            ("Write unit tests with pytest", "testing"),
            ("Generate Python function", "code_generation"),
            ("Fix the bug causing crash", "debugging"),
            ("Refactor the code for performance", "refactoring"),
            ("Write documentation and README", "documentation"),
            ("Design system architecture with microservices", "architecture"),
            ("Query the database using SQL", "database"),
            ("Deploy with Docker and Kubernetes", "devops"),
            ("Implement authentication and encryption", "security"),
            ("Analyze the code metrics", "analysis"),
        ],
    )
    def test_domain_detection(self, content: str, expected_domain: str) -> None:
        """Test that various content types detect correct domains."""
        result = analyze_semantics(content)
        assert expected_domain in result["domain_indicators"], (
            f"Expected {expected_domain} in domains for '{content}', "
            f"got {result['domain_indicators']}"
        )


# =============================================================================
# Integration with Intent Classification
# =============================================================================


@pytest.mark.unit
class TestIntegrationWithIntentClassification:
    """Tests for integration between semantic analysis and intent classification."""

    def test_semantic_boosts_can_enhance_classification(self) -> None:
        """Test that semantic boosts can be used to enhance classification."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            classify_intent,
        )

        content = "Create a REST API endpoint with tests"

        # Get base classification using threshold=0.0 to obtain the actual top intent
        base_result = classify_intent(content, confidence_threshold=0.0)

        # Get semantic analysis
        semantic_result = analyze_semantics(content)

        # Get boosts
        boosts = map_semantic_to_intent_boost(semantic_result)

        # Verify we can combine them (the actual combination logic is in the node)
        assert base_result["confidence"] > 0
        assert len(boosts) > 0

        # The combined confidence could be calculated as:
        base_intent = base_result["intent_category"]
        boost = boosts.get(base_intent, 0.0)
        enhanced_confidence = min(1.0, base_result["confidence"] + boost)

        assert enhanced_confidence >= base_result["confidence"]

    def test_semantic_and_tfidf_agree_on_strong_signals(self) -> None:
        """Test that semantic and TF-IDF agree on clear intent signals."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            classify_intent,
        )

        test_cases = [
            ("Generate a Python function to sort a list", "code_generation"),
            ("Write comprehensive unit tests", "testing"),
            ("Fix the authentication bug", "debugging"),
        ]

        for content, expected in test_cases:
            tfidf_result = classify_intent(content, confidence_threshold=0.0)
            semantic_result = analyze_semantics(content)
            boosts = map_semantic_to_intent_boost(semantic_result)

            # TF-IDF should classify correctly
            assert tfidf_result["intent_category"] == expected

            # Semantic analysis should boost the same intent
            assert expected in boosts or any(
                d in [expected, expected.replace("_", "")]
                for d in semantic_result["domain_indicators"]
            )


# =============================================================================
# Explicit Config Parameter Tests
# =============================================================================


@pytest.mark.unit
class TestExplicitConfigParameter:
    """Tests for explicit config parameter passing."""

    def test_analyze_semantics_with_default_config(
        self, default_semantic_config: ModelSemanticAnalysisConfig
    ) -> None:
        """Test that analyze_semantics accepts explicit default config."""
        result = analyze_semantics(
            "Create REST API endpoint",
            config=default_semantic_config,
        )
        assert "api_design" in result["domain_indicators"]

    def test_analyze_semantics_with_none_config_uses_default(self) -> None:
        """Test that None config uses DEFAULT_SEMANTIC_CONFIG."""
        result_none = analyze_semantics("Create REST API endpoint", config=None)
        result_default = analyze_semantics(
            "Create REST API endpoint", config=DEFAULT_SEMANTIC_CONFIG
        )

        # Results should be equivalent
        assert result_none["domain_indicators"] == result_default["domain_indicators"]

    def test_map_semantic_with_custom_boost_cap(
        self, custom_semantic_config: ModelSemanticAnalysisConfig
    ) -> None:
        """Test that custom boost cap is respected."""
        result = analyze_semantics(
            "api rest endpoint http request response authentication jwt oauth",
            config=custom_semantic_config,
        )
        boosts = map_semantic_to_intent_boost(result, config=custom_semantic_config)

        # Custom config has max_boost_cap=0.5
        for intent, boost in boosts.items():
            assert boost <= 0.5, f"Boost for {intent} ({boost}) exceeds custom max 0.5"

    def test_map_semantic_with_default_boost_cap(self) -> None:
        """Test that default boost cap (0.30) is applied."""
        result = analyze_semantics(
            "api rest endpoint http request response authentication jwt oauth"
        )
        boosts = map_semantic_to_intent_boost(result)

        # Default config has max_boost_cap=0.30
        for intent, boost in boosts.items():
            assert boost <= 0.30, f"Boost for {intent} ({boost}) exceeds default max"

    def test_custom_config_with_modified_scoring(self) -> None:
        """Test that custom scoring config affects results."""
        # Create config with higher minimum confidence
        # (default_min_confidence is on ModelSemanticAnalysisConfig, not scoring)
        high_min_config = ModelSemanticAnalysisConfig(
            default_min_confidence=0.9,
        )

        # With high minimum confidence, should get fewer results
        result_high = analyze_semantics(
            "Test content for scoring",
            config=high_min_config,
        )

        # Default config with lower threshold
        result_default = analyze_semantics("Test content for scoring")

        # High threshold should filter more
        assert len(result_high["domains"]) <= len(result_default["domains"])

    def test_custom_limits_config(self) -> None:
        """Test that custom limits config affects results."""
        # Create config with lower limits
        # (ModelSemanticLimitsConfig has max_concepts and max_domain_indicators)
        limited_config = ModelSemanticAnalysisConfig(
            limits=ModelSemanticLimitsConfig(
                max_concepts=2,
                max_domain_indicators=2,
            ),
        )

        result = analyze_semantics(
            "Create REST API with testing and documentation and debugging",
            config=limited_config,
        )

        # Should respect limits
        assert len(result["concepts"]) <= 2
        assert len(result["domain_indicators"]) <= 2

    def test_default_semantic_config_is_frozen(self) -> None:
        """Test that DEFAULT_SEMANTIC_CONFIG is immutable."""
        # Pydantic models with frozen=True should raise ValidationError on modification
        with pytest.raises(ValidationError):
            DEFAULT_SEMANTIC_CONFIG.boosts.max_boost_cap = 0.99  # type: ignore[misc]
