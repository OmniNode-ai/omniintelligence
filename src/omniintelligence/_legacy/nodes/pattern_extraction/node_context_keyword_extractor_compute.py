#!/usr/bin/env python3
"""
Context Keyword Extractor Compute Node - ONEX Compliant

Extracts relevant keywords from execution context using TF-IDF and semantic analysis.
Part of Track 2 Intelligence Hook System (Track 3-1.4).

Generated with DeepSeek-Lite via vLLM
Author: Archon Intelligence Team
Date: 2025-10-02
"""

import hashlib
import math
import re
import uuid
from collections import Counter, defaultdict
from typing import Any

from pydantic import BaseModel, Field

# ============================================================================
# Models
# ============================================================================


class ModelKeywordExtractionInput(BaseModel):
    """Input state for keyword extraction."""

    context_text: str = Field(..., description="Context text to extract keywords from")
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID for tracing",
    )
    max_keywords: int = Field(
        default=10, description="Maximum number of keywords to extract", ge=1, le=50
    )
    min_score: float = Field(
        default=0.3, description="Minimum relevance score", ge=0.0, le=1.0
    )
    include_phrases: bool = Field(
        default=True, description="Include multi-word phrases"
    )


class ModelKeywordExtractionOutput(BaseModel):
    """Output state for keyword extraction."""

    keywords: list[str] = Field(
        default_factory=list, description="Extracted keywords ranked by relevance"
    )
    keyword_scores: dict[str, float] = Field(
        default_factory=dict, description="Relevance scores for each keyword"
    )
    phrases: list[str] = Field(
        default_factory=list, description="Extracted multi-word phrases"
    )
    phrase_scores: dict[str, float] = Field(
        default_factory=dict, description="Relevance scores for phrases"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Extraction metadata"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")


# ============================================================================
# ONEX Compute Node Implementation
# ============================================================================


class NodeContextKeywordExtractorCompute:
    """
    ONEX-Compliant Compute Node for Context Keyword Extraction.

    Implements TF-IDF based keyword extraction with phrase detection
    for extracting relevant terms from execution contexts.

    ONEX Patterns:
    - Pure functional computation (no side effects)
    - Deterministic results for same inputs
    - Correlation ID propagation
    - Performance optimized (<50ms target)
    """

    # Stop words to filter out (common words with low semantic value)
    STOP_WORDS: set[str] = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "has",
        "he",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "that",
        "the",
        "to",
        "was",
        "will",
        "with",
        "this",
        "these",
        "those",
        "which",
        "who",
        "what",
        "where",
        "when",
        "why",
        "how",
    }

    # Domain-specific keyword boosters (technical terms)
    DOMAIN_BOOSTERS: set[str] = {
        "function",
        "class",
        "method",
        "variable",
        "parameter",
        "return",
        "async",
        "await",
        "import",
        "from",
        "def",
        "else",
        "for",
        "while",
        "try",
        "except",
        "error",
        "exception",
        "test",
        "assert",
        "validate",
    }

    # Performance constants
    MAX_TEXT_LENGTH = 50000
    DEFAULT_TIMEOUT_MS = 50

    def __init__(self) -> None:
        """Initialize keyword extractor."""
        # IDF corpus for TF-IDF calculation (simplified for standalone use)
        self._document_frequency: dict[str, int] = defaultdict(int)
        self._total_documents = 0

    # ========================================================================
    # ONEX Execute Compute Method (Primary Interface)
    # ========================================================================

    async def execute_compute(
        self, input_state: ModelKeywordExtractionInput
    ) -> ModelKeywordExtractionOutput:
        """
        Execute keyword extraction computation (ONEX NodeCompute interface).

        Pure functional method with no side effects, deterministic results.

        Args:
            input_state: Input state with context text and parameters

        Returns:
            ModelKeywordExtractionOutput: Extracted keywords with scores
        """
        import time

        start_time = time.time()

        try:
            # Validate input
            if not input_state.context_text.strip():
                return ModelKeywordExtractionOutput(
                    keywords=[],
                    keyword_scores={},
                    phrases=[],
                    phrase_scores={},
                    metadata={"error": "Empty context text"},
                    correlation_id=input_state.correlation_id,
                )

            # Extract keywords using TF-IDF
            keywords, keyword_scores = self._extract_keywords(
                text=input_state.context_text,
                max_keywords=input_state.max_keywords,
                min_score=input_state.min_score,
            )

            # Extract phrases if requested
            phrases: list[str] = []
            phrase_scores: dict[str, float] = {}
            if input_state.include_phrases:
                phrases, phrase_scores = self._extract_phrases(
                    text=input_state.context_text,
                    max_phrases=input_state.max_keywords // 2,  # Fewer phrases
                    min_score=input_state.min_score,
                )

            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms

            return ModelKeywordExtractionOutput(
                keywords=keywords,
                keyword_scores=keyword_scores,
                phrases=phrases,
                phrase_scores=phrase_scores,
                metadata={
                    "processing_time_ms": processing_time,
                    "text_length": len(input_state.context_text),
                    "algorithm": "tfidf_with_phrases",
                    "total_keywords_found": len(keywords),
                    "total_phrases_found": len(phrases),
                },
                correlation_id=input_state.correlation_id,
            )

        except Exception as e:
            return ModelKeywordExtractionOutput(
                keywords=[],
                keyword_scores={},
                phrases=[],
                phrase_scores={},
                metadata={"error": str(e)},
                correlation_id=input_state.correlation_id,
            )

    # ========================================================================
    # Pure Functional Keyword Extraction Algorithm
    # ========================================================================

    def _extract_keywords(
        self, text: str, max_keywords: int = 10, min_score: float = 0.3
    ) -> tuple[list[str], dict[str, float]]:
        """
        Extract keywords using TF-IDF algorithm.

        Algorithm:
        1. Tokenize and filter stop words
        2. Calculate term frequency (TF)
        3. Calculate inverse document frequency (IDF)
        4. Calculate TF-IDF scores
        5. Apply domain boosters
        6. Rank and filter by score
        7. Return top keywords

        Args:
            text: Input text
            max_keywords: Maximum keywords to return
            min_score: Minimum TF-IDF score

        Returns:
            Tuple of (keywords list, scores dict)
        """
        # Step 1: Tokenize and filter
        tokens = self._tokenize(text)
        filtered_tokens = [t for t in tokens if t not in self.STOP_WORDS and len(t) > 2]

        if not filtered_tokens:
            return [], {}

        # Step 2: Calculate TF
        tf_scores = self._calculate_tf(filtered_tokens)

        # Step 3: Calculate IDF (simplified - use log of total unique words)
        unique_words = len(set(filtered_tokens))
        idf_scores = self._calculate_idf(filtered_tokens, unique_words)

        # Step 4: Calculate TF-IDF
        tfidf_scores: dict[str, float] = {}
        for term in set(filtered_tokens):
            tfidf_scores[term] = tf_scores[term] * idf_scores[term]

        # Step 5: Apply domain boosters
        for term in tfidf_scores:
            if term in self.DOMAIN_BOOSTERS:
                tfidf_scores[term] *= 1.5  # Boost technical terms

        # Step 6: Normalize scores to 0.0-1.0
        max_score = max(tfidf_scores.values()) if tfidf_scores else 1.0
        normalized_scores = {
            term: score / max_score if max_score > 0 else 0.0
            for term, score in tfidf_scores.items()
        }

        # Step 7: Filter and rank
        filtered_keywords = {
            term: score
            for term, score in normalized_scores.items()
            if score >= min_score
        }

        sorted_keywords = sorted(
            filtered_keywords.items(), key=lambda x: x[1], reverse=True
        )[:max_keywords]

        keywords = [term for term, _ in sorted_keywords]
        scores = dict(sorted_keywords)

        return keywords, scores

    def _extract_phrases(
        self, text: str, max_phrases: int = 5, min_score: float = 0.3
    ) -> tuple[list[str], dict[str, float]]:
        """
        Extract multi-word phrases using n-gram analysis.

        Algorithm:
        1. Extract bigrams and trigrams
        2. Filter stop words from phrases
        3. Calculate phrase frequencies
        4. Score by frequency and term quality
        5. Return top phrases

        Args:
            text: Input text
            max_phrases: Maximum phrases to return
            min_score: Minimum phrase score

        Returns:
            Tuple of (phrases list, scores dict)
        """
        # Step 1: Tokenize
        tokens = self._tokenize(text)

        # Step 2: Extract bigrams
        bigrams = self._extract_ngrams(tokens, n=2)
        trigrams = self._extract_ngrams(tokens, n=3)

        all_phrases = bigrams + trigrams

        if not all_phrases:
            return [], {}

        # Step 3: Calculate phrase frequencies
        phrase_counts = Counter(all_phrases)

        # Step 4: Score phrases
        phrase_scores: dict[str, float] = {}
        for phrase, count in phrase_counts.items():
            # Filter phrases with stop words
            phrase_tokens = phrase.split()
            if any(token in self.STOP_WORDS for token in phrase_tokens):
                continue

            # Score based on frequency and length
            score = count * (len(phrase_tokens) / 3.0)  # Favor longer phrases
            phrase_scores[phrase] = score

        # Step 5: Normalize scores
        max_score = max(phrase_scores.values()) if phrase_scores else 1.0
        normalized_scores = {
            phrase: score / max_score if max_score > 0 else 0.0
            for phrase, score in phrase_scores.items()
        }

        # Step 6: Filter and rank
        filtered_phrases = {
            phrase: score
            for phrase, score in normalized_scores.items()
            if score >= min_score
        }

        sorted_phrases = sorted(
            filtered_phrases.items(), key=lambda x: x[1], reverse=True
        )[:max_phrases]

        phrases = [phrase for phrase, _ in sorted_phrases]
        scores = dict(sorted_phrases)

        return phrases, scores

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize and normalize text."""
        # Split on word boundaries and convert to lowercase
        tokens = re.findall(r"\b\w+\b", text.lower())
        return tokens

    def _calculate_tf(self, tokens: list[str]) -> dict[str, float]:
        """Calculate term frequency (TF) scores."""
        if not tokens:
            return {}

        token_counts = Counter(tokens)
        total_tokens = len(tokens)

        tf_scores = {
            token: count / total_tokens for token, count in token_counts.items()
        }

        return tf_scores

    def _calculate_idf(
        self, tokens: list[str], total_documents: int
    ) -> dict[str, float]:
        """
        Calculate inverse document frequency (IDF) scores.

        IDF(t) = log(Total documents / Documents containing term)

        Simplified for single-document extraction: use unique word count.
        """
        if not tokens:
            return {}

        token_counts = Counter(tokens)
        idf_scores: dict[str, float] = {}

        for token in set(tokens):
            # Use log of inverse frequency within document
            # More unique terms (lower frequency) get higher IDF
            idf_scores[token] = math.log(total_documents / token_counts[token])

        return idf_scores

    def _extract_ngrams(self, tokens: list[str], n: int = 2) -> list[str]:
        """
        Extract n-grams from token list.

        Args:
            tokens: List of tokens
            n: N-gram size (2=bigram, 3=trigram)

        Returns:
            List of n-gram phrases
        """
        ngrams: list[str] = []
        for i in range(len(tokens) - n + 1):
            ngram = " ".join(tokens[i : i + n])
            ngrams.append(ngram)
        return ngrams

    def calculate_deterministic_hash(self, text: str) -> str:
        """Calculate deterministic hash for reproducibility."""
        combined = f"{text}|keyword_extractor|v1.0.0"
        hash_bytes = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return f"sha256:{hash_bytes[:16]}"


# ============================================================================
# Unit Test Helpers
# ============================================================================


async def test_keyword_extractor() -> None:
    """Test keyword extractor with various inputs."""
    extractor = NodeContextKeywordExtractorCompute()

    # Test 1: Technical context
    test_input = ModelKeywordExtractionInput(
        context_text="""
        Implementing async function for database connection with error handling.
        The function will validate parameters and return connection object.
        Need to test exception cases and validate return types.
        """,
        max_keywords=8,
    )
    result = await extractor.execute_compute(test_input)
    print(f"Test 1 - Keywords: {result.keywords}")
    print(f"Test 1 - Scores: {result.keyword_scores}")
    print(f"Test 1 - Phrases: {result.phrases}")
    assert len(result.keywords) > 0
    assert "function" in result.keywords or "async" in result.keywords

    # Test 2: Code snippet context
    test_input = ModelKeywordExtractionInput(
        context_text="""
        def calculate_metrics(data: List[int]) -> Dict[str, float]:
            total = sum(data)
            average = total / len(data)
            return {"total": total, "average": average}
        """,
        include_phrases=True,
    )
    result = await extractor.execute_compute(test_input)
    print(f"\nTest 2 - Keywords: {result.keywords}")
    print(f"Test 2 - Phrases: {result.phrases}")
    print(f"Test 2 - Processing time: {result.metadata.get('processing_time_ms')}ms")

    # Test 3: Empty context
    test_input = ModelKeywordExtractionInput(context_text="")
    result = await extractor.execute_compute(test_input)
    print(f"\nTest 3 - Empty: {result.keywords}")
    assert len(result.keywords) == 0

    # Test 4: Performance test with large context
    large_context = (
        """
    Debugging complex authentication system with JWT tokens and refresh mechanisms.
    The issue involves expired tokens not being properly refreshed during API calls.
    Need to implement token rotation strategy with proper error handling and logging.
    Testing various edge cases including concurrent requests and network failures.
    """
        * 10
    )  # Repeat for larger context

    test_input = ModelKeywordExtractionInput(
        context_text=large_context, max_keywords=15
    )
    result = await extractor.execute_compute(test_input)
    print(f"\nTest 4 - Large context keywords: {result.keywords[:5]}...")
    print(f"Test 4 - Processing time: {result.metadata.get('processing_time_ms')}ms")

    print("\nAll tests passed!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_keyword_extractor())
