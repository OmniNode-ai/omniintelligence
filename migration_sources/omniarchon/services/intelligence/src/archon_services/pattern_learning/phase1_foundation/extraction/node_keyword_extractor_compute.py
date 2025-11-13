#!/usr/bin/env python3
"""
Keyword Extractor Compute Node - ONEX Compliant

Extracts relevant keywords using TF-IDF algorithm for pattern extraction.
Part of Pattern Learning Engine Phase 1 Foundation.

Author: Archon Intelligence Team
Date: 2025-10-02
ONEX Compliance: >0.9
"""

import hashlib
import math
import re
import uuid
from collections import Counter, defaultdict
from typing import Any, Dict, List, Set, Tuple

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
        default=15, description="Maximum number of keywords to extract", ge=1, le=50
    )
    min_score: float = Field(
        default=0.2, description="Minimum relevance score", ge=0.0, le=1.0
    )
    include_phrases: bool = Field(
        default=True, description="Include multi-word phrases"
    )


class ModelKeywordExtractionOutput(BaseModel):
    """Output state for keyword extraction."""

    keywords: List[str] = Field(
        default_factory=list, description="Extracted keywords ranked by relevance"
    )
    keyword_scores: Dict[str, float] = Field(
        default_factory=dict, description="TF-IDF scores for each keyword"
    )
    phrases: List[str] = Field(
        default_factory=list, description="Extracted multi-word phrases"
    )
    phrase_scores: Dict[str, float] = Field(
        default_factory=dict, description="Relevance scores for phrases"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Extraction metadata"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")


# ============================================================================
# ONEX Compute Node Implementation
# ============================================================================


class NodeKeywordExtractorCompute:
    """
    ONEX-Compliant Compute Node for Keyword Extraction.

    Implements TF-IDF based keyword extraction with phrase detection
    for extracting relevant terms from execution contexts.

    ONEX Patterns:
    - Pure functional computation (no side effects)
    - Deterministic results for same inputs
    - Correlation ID propagation
    - Performance optimized (<30ms target)
    """

    # Stop words to filter out (common words with low semantic value)
    STOP_WORDS: Set[str] = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
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
        "can",
        "could",
        "would",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "do",
        "does",
        "did",
        "have",
        "had",
        "been",
        "being",
        "but",
        "or",
        "nor",
        "not",
        "all",
        "any",
        "some",
        "such",
        "no",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "another",
        "same",
        "so",
        "than",
        "too",
        "very",
    }

    # Domain-specific keyword boosters (technical terms)
    DOMAIN_BOOSTERS: Set[str] = {
        "function",
        "class",
        "method",
        "variable",
        "parameter",
        "return",
        "async",
        "await",
        "import",
        "def",
        "error",
        "exception",
        "test",
        "assert",
        "validate",
        "algorithm",
        "compute",
        "execute",
        "process",
        "analyze",
        "extract",
        "pattern",
        "node",
        "orchestrate",
    }

    # Performance constants
    MAX_TEXT_LENGTH = 50000
    DEFAULT_TIMEOUT_MS = 30

    def __init__(self) -> None:
        """Initialize keyword extractor."""
        # IDF corpus for TF-IDF calculation (simplified for standalone use)
        self._document_frequency: Dict[str, int] = defaultdict(int)
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
            ModelKeywordExtractionOutput: Extracted keywords with TF-IDF scores
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
            phrases: List[str] = []
            phrase_scores: Dict[str, float] = {}
            if input_state.include_phrases:
                phrases, phrase_scores = self._extract_phrases(
                    text=input_state.context_text,
                    max_phrases=min(input_state.max_keywords // 2, 8),
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
        self, text: str, max_keywords: int = 15, min_score: float = 0.2
    ) -> Tuple[List[str], Dict[str, float]]:
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
        tfidf_scores: Dict[str, float] = {}
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
        scores = {term: score for term, score in sorted_keywords}

        return keywords, scores

    def _extract_phrases(
        self, text: str, max_phrases: int = 8, min_score: float = 0.2
    ) -> Tuple[List[str], Dict[str, float]]:
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

        # Step 2: Extract bigrams and trigrams
        bigrams = self._extract_ngrams(tokens, n=2)
        trigrams = self._extract_ngrams(tokens, n=3)

        all_phrases = bigrams + trigrams

        if not all_phrases:
            return [], {}

        # Step 3: Calculate phrase frequencies
        phrase_counts = Counter(all_phrases)

        # Step 4: Score phrases
        phrase_scores: Dict[str, float] = {}
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
        scores = {phrase: score for phrase, score in sorted_phrases}

        return phrases, scores

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize and normalize text."""
        # Split on word boundaries and convert to lowercase
        tokens = re.findall(r"\b\w+\b", text.lower())
        return tokens

    def _calculate_tf(self, tokens: List[str]) -> Dict[str, float]:
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
        self, tokens: List[str], total_documents: int
    ) -> Dict[str, float]:
        """
        Calculate inverse document frequency (IDF) scores.

        IDF(t) = log(Total documents / Documents containing term)

        Simplified for single-document extraction: use unique word count.
        """
        if not tokens:
            return {}

        token_counts = Counter(tokens)
        idf_scores: Dict[str, float] = {}

        for token in set(tokens):
            # Use log of inverse frequency within document
            # More unique terms (lower frequency) get higher IDF
            idf_scores[token] = math.log(total_documents / token_counts[token])

        return idf_scores

    def _extract_ngrams(self, tokens: List[str], n: int = 2) -> List[str]:
        """
        Extract n-grams from token list.

        Args:
            tokens: List of tokens
            n: N-gram size (2=bigram, 3=trigram)

        Returns:
            List of n-gram phrases
        """
        ngrams: List[str] = []
        for i in range(len(tokens) - n + 1):
            ngram = " ".join(tokens[i : i + n])
            ngrams.append(ngram)
        return ngrams

    def calculate_deterministic_hash(self, text: str) -> str:
        """Calculate deterministic hash for reproducibility."""
        combined = f"{text}|keyword_extractor|v1.0.0"
        hash_bytes = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return f"sha256:{hash_bytes[:16]}"
