# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for handle_intent_classification — the orchestrating handler.

These tests verify the integration of the langextract semantic enrichment
pipeline with TF-IDF classification inside handle_intent_classification().

Coverage includes:
- Direct unit test coverage for the orchestrating handler
- The semantic boost path (analyze_semantics -> map_semantic_to_intent_boost ->
  score_boosts kwarg in classify_intent) tested end-to-end
- Fallback behavior when semantic analysis fails

Originally tracked as OMN-2377 (langextract integration tests). All tests
are complete and cover the full boost pipeline.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
    HandlerIntentClassification,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_langextract import (
    HandlerSemanticAnalysis,
)
from omniintelligence.nodes.node_intent_classifier_compute.models import (
    ModelClassificationConfig,
    ModelClassifyIntentRequest,
    ModelIntentClassificationInput,
    ModelIntentClassificationOutput,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_input(content: str) -> ModelIntentClassificationInput:
    """Construct a ModelIntentClassificationInput with minimal required fields."""
    return ModelIntentClassificationInput(content=content)


_DEFAULT_CONFIG = ModelClassificationConfig()


# =============================================================================
# handle_intent_classification direct coverage
# =============================================================================


@pytest.mark.unit
class TestHandleIntentClassificationIntegration:
    """Tests for handle_intent_classification — the orchestrating handler.

    These tests exercise the full langextract + TF-IDF pipeline via the
    orchestrating handler, which was previously completely untested.
    """

    def test_returns_success_true_for_valid_input(self) -> None:
        """handle_intent_classification returns success=True on valid input."""
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
            _make_input("Generate a Python function")
        )
        assert result.success is True

    def test_returns_model_intent_classification_output(self) -> None:
        """Return type is ModelIntentClassificationOutput with required fields."""
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
            _make_input("Write unit tests")
        )
        assert isinstance(result, ModelIntentClassificationOutput)
        assert isinstance(result.intent_category, str)
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0

    def test_classifies_code_generation_correctly(self) -> None:
        """Strong code generation signal produces code_generation intent."""
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
            _make_input("Generate a Python function to process data")
        )
        assert result.success is True
        assert result.intent_category == "code_generation"

    def test_classifies_testing_correctly(self) -> None:
        """Strong testing signal produces testing intent."""
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
            _make_input("Write comprehensive unit tests with pytest")
        )
        assert result.success is True
        assert result.intent_category == "testing"

    def test_classifies_debugging_correctly(self) -> None:
        """Strong debugging signal produces debugging intent."""
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
            _make_input("Fix the authentication bug causing crash")
        )
        assert result.success is True
        assert result.intent_category == "debugging"

    def test_returns_failure_for_empty_content(self) -> None:
        """Empty or whitespace-only content returns success=False.

        ModelIntentClassificationInput enforces min_length=1, so we must
        test the validation path by patching the validated content on the
        input model after construction, or verify the handler's own guard.
        """
        # Pydantic enforces min_length=1 at construction — test that the
        # handler's input guard produces a graceful error response when called
        # via the handler directly with a model whose content is a single space
        # (min_length=1 allows " ").
        # The handler checks `not input_data.content.strip()` internally.
        input_data = ModelIntentClassificationInput(content=" ")
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(input_data)
        assert result.success is False
        assert result.intent_category == "unknown"
        assert result.confidence == 0.0

    def test_processing_time_is_recorded(self) -> None:
        """processing_time_ms is non-negative on successful classification."""
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
            _make_input("Generate a REST API endpoint")
        )
        assert result.processing_time_ms >= 0.0

    def test_metadata_contains_status_completed(self) -> None:
        """Successful classification sets metadata.status == 'completed'."""
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
            _make_input("Write tests for the API")
        )
        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.get("status") == "completed"

    def test_metadata_contains_raw_scores(self) -> None:
        """Successful classification includes raw_scores in metadata."""
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
            _make_input("Generate a Python class")
        )
        assert result.metadata is not None
        raw_scores = result.metadata.get("raw_scores", {})
        assert isinstance(raw_scores, dict)
        assert len(raw_scores) > 0

    def test_secondary_intents_is_list(self) -> None:
        """secondary_intents is always a list (never None)."""
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
            _make_input("Create REST API with tests")
        )
        assert isinstance(result.secondary_intents, list)

    def test_keywords_is_list(self) -> None:
        """keywords is always a list (never None)."""
        result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
            _make_input("Fix the bug in error handling")
        )
        assert isinstance(result.keywords, list)


# =============================================================================
# Langextract semantic boost integration with handle_intent_classification
# =============================================================================


@pytest.mark.unit
class TestLangextractBoostIntegration:
    """Tests that verify langextract boosts flow into handle_intent_classification.

    These are the critical integration tests. They verify:
    1. analyze_semantics is called inside handle_intent_classification
    2. Its output is converted to boosts via map_semantic_to_intent_boost
    3. Boosts affect classify_intent scoring (score_boosts kwarg)
    4. Fallback works when semantic analysis raises an exception
    """

    def test_semantic_boost_is_called_during_handle(self) -> None:
        """analyze_semantics is called inside handle_intent_classification."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_langextract import (
            HandlerSemanticAnalysis,
        )

        with patch(
            "omniintelligence.nodes.node_intent_classifier_compute.handlers"
            ".handler_intent_classification.HandlerSemanticAnalysis.handle",
            wraps=HandlerSemanticAnalysis().handle,
        ) as mock_analyze:
            HandlerIntentClassification(_DEFAULT_CONFIG).handle(
                _make_input("Generate Python code")
            )
            assert mock_analyze.call_count >= 1

    def test_map_semantic_to_intent_boost_is_called_on_success(self) -> None:
        """map_semantic_to_intent_boost is called when analyze_semantics succeeds."""
        with patch(
            "omniintelligence.nodes.node_intent_classifier_compute.handlers"
            ".handler_intent_classification.HandlerSemanticIntentBoost.handle",
            wraps=__import__(
                "omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_langextract",
                fromlist=["HandlerSemanticIntentBoost"],
            )
            .HandlerSemanticIntentBoost()
            .handle,
        ) as mock_boost:
            HandlerIntentClassification(_DEFAULT_CONFIG).handle(
                _make_input("Create REST API endpoint with authentication")
            )
            mock_boost.assert_called_once()

    def test_semantic_exception_falls_back_to_tfidf_only(self) -> None:
        """When analyze_semantics raises, handler falls back to TF-IDF-only scoring.

        This is the critical fallback path: langextract failure must not
        prevent intent classification from succeeding.
        """
        with patch(
            "omniintelligence.nodes.node_intent_classifier_compute.handlers"
            ".handler_intent_classification.HandlerSemanticAnalysis.handle",
            side_effect=RuntimeError("simulated semantic analysis failure"),
        ):
            result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
                _make_input("Generate a Python function")
            )
            # Must still succeed — fallback to TF-IDF-only
            assert result.success is True
            assert result.intent_category == "code_generation"

    def test_semantic_error_result_skips_boost_mapping(self) -> None:
        """When analyze_semantics returns error, map_semantic_to_intent_boost is not called."""
        error_result = HandlerSemanticAnalysis.create_empty_semantic_result(
            error="forced error"
        )

        with (
            patch(
                "omniintelligence.nodes.node_intent_classifier_compute.handlers"
                ".handler_intent_classification.HandlerSemanticAnalysis.handle",
                return_value=error_result,
            ),
            patch(
                "omniintelligence.nodes.node_intent_classifier_compute.handlers"
                ".handler_intent_classification.HandlerSemanticIntentBoost.handle",
            ) as mock_boost,
        ):
            result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
                _make_input("Generate Python code")
            )
            # Boost mapping should NOT be called when semantic analysis has error
            mock_boost.assert_not_called()
            # But handler should still succeed via TF-IDF
            assert result.success is True

    def test_boosts_propagate_to_scoring(self) -> None:
        """Semantic boosts from langextract propagate into classify_intent score_boosts.

        Verifies that the boost dict produced by map_semantic_to_intent_boost
        is actually passed as score_boosts to classify_intent, altering scores.
        """
        # 999.0 is intentionally >> max possible TF-IDF score (0.0-1.0 after softmax),
        # guaranteeing the boost always overrides the baseline winner regardless of content.
        large_boost: dict[str, float] = {"testing": 999.0}

        with patch(
            "omniintelligence.nodes.node_intent_classifier_compute.handlers"
            ".handler_intent_classification.HandlerSemanticIntentBoost.handle",
            return_value=large_boost,
        ):
            result = HandlerIntentClassification(_DEFAULT_CONFIG).handle(
                _make_input("generate implement create build develop")
            )
            # With a massive boost of 999.0 on 'testing', it should win
            assert result.intent_category == "testing"

    def test_classify_intent_receives_boosts_from_langextract(self) -> None:
        """classify_intent is called with score_boosts from langextract."""
        captured_kwargs: dict[str, object] = {}

        original_classify = (
            __import__(
                "omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_intent_classification",
                fromlist=["HandlerIntentClassifier"],
            )
            .HandlerIntentClassifier()
            .handle
        )

        def capture_classify(request: ModelClassifyIntentRequest) -> object:
            captured_kwargs.update(request.model_dump())
            return original_classify(request)

        with patch(
            "omniintelligence.nodes.node_intent_classifier_compute.handlers"
            ".handler_intent_classification.HandlerIntentClassifier.handle",
            side_effect=capture_classify,
        ):
            HandlerIntentClassification(_DEFAULT_CONFIG).handle(
                _make_input("Create REST API endpoint")
            )

        # The request must carry score_boosts to the classifier
        assert "score_boosts" in captured_kwargs
        # It should be a dict (could be empty if no boosts mapped)
        assert isinstance(captured_kwargs["score_boosts"], dict)

    def test_multi_label_always_enabled_in_handler(self) -> None:
        """handle_intent_classification always passes multi_label=True to classify_intent."""
        captured_kwargs: dict[str, object] = {}

        original_classify = (
            __import__(
                "omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_intent_classification",
                fromlist=["HandlerIntentClassifier"],
            )
            .HandlerIntentClassifier()
            .handle
        )

        def capture_classify(request: ModelClassifyIntentRequest) -> object:
            captured_kwargs.update(request.model_dump())
            return original_classify(request)

        with patch(
            "omniintelligence.nodes.node_intent_classifier_compute.handlers"
            ".handler_intent_classification.HandlerIntentClassifier.handle",
            side_effect=capture_classify,
        ):
            HandlerIntentClassification(_DEFAULT_CONFIG).handle(
                _make_input("Write unit tests")
            )

        assert captured_kwargs.get("multi_label") is True
