#!/usr/bin/env python3
"""
Intent Classifier Compute Node - ONEX Compliant

Classifies request intent using NLP-based algorithms for pattern extraction.
Part of Track 2 Intelligence Hook System (Track 3-1.4).

Generated with DeepSeek-Lite via vLLM
Author: Archon Intelligence Team
Date: 2025-10-02
"""

import hashlib
import re
import uuid
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

# ============================================================================
# Models (simplified for standalone pattern extraction)
# ============================================================================


class ModelIntentClassificationInput(BaseModel):
    """Input state for intent classification."""

    request_text: str = Field(..., description="Text to classify for intent")
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID for tracing",
    )
    confidence_threshold: float = Field(
        default=0.5, description="Minimum confidence threshold", ge=0.0, le=1.0
    )
    multi_label: bool = Field(
        default=False, description="Enable multi-label classification"
    )


class ModelIntentClassificationOutput(BaseModel):
    """Output state for intent classification."""

    intent: str = Field(..., description="Classified intent type")
    confidence: float = Field(..., description="Classification confidence (0.0-1.0)")
    keywords: list[str] = Field(
        default_factory=list, description="Keywords that influenced classification"
    )
    all_scores: dict[str, float] = Field(
        default_factory=dict, description="Confidence scores for all intents"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")


# ============================================================================
# ONEX Compute Node Implementation
# ============================================================================


class NodeIntentClassifierCompute:
    """
    ONEX-Compliant Compute Node for Intent Classification.

    Implements TF-IDF based classification with pattern matching
    for accurate intent detection from execution traces.

    ONEX Patterns:
    - Pure functional computation (no side effects)
    - Deterministic results for same inputs
    - Correlation ID propagation
    - Performance optimized (<50ms target)
    """

    # Intent patterns and keywords (business logic constants)
    INTENT_PATTERNS: dict[str, list[str]] = {
        "code_generation": [
            "generate",
            "create",
            "implement",
            "write",
            "build",
            "develop",
            "add",
            "make",
        ],
        "debugging": [
            "debug",
            "fix",
            "error",
            "bug",
            "issue",
            "problem",
            "crash",
            "fail",
        ],
        "refactoring": [
            "refactor",
            "improve",
            "optimize",
            "restructure",
            "clean",
            "reorganize",
        ],
        "testing": [
            "test",
            "validate",
            "verify",
            "check",
            "assert",
            "spec",
            "unittest",
        ],
        "documentation": [
            "document",
            "explain",
            "describe",
            "comment",
            "annotate",
            "doc",
        ],
        "analysis": [
            "analyze",
            "review",
            "inspect",
            "examine",
            "evaluate",
            "assess",
        ],
    }

    # Performance constants
    MAX_TEXT_LENGTH = 10000
    DEFAULT_TIMEOUT_MS = 50

    def __init__(self) -> None:
        """Initialize intent classifier with pattern database."""
        # Pre-compute normalized patterns for performance
        self._normalized_patterns: dict[str, list[str]] = {}
        for intent, keywords in self.INTENT_PATTERNS.items():
            self._normalized_patterns[intent] = [kw.lower() for kw in keywords]

    # ========================================================================
    # ONEX Execute Compute Method (Primary Interface)
    # ========================================================================

    async def execute_compute(
        self, input_state: ModelIntentClassificationInput
    ) -> ModelIntentClassificationOutput:
        """
        Execute intent classification computation (ONEX NodeCompute interface).

        Pure functional method with no side effects, deterministic results.

        Args:
            input_state: Input state with request text and parameters

        Returns:
            ModelIntentClassificationOutput: Classification result with confidence
        """
        import time

        start_time = time.time()

        try:
            # Validate input
            if not input_state.request_text.strip():
                return ModelIntentClassificationOutput(
                    intent="unknown",
                    confidence=0.0,
                    keywords=[],
                    all_scores={},
                    metadata={"error": "Empty request text"},
                    correlation_id=input_state.correlation_id,
                )

            # Classify intent using TF-IDF algorithm
            classification_result = self._classify_intent(
                text=input_state.request_text,
                confidence_threshold=input_state.confidence_threshold,
                multi_label=input_state.multi_label,
            )

            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms

            # Build output
            return ModelIntentClassificationOutput(
                intent=classification_result["intent"],
                confidence=classification_result["confidence"],
                keywords=classification_result["keywords"],
                all_scores=classification_result["all_scores"],
                metadata={
                    "processing_time_ms": processing_time,
                    "text_length": len(input_state.request_text),
                    "algorithm": "tfidf_pattern_matching",
                },
                correlation_id=input_state.correlation_id,
            )

        except Exception as e:
            # Graceful error handling
            return ModelIntentClassificationOutput(
                intent="unknown",
                confidence=0.0,
                keywords=[],
                all_scores={},
                metadata={"error": str(e)},
                correlation_id=input_state.correlation_id,
            )

    # ========================================================================
    # Pure Functional Classification Algorithm
    # ========================================================================

    def _classify_intent(
        self,
        text: str,
        confidence_threshold: float = 0.5,
        multi_label: bool = False,
    ) -> dict[str, Any]:
        """
        Classify intent using TF-IDF and pattern matching.

        Algorithm:
        1. Tokenize and normalize text
        2. Calculate TF scores for each token
        3. Match against intent patterns
        4. Calculate weighted confidence scores
        5. Rank by confidence
        6. Return top classification or multi-label results

        Args:
            text: Input text to classify
            confidence_threshold: Minimum confidence for classification
            multi_label: Return all intents above threshold

        Returns:
            Dictionary with intent, confidence, keywords, and all scores
        """
        # Step 1: Tokenize and normalize
        tokens = self._tokenize(text)
        if not tokens:
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "keywords": [],
                "all_scores": {},
            }

        # Step 2: Calculate term frequencies
        tf_scores = self._calculate_tf(tokens)

        # Step 3: Match against patterns and calculate confidence
        intent_scores: dict[str, float] = {}
        intent_keywords: dict[str, list[str]] = {}

        for intent, patterns in self._normalized_patterns.items():
            score, matched_keywords = self._calculate_intent_score(
                tf_scores, patterns, tokens
            )
            intent_scores[intent] = score
            intent_keywords[intent] = matched_keywords

        # Step 4: Normalize scores to 0.0-1.0 range (sum-based for proportional confidence)
        total_score = sum(intent_scores.values()) if intent_scores else 1.0
        normalized_scores = {
            intent: score / total_score if total_score > 0 else 0.0
            for intent, score in intent_scores.items()
        }

        # Step 5: Rank by confidence
        sorted_intents = sorted(
            normalized_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Step 6: Return result
        if multi_label:
            # Return all intents above threshold
            filtered_intents = [
                (intent, score)
                for intent, score in sorted_intents
                if score >= confidence_threshold
            ]
            if filtered_intents:
                primary_intent, primary_score = filtered_intents[0]
                return {
                    "intent": primary_intent,
                    "confidence": primary_score,
                    "keywords": intent_keywords[primary_intent],
                    "all_scores": normalized_scores,
                    "multi_label_results": filtered_intents,
                }

        # Single label: return top result
        if sorted_intents and sorted_intents[0][1] >= confidence_threshold:
            top_intent, top_score = sorted_intents[0]
            return {
                "intent": top_intent,
                "confidence": top_score,
                "keywords": intent_keywords[top_intent],
                "all_scores": normalized_scores,
            }

        # Below threshold
        return {
            "intent": "unknown",
            "confidence": 0.0,
            "keywords": [],
            "all_scores": normalized_scores,
        }

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize and normalize text.

        Pure functional method for deterministic tokenization.

        Args:
            text: Input text

        Returns:
            List of normalized tokens
        """
        # Convert to lowercase and extract words
        tokens = re.findall(r"\w+", text.lower())
        return tokens

    def _calculate_tf(self, tokens: list[str]) -> dict[str, float]:
        """
        Calculate term frequency (TF) scores.

        TF(t) = (Number of times term t appears in document) / (Total number of terms)

        Args:
            tokens: List of tokens

        Returns:
            Dictionary mapping tokens to TF scores
        """
        if not tokens:
            return {}

        token_counts = Counter(tokens)
        total_tokens = len(tokens)

        tf_scores = {
            token: count / total_tokens for token, count in token_counts.items()
        }

        return tf_scores

    def _calculate_intent_score(
        self, tf_scores: dict[str, float], patterns: list[str], tokens: list[str]
    ) -> tuple[float, list[str]]:
        """
        Calculate intent score based on pattern matching and TF scores.

        Combines pattern matching with term frequency weighting.

        Args:
            tf_scores: Term frequency scores
            patterns: Intent pattern keywords
            tokens: Original tokens

        Returns:
            Tuple of (score, matched_keywords)
        """
        score = 0.0
        matched_keywords: list[str] = []

        # Direct pattern matches (weighted by TF)
        for pattern in patterns:
            if pattern in tf_scores:
                score += tf_scores[pattern] * 10.0  # Weight pattern matches
                matched_keywords.append(pattern)

        # Partial matches (fuzzy matching for variations)
        for token in tokens:
            for pattern in patterns:
                if (pattern in token or token in pattern) and token not in matched_keywords:
                    score += tf_scores.get(token, 0.0) * 5.0  # Lower weight
                    matched_keywords.append(token)

        return score, matched_keywords

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def calculate_deterministic_hash(self, text: str) -> str:
        """
        Calculate deterministic hash for reproducibility.

        Pure functional method for testing and validation.

        Args:
            text: Input text

        Returns:
            SHA256 hash string with algorithm prefix
        """
        combined = f"{text}|intent_classifier|v1.0.0"
        hash_bytes = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return f"sha256:{hash_bytes[:16]}"


# ============================================================================
# Unit Test Helpers
# ============================================================================


async def test_intent_classifier() -> None:
    """Test intent classifier with various inputs."""
    classifier = NodeIntentClassifierCompute()

    # Test 1: Code generation intent
    test_input = ModelIntentClassificationInput(
        request_text="I want to generate some code for user authentication"
    )
    result = await classifier.execute_compute(test_input)
    print(f"Test 1: {result}")
    assert result.intent == "code_generation"
    assert result.confidence > 0.5

    # Test 2: Debugging intent
    test_input = ModelIntentClassificationInput(
        request_text="Help me debug this error in my function"
    )
    result = await classifier.execute_compute(test_input)
    print(f"Test 2: {result}")
    assert result.intent == "debugging"

    # Test 3: Unknown intent
    test_input = ModelIntentClassificationInput(
        request_text="hello world", confidence_threshold=0.8
    )
    result = await classifier.execute_compute(test_input)
    print(f"Test 3: {result}")

    # Test 4: Multi-label classification
    test_input = ModelIntentClassificationInput(
        request_text="Generate tests and fix bugs in authentication module",
        multi_label=True,
    )
    result = await classifier.execute_compute(test_input)
    print(f"Test 4: {result}")

    print("All tests passed!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_intent_classifier())
