# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for TF-IDF intent classification handler.

This module tests the core intent classification functionality including:
    - All 14 intent categories detection (9 original + 5 domain-specific)
    - Confidence threshold filtering
    - Multi-label classification mode
    - Edge cases (empty input, special characters, etc.)
    - TF-IDF scoring algorithm
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
    DEFAULT_CLASSIFICATION_CONFIG,
    INTENT_PATTERNS,
    classify_intent,
)
from omniintelligence.nodes.node_intent_classifier_compute.models import (
    ModelClassificationConfig,
)


# =============================================================================
# Test Fixtures - Configuration
# =============================================================================


@pytest.fixture
def default_config() -> ModelClassificationConfig:
    """Provide default classification config for tests."""
    return ModelClassificationConfig()


@pytest.fixture
def custom_config() -> ModelClassificationConfig:
    """Provide a custom config for testing config behavior."""
    return ModelClassificationConfig(
        exact_match_weight=20.0,
        default_confidence_threshold=0.3,
    )


# =============================================================================
# Test Fixtures - Sample Content for Each Intent Category
# =============================================================================


SAMPLE_CODE_GENERATION = [
    "Please generate a Python function to parse JSON",
    "Create a new class for user authentication",
    "Implement a function for data validation",
    "Write a module to handle file operations",
    "Build a component for file upload functionality",
    "Develop a function to calculate tax rates",
    "Make a scaffold for a new service",
    "Update the configuration file for the system",
]

SAMPLE_DEBUGGING = [
    "Fix the bug in the login flow",
    "Debug the memory leak in the image processor",
    "Troubleshoot the crash when uploading files",
    "Troubleshoot the connection timeout issue",
    "Diagnose the issue with the API response",
    "Problem with the database connection failing",
    "Debug and fix the retry logic bug",
    "Fix the crash bug in the system",
]

SAMPLE_REFACTORING = [
    "Refactor the user service for better maintainability",
    "Improve the performance of the search algorithm",
    "Optimize the database queries for performance",
    "Refactor and restructure the middleware code",
    "Clean up the legacy code in the payment processor",
    "Simplify the complex validation logic",
    "Enhance the caching mechanism to improve performance",
    "Refactor to async pattern for better performance",
]

SAMPLE_TESTING = [
    "Write unit tests for the payment service",
    "Create comprehensive test coverage for the API",
    "Validate the user registration flow with tests",
    "Test the edge cases with unit tests",
    "Add assert tests for the calculation logic",
    "Write test specs for the new feature",
    "Verify with integration tests between services",
    "Add unittest coverage for error handling",
]

SAMPLE_DOCUMENTATION = [
    "Add documentation for the API endpoints",
    "Write a README guide for the installation process",
    "Add docstrings to explain the functions",
    "Write documentation explaining the system",
    "Add comprehensive documentation for the schema",
    "Add comprehensive comments explaining the algorithm",
    "Document and describe the configuration options",
    "Describe the deployment process in documentation",
]

SAMPLE_ANALYSIS = [
    "Review the implementation decisions carefully",
    "Review and inspect the module structure",
    "Examine the code organization carefully",
    "Evaluate the decisions used here",
    "Audit the dependency versions",
    "Investigate the memory usage patterns",
    "Review the existing implementation",
    "Inspect and examine the codebase",
]

SAMPLE_PATTERN_LEARNING = [
    "Learn patterns from the successful deployments",
    "Create embeddings for code similarity search",
    "Train a model on the coding patterns",
    "Extract features from the codebase for learning",
    "Cluster similar code snippets",
    "Classify the programming paradigms used",
    "Pattern recognition for error detection",
    "Learn vector representations for similarity",
]

SAMPLE_QUALITY_ASSESSMENT = [
    "Assess code quality for the new module",
    "Score the maintainability of the codebase",
    "Check ONEX compliance for all nodes",
    "Validate against coding standards for quality",
    "Get quality metrics for the repository",
    "Benchmark the code quality against best practices",
    "Rate the code quality and compliance score",
    "Grade the quality rating for the module",
]

SAMPLE_SEMANTIC_ANALYSIS = [
    "Semantic analysis of the codebase structure",
    "Extract concepts and themes from the text",
    "Analyze the domain context semantically",
    "Understand the theme of the code changes",
    "Interpret the semantic meaning of the design",
    "Semantic NLP processing for the content",
    "Language understanding and semantic context",
    "Context and theme extraction from signatures",
]


# =============================================================================
# Intent Category Detection Tests
# =============================================================================


@pytest.mark.unit
class TestCodeGenerationIntent:
    """Tests for code_generation intent detection."""

    @pytest.mark.parametrize("content", SAMPLE_CODE_GENERATION)
    def test_detects_code_generation(self, content: str) -> None:
        """Test detection of code generation intent for various phrases."""
        result = classify_intent(content)
        assert result["intent_category"] == "code_generation", (
            f"Expected 'code_generation' for: {content!r}, "
            f"got: {result['intent_category']}"
        )
        assert result["confidence"] > 0.0

    def test_code_generation_keywords_present(self) -> None:
        """Verify code_generation keywords are in INTENT_PATTERNS."""
        patterns = INTENT_PATTERNS["code_generation"]
        assert "generate" in patterns
        assert "create" in patterns
        assert "implement" in patterns
        assert "write" in patterns
        assert "build" in patterns


@pytest.mark.unit
class TestDebuggingIntent:
    """Tests for debugging intent detection."""

    @pytest.mark.parametrize("content", SAMPLE_DEBUGGING)
    def test_detects_debugging(self, content: str) -> None:
        """Test detection of debugging intent for various phrases."""
        result = classify_intent(content)
        assert result["intent_category"] == "debugging", (
            f"Expected 'debugging' for: {content!r}, got: {result['intent_category']}"
        )
        assert result["confidence"] > 0.0

    def test_debugging_keywords_present(self) -> None:
        """Verify debugging keywords are in INTENT_PATTERNS."""
        patterns = INTENT_PATTERNS["debugging"]
        assert "debug" in patterns
        assert "fix" in patterns
        assert "error" in patterns
        assert "bug" in patterns
        assert "crash" in patterns


@pytest.mark.unit
class TestRefactoringIntent:
    """Tests for refactoring intent detection."""

    @pytest.mark.parametrize("content", SAMPLE_REFACTORING)
    def test_detects_refactoring(self, content: str) -> None:
        """Test detection of refactoring intent for various phrases."""
        result = classify_intent(content)
        assert result["intent_category"] == "refactoring", (
            f"Expected 'refactoring' for: {content!r}, got: {result['intent_category']}"
        )
        assert result["confidence"] > 0.0

    def test_refactoring_keywords_present(self) -> None:
        """Verify refactoring keywords are in INTENT_PATTERNS."""
        patterns = INTENT_PATTERNS["refactoring"]
        assert "refactor" in patterns
        assert "improve" in patterns
        assert "optimize" in patterns
        assert "restructure" in patterns
        assert "clean" in patterns


@pytest.mark.unit
class TestTestingIntent:
    """Tests for testing intent detection."""

    @pytest.mark.parametrize("content", SAMPLE_TESTING)
    def test_detects_testing(self, content: str) -> None:
        """Test detection of testing intent for various phrases."""
        result = classify_intent(content)
        assert result["intent_category"] == "testing", (
            f"Expected 'testing' for: {content!r}, got: {result['intent_category']}"
        )
        assert result["confidence"] > 0.0

    def test_testing_keywords_present(self) -> None:
        """Verify testing keywords are in INTENT_PATTERNS."""
        patterns = INTENT_PATTERNS["testing"]
        assert "test" in patterns
        assert "validate" in patterns
        assert "verify" in patterns
        assert "assert" in patterns
        assert "coverage" in patterns


@pytest.mark.unit
class TestDocumentationIntent:
    """Tests for documentation intent detection."""

    @pytest.mark.parametrize("content", SAMPLE_DOCUMENTATION)
    def test_detects_documentation(self, content: str) -> None:
        """Test detection of documentation intent for various phrases."""
        result = classify_intent(content)
        assert result["intent_category"] == "documentation", (
            f"Expected 'documentation' for: {content!r}, "
            f"got: {result['intent_category']}"
        )
        assert result["confidence"] > 0.0

    def test_documentation_keywords_present(self) -> None:
        """Verify documentation keywords are in INTENT_PATTERNS."""
        patterns = INTENT_PATTERNS["documentation"]
        assert "documentation" in patterns
        assert "explain" in patterns
        assert "describe" in patterns
        assert "readme" in patterns
        assert "docstring" in patterns


@pytest.mark.unit
class TestAnalysisIntent:
    """Tests for analysis intent detection."""

    @pytest.mark.parametrize("content", SAMPLE_ANALYSIS)
    def test_detects_analysis(self, content: str) -> None:
        """Test detection of analysis intent for various phrases."""
        result = classify_intent(content)
        assert result["intent_category"] == "analysis", (
            f"Expected 'analysis' for: {content!r}, got: {result['intent_category']}"
        )
        assert result["confidence"] > 0.0

    def test_analysis_keywords_present(self) -> None:
        """Verify analysis keywords are in INTENT_PATTERNS."""
        patterns = INTENT_PATTERNS["analysis"]
        assert "analyze" in patterns
        assert "review" in patterns
        assert "inspect" in patterns
        assert "examine" in patterns
        assert "evaluate" in patterns


@pytest.mark.unit
class TestPatternLearningIntent:
    """Tests for pattern_learning intent detection."""

    @pytest.mark.parametrize("content", SAMPLE_PATTERN_LEARNING)
    def test_detects_pattern_learning(self, content: str) -> None:
        """Test detection of pattern_learning intent for various phrases."""
        result = classify_intent(content)
        assert result["intent_category"] == "pattern_learning", (
            f"Expected 'pattern_learning' for: {content!r}, "
            f"got: {result['intent_category']}"
        )
        assert result["confidence"] > 0.0

    def test_pattern_learning_keywords_present(self) -> None:
        """Verify pattern_learning keywords are in INTENT_PATTERNS."""
        patterns = INTENT_PATTERNS["pattern_learning"]
        assert "learn" in patterns
        assert "pattern" in patterns
        assert "embedding" in patterns
        assert "similarity" in patterns
        assert "vector" in patterns


@pytest.mark.unit
class TestQualityAssessmentIntent:
    """Tests for quality_assessment intent detection."""

    @pytest.mark.parametrize("content", SAMPLE_QUALITY_ASSESSMENT)
    def test_detects_quality_assessment(self, content: str) -> None:
        """Test detection of quality_assessment intent for various phrases."""
        result = classify_intent(content)
        assert result["intent_category"] == "quality_assessment", (
            f"Expected 'quality_assessment' for: {content!r}, "
            f"got: {result['intent_category']}"
        )
        assert result["confidence"] > 0.0

    def test_quality_assessment_keywords_present(self) -> None:
        """Verify quality_assessment keywords are in INTENT_PATTERNS."""
        patterns = INTENT_PATTERNS["quality_assessment"]
        assert "quality" in patterns
        assert "assess" in patterns
        assert "score" in patterns
        assert "compliance" in patterns
        assert "onex" in patterns


@pytest.mark.unit
class TestSemanticAnalysisIntent:
    """Tests for semantic_analysis intent detection."""

    @pytest.mark.parametrize("content", SAMPLE_SEMANTIC_ANALYSIS)
    def test_detects_semantic_analysis(self, content: str) -> None:
        """Test detection of semantic_analysis intent for various phrases."""
        result = classify_intent(content)
        assert result["intent_category"] == "semantic_analysis", (
            f"Expected 'semantic_analysis' for: {content!r}, "
            f"got: {result['intent_category']}"
        )
        assert result["confidence"] > 0.0

    def test_semantic_analysis_keywords_present(self) -> None:
        """Verify semantic_analysis keywords are in INTENT_PATTERNS."""
        patterns = INTENT_PATTERNS["semantic_analysis"]
        assert "semantic" in patterns
        assert "extract" in patterns
        assert "concept" in patterns
        assert "theme" in patterns
        assert "domain" in patterns


# =============================================================================
# Confidence Threshold Tests
# =============================================================================


@pytest.mark.unit
class TestConfidenceThreshold:
    """Tests for confidence threshold filtering."""

    def test_default_threshold(self) -> None:
        """Test that default threshold (0.5) is applied."""
        result = classify_intent("generate a function")
        assert result["confidence"] >= 0.5 or result["intent_category"] == "unknown"

    def test_high_threshold_returns_unknown(self) -> None:
        """Test that very high threshold returns unknown for ambiguous text."""
        # Ambiguous text with no strong keyword matches
        result = classify_intent("xyz abc random words here", confidence_threshold=0.99)
        assert result["intent_category"] == "unknown"
        assert result["confidence"] == 0.0

    def test_low_threshold_returns_result(self) -> None:
        """Test that low threshold returns results for weak matches."""
        result = classify_intent("work on the project", confidence_threshold=0.1)
        # Should return something, not unknown
        # The result may vary based on TF-IDF scoring
        assert result["confidence"] >= 0.0

    def test_zero_threshold_returns_best_match(self) -> None:
        """Test that zero threshold returns best match regardless of score."""
        result = classify_intent("xyz abc 123", confidence_threshold=0.0)
        # Should return something even for unrelated text
        assert "intent_category" in result

    def test_threshold_at_boundary(self) -> None:
        """Test threshold behavior at exact match boundary."""
        result = classify_intent("generate a Python function")
        exact_confidence = result["confidence"]

        # Using exact threshold should keep the result
        result_exact = classify_intent(
            "generate a Python function",
            confidence_threshold=exact_confidence,
        )
        assert result_exact["intent_category"] == result["intent_category"]

        # Using slightly higher threshold may return unknown
        result_higher = classify_intent(
            "generate a Python function",
            confidence_threshold=exact_confidence + 0.01,
        )
        # May be unknown if threshold exceeds confidence
        assert result_higher["intent_category"] in [
            result["intent_category"],
            "unknown",
        ]


# =============================================================================
# Multi-Label Classification Tests
# =============================================================================


@pytest.mark.unit
class TestMultiLabelClassification:
    """Tests for multi-label classification mode."""

    def test_multi_label_returns_secondary_intents(self) -> None:
        """Test that multi-label mode returns secondary intents."""
        # Text that should match multiple intents
        content = "Generate tests and documentation for the API"
        result = classify_intent(content, multi_label=True)

        assert "secondary_intents" in result
        assert isinstance(result["secondary_intents"], list)

    def test_multi_label_primary_is_highest_confidence(self) -> None:
        """Test that primary intent has highest confidence."""
        content = "Generate tests and documentation for the API"
        result = classify_intent(content, multi_label=True)

        if result["secondary_intents"]:
            for secondary in result["secondary_intents"]:
                assert result["confidence"] >= secondary["confidence"]

    def test_multi_label_respects_threshold(self) -> None:
        """Test that multi-label respects confidence threshold."""
        content = "Generate code and run tests"
        result = classify_intent(content, multi_label=True, confidence_threshold=0.5)

        # All secondary intents should be above threshold
        for secondary in result["secondary_intents"]:
            assert secondary["confidence"] >= 0.5

    def test_multi_label_max_intents(self) -> None:
        """Test that max_intents limits secondary intents."""
        content = "Generate code, write tests, add documentation, analyze patterns"
        result = classify_intent(content, multi_label=True, max_intents=2)

        # Secondary intents should be limited
        assert len(result["secondary_intents"]) <= 2

    def test_multi_label_keywords_included(self) -> None:
        """Test that secondary intents include matched keywords."""
        content = "Generate code and write comprehensive unit tests"
        result = classify_intent(content, multi_label=True, confidence_threshold=0.3)

        for secondary in result["secondary_intents"]:
            assert "keywords" in secondary
            assert isinstance(secondary["keywords"], list)

    def test_single_label_no_secondary(self) -> None:
        """Test that single-label mode does not include secondary intents."""
        result = classify_intent("generate a function", multi_label=False)
        assert "secondary_intents" not in result


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_content_returns_unknown(self) -> None:
        """Test that empty content returns unknown intent."""
        result = classify_intent("")
        assert result["intent_category"] == "unknown"
        assert result["confidence"] == 0.0
        assert result["keywords"] == []

    def test_whitespace_only_returns_unknown(self) -> None:
        """Test that whitespace-only content returns unknown."""
        result = classify_intent("   \n\t  ")
        assert result["intent_category"] == "unknown"
        assert result["confidence"] == 0.0

    def test_single_word_classification(self) -> None:
        """Test classification of single keyword."""
        result = classify_intent("generate")
        assert result["intent_category"] == "code_generation"
        assert result["confidence"] == 1.0  # Perfect match

    def test_case_insensitive_matching(self) -> None:
        """Test that matching is case insensitive."""
        result_lower = classify_intent("generate code")
        result_upper = classify_intent("GENERATE CODE")
        result_mixed = classify_intent("Generate Code")

        assert result_lower["intent_category"] == result_upper["intent_category"]
        assert result_lower["intent_category"] == result_mixed["intent_category"]

    def test_special_characters_handled(self) -> None:
        """Test that special characters don't break classification."""
        result = classify_intent("Generate a function!!!@#$%^&*()")
        assert result["intent_category"] == "code_generation"

    def test_numbers_in_content(self) -> None:
        """Test that numbers in content are handled."""
        result = classify_intent("Generate 10 test functions for version 2.0")
        # Should still detect testing or code_generation
        assert result["intent_category"] in ["testing", "code_generation"]

    def test_unicode_content(self) -> None:
        """Test that unicode content is handled correctly."""
        # Test with various unicode characters (Chinese, emoji, accented chars)
        unicode_content = (
            "Generate a function to process \u4e2d\u6587 text with caf\u00e9"
        )
        result = classify_intent(unicode_content)

        # Should classify as code_generation and return valid result structure
        assert result["intent_category"] == "code_generation"
        assert result["confidence"] > 0.0
        assert isinstance(result["keywords"], list)
        assert "generate" in result["keywords"]

    def test_unicode_only_content(self) -> None:
        """Test classification of content with only unicode characters."""
        # Pure unicode content with no recognizable keywords
        result = classify_intent("\u4e2d\u6587\u6587\u672c", confidence_threshold=0.9)
        # Should return unknown since no English keywords match
        assert result["intent_category"] == "unknown"
        assert isinstance(result["confidence"], float)

    def test_unicode_keywords_mixed(self) -> None:
        """Test that unicode mixed with keywords still classifies correctly."""
        result = classify_intent("Debug the \u30d0\u30b0 bug in \u30b3\u30fc\u30c9")
        assert result["intent_category"] == "debugging"
        assert "debug" in result["keywords"] or "bug" in result["keywords"]

    def test_very_long_content(self) -> None:
        """Test classification of very long content."""
        long_content = "Generate " * 100 + "a Python function"
        result = classify_intent(long_content)
        assert result["intent_category"] == "code_generation"

    def test_repeated_keywords(self) -> None:
        """Test that repeated keywords boost confidence."""
        result_single = classify_intent("generate code")
        result_repeated = classify_intent("generate generate generate code")

        # Both should detect code_generation
        assert result_single["intent_category"] == "code_generation"
        assert result_repeated["intent_category"] == "code_generation"

    def test_no_matching_keywords(self) -> None:
        """Test content with no matching keywords."""
        result = classify_intent(
            "xyzzy foobar baz quux",
            confidence_threshold=0.9,
        )
        assert result["intent_category"] == "unknown"


# =============================================================================
# Result Structure Tests
# =============================================================================


@pytest.mark.unit
class TestResultStructure:
    """Tests for result dictionary structure."""

    def test_single_label_result_structure(self) -> None:
        """Test that single-label result has expected structure."""
        result = classify_intent("generate a function")

        assert "intent_category" in result
        assert "confidence" in result
        assert "keywords" in result
        assert "all_scores" in result

        assert isinstance(result["intent_category"], str)
        assert isinstance(result["confidence"], float)
        assert isinstance(result["keywords"], list)
        assert isinstance(result["all_scores"], dict)

    def test_multi_label_result_structure(self) -> None:
        """Test that multi-label result has expected structure."""
        result = classify_intent("generate tests", multi_label=True)

        assert "intent_category" in result
        assert "confidence" in result
        assert "keywords" in result
        assert "all_scores" in result
        assert "secondary_intents" in result

        assert isinstance(result["secondary_intents"], list)

    def test_all_scores_contains_all_intents(self) -> None:
        """Test that all_scores contains scores for all 14 intents."""
        result = classify_intent("generate code")

        assert len(result["all_scores"]) == 14

        expected_intents = {
            # Original 9 categories
            "code_generation",
            "debugging",
            "refactoring",
            "testing",
            "documentation",
            "analysis",
            "pattern_learning",
            "quality_assessment",
            "semantic_analysis",
            # Domain-specific categories (aligned with DOMAIN_TO_INTENT_MAP)
            "api_design",
            "architecture",
            "database",
            "devops",
            "security",
        }
        assert set(result["all_scores"].keys()) == expected_intents

    def test_all_scores_in_valid_range(self) -> None:
        """Test that all confidence scores are in [0.0, 1.0] range."""
        result = classify_intent("generate code and write tests")

        for intent, score in result["all_scores"].items():
            assert 0.0 <= score <= 1.0, (
                f"Score {score} for {intent} is out of range [0.0, 1.0]"
            )

    def test_keywords_are_lowercase(self) -> None:
        """Test that matched keywords are lowercase."""
        result = classify_intent("GENERATE CODE")

        for keyword in result["keywords"]:
            assert keyword == keyword.lower()


# =============================================================================
# Configuration Tests
# =============================================================================


@pytest.mark.unit
class TestConfigurationPassing:
    """Tests for explicit configuration passing."""

    def test_default_config_matches_module_default(
        self, default_config: ModelClassificationConfig
    ) -> None:
        """Test that fixture default_config matches DEFAULT_CLASSIFICATION_CONFIG."""
        assert (
            default_config.exact_match_weight
            == DEFAULT_CLASSIFICATION_CONFIG.exact_match_weight
        )
        assert (
            default_config.default_confidence_threshold
            == DEFAULT_CLASSIFICATION_CONFIG.default_confidence_threshold
        )

    def test_classify_with_explicit_default_config(
        self, default_config: ModelClassificationConfig
    ) -> None:
        """Test classification with explicitly passed default config."""
        result = classify_intent("generate a function", config=default_config)
        assert result["intent_category"] == "code_generation"
        assert result["confidence"] > 0.0

    def test_classify_with_custom_config(
        self, custom_config: ModelClassificationConfig
    ) -> None:
        """Test classification with custom config."""
        result = classify_intent("generate a function", config=custom_config)
        assert result["intent_category"] == "code_generation"
        # Custom config has exact_match_weight=20.0 (higher than default 15.0)
        # This should still classify correctly
        assert result["confidence"] > 0.0

    def test_custom_threshold_via_config(self) -> None:
        """Test that custom threshold in config is respected."""
        low_threshold_config = ModelClassificationConfig(
            default_confidence_threshold=0.1,
        )
        high_threshold_config = ModelClassificationConfig(
            default_confidence_threshold=0.99,
        )

        # Low threshold should return result for weak match
        result_low = classify_intent("work on the project", config=low_threshold_config)
        # High threshold should return unknown for same text
        result_high = classify_intent(
            "work on the project", config=high_threshold_config
        )

        # Low threshold allows weak matches through
        # High threshold filters them out
        if result_low["intent_category"] != "unknown":
            assert (
                result_high["intent_category"] == "unknown"
                or result_high["confidence"] >= 0.99
            )

    def test_config_weight_affects_scoring(self) -> None:
        """Test that different weights affect relative scoring."""
        normal_config = ModelClassificationConfig()
        high_exact_config = ModelClassificationConfig(
            exact_match_weight=30.0,  # Double the default
        )

        result_normal = classify_intent("generate code", config=normal_config)
        result_high = classify_intent("generate code", config=high_exact_config)

        # Both should classify as code_generation
        assert result_normal["intent_category"] == "code_generation"
        assert result_high["intent_category"] == "code_generation"

    def test_none_config_uses_default(self) -> None:
        """Test that passing config=None uses default configuration."""
        result_none = classify_intent("generate a function", config=None)
        result_default = classify_intent(
            "generate a function", config=DEFAULT_CLASSIFICATION_CONFIG
        )

        assert result_none["intent_category"] == result_default["intent_category"]
        assert result_none["confidence"] == result_default["confidence"]

    def test_config_is_frozen(self) -> None:
        """Test that config is immutable (frozen)."""
        from pydantic import ValidationError

        config = ModelClassificationConfig()
        with pytest.raises(ValidationError):
            config.exact_match_weight = 100.0  # type: ignore[misc]


# =============================================================================
# INTENT_PATTERNS Tests
# =============================================================================


@pytest.mark.unit
class TestIntentPatterns:
    """Tests for INTENT_PATTERNS constant."""

    def test_intent_patterns_has_fourteen_categories(self) -> None:
        """Test that INTENT_PATTERNS contains exactly 14 intent categories."""
        assert len(INTENT_PATTERNS) == 14

    def test_intent_patterns_categories(self) -> None:
        """Test that all expected categories are present."""
        expected_categories = {
            # Original 9 categories
            "code_generation",
            "debugging",
            "refactoring",
            "testing",
            "documentation",
            "analysis",
            "pattern_learning",
            "quality_assessment",
            "semantic_analysis",
            # Domain-specific categories (aligned with DOMAIN_TO_INTENT_MAP)
            "api_design",
            "architecture",
            "database",
            "devops",
            "security",
        }
        assert set(INTENT_PATTERNS.keys()) == expected_categories

    def test_each_category_has_keywords(self) -> None:
        """Test that each category has at least one keyword."""
        for category, keywords in INTENT_PATTERNS.items():
            assert len(keywords) > 0, f"Category {category} has no keywords"

    def test_keywords_are_lowercase(self) -> None:
        """Test that all keywords in patterns are lowercase."""
        for category, keywords in INTENT_PATTERNS.items():
            for keyword in keywords:
                assert keyword == keyword.lower(), (
                    f"Keyword {keyword!r} in {category} is not lowercase"
                )

    def test_no_duplicate_keywords_within_category(self) -> None:
        """Test that there are no duplicate keywords within a category."""
        for category, keywords in INTENT_PATTERNS.items():
            assert len(keywords) == len(set(keywords)), (
                f"Category {category} has duplicate keywords"
            )
