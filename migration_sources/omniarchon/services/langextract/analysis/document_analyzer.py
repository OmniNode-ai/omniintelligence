"""
Document Analyzer - Advanced Implementation

This module provides comprehensive document analysis capabilities for the LangExtract service,
including text metrics, readability analysis, topic extraction, sentiment analysis,
and document structure assessment.
"""

import asyncio
import logging
import math
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DocumentMetrics(BaseModel):
    """Comprehensive metrics for document analysis"""

    # Basic counts
    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    character_count: int = 0
    character_count_no_spaces: int = 0

    # Advanced metrics
    average_sentence_length: float = 0.0
    average_word_length: float = 0.0
    lexical_diversity: float = 0.0  # Type-token ratio

    # Readability scores
    flesch_kincaid_grade: float = 0.0
    flesch_reading_ease: float = 0.0
    gunning_fog_index: float = 0.0
    smog_index: float = 0.0
    automated_readability_index: float = 0.0
    coleman_liau_index: float = 0.0

    # Complexity metrics
    complexity_score: float = 0.0
    vocabulary_complexity: float = 0.0
    sentence_complexity: float = 0.0

    # Structure metrics
    heading_count: int = 0
    list_count: int = 0
    link_count: int = 0
    image_count: int = 0


class TopicInfo(BaseModel):
    """Information about detected topics"""

    topic: str
    confidence: float = Field(ge=0.0, le=1.0)
    keywords: List[str] = Field(default_factory=list)
    frequency: int = 0


class SentimentAnalysis(BaseModel):
    """Sentiment analysis results"""

    overall_sentiment: str  # positive, negative, neutral
    confidence: float = Field(ge=0.0, le=1.0)
    positive_score: float = Field(ge=0.0, le=1.0)
    negative_score: float = Field(ge=0.0, le=1.0)
    neutral_score: float = Field(ge=0.0, le=1.0)
    emotional_indicators: Dict[str, int] = Field(default_factory=dict)


class DocumentStructure(BaseModel):
    """Document structure analysis"""

    has_title: bool = False
    has_headings: bool = False
    has_lists: bool = False
    has_tables: bool = False
    has_links: bool = False
    has_images: bool = False
    has_code_blocks: bool = False
    structure_type: str = "plain_text"  # article, report, technical, academic, etc.
    organization_score: float = Field(ge=0.0, le=1.0)


# Import the main DocumentAnalysisResult from extraction models to ensure compatibility
try:
    from models.extraction_models import DocumentAnalysisResult

    logger.info("Using DocumentAnalysisResult from extraction_models for compatibility")
except ImportError:
    logger.warning(
        "Could not import DocumentAnalysisResult from extraction_models, using local definition"
    )

    class DocumentAnalysisResult(BaseModel):
        """Comprehensive result model for document analysis"""

        metrics: DocumentMetrics = Field(default_factory=DocumentMetrics)
        summary: str = ""
        key_topics: List[TopicInfo] = Field(default_factory=list)
        sentiment: SentimentAnalysis = Field(
            default_factory=lambda: SentimentAnalysis(
                overall_sentiment="neutral", confidence=0.0
            )
        )
        structure: DocumentStructure = Field(default_factory=DocumentStructure)
        metadata: Dict[str, Any] = Field(default_factory=dict)
        analysis_type: str = "document"
        quality_score: float = Field(ge=0.0, le=1.0, default=0.0)
        statistics: Dict[str, Any] = Field(default_factory=dict)


class DocumentAnalyzer:
    """
    Advanced document analyzer for comprehensive analysis of text documents,
    including metrics, sentiment, topics, readability, and structure analysis.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the document analyzer"""
        self.config = config or {}
        self.initialized = False

        # Sentiment keywords
        self.positive_words = {
            "excellent",
            "amazing",
            "wonderful",
            "fantastic",
            "great",
            "good",
            "positive",
            "happy",
            "satisfied",
            "pleased",
            "delighted",
            "thrilled",
            "excited",
            "love",
            "like",
            "enjoy",
            "appreciate",
            "recommend",
            "perfect",
            "outstanding",
            "brilliant",
            "superb",
            "magnificent",
            "exceptional",
            "remarkable",
            "impressive",
            "awesome",
            "beautiful",
            "marvelous",
            "terrific",
            "fabulous",
            "splendid",
            "excellent",
        }

        self.negative_words = {
            "terrible",
            "awful",
            "horrible",
            "bad",
            "worst",
            "hate",
            "dislike",
            "disappointed",
            "frustrated",
            "angry",
            "annoyed",
            "upset",
            "sad",
            "depressed",
            "disgusting",
            "unacceptable",
            "poor",
            "inadequate",
            "unsatisfactory",
            "regret",
            "complaint",
            "problem",
            "issue",
            "error",
            "failure",
            "wrong",
            "difficult",
            "challenging",
            "concerning",
            "troubling",
        }

        self.emotion_words = {
            "joy": {
                "joy",
                "happiness",
                "delight",
                "pleasure",
                "cheerful",
                "glad",
                "elated",
            },
            "anger": {
                "anger",
                "rage",
                "fury",
                "mad",
                "irritated",
                "annoyed",
                "furious",
            },
            "fear": {
                "fear",
                "afraid",
                "scared",
                "terrified",
                "anxious",
                "worried",
                "nervous",
            },
            "sadness": {
                "sad",
                "sorrow",
                "grief",
                "depressed",
                "melancholy",
                "gloomy",
                "miserable",
            },
            "surprise": {
                "surprise",
                "amazed",
                "astonished",
                "shocked",
                "stunned",
                "bewildered",
            },
            "disgust": {"disgusted", "revolted", "repulsed", "sickened", "appalled"},
        }

        # Common stop words for topic analysis
        self.stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "up",
            "about",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "among",
            "throughout",
            "within",
            "without",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
            "his",
            "her",
            "its",
            "our",
            "their",
            "this",
            "that",
            "these",
            "those",
            "am",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "can",
            "may",
            "might",
            "must",
        }

    async def initialize(self):
        """Initialize the analyzer with any required setup"""
        try:
            self.initialized = True
            logger.info("Document analyzer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize document analyzer: {e}")
            self.initialized = False

    async def analyze(
        self, content: str, doc_type: str = "text", context: Optional[str] = None
    ) -> DocumentAnalysisResult:
        """
        Perform comprehensive document analysis

        Args:
            content: The document content to analyze
            doc_type: Type of document (text, html, markdown, etc.)
            context: Additional context for analysis

        Returns:
            DocumentAnalysisResult with comprehensive analysis
        """
        if not self.initialized:
            await self.initialize()

        start_time = datetime.now()

        try:
            # Run analysis components concurrently
            metrics_task = asyncio.create_task(self._calculate_metrics(content))
            topics_task = asyncio.create_task(self._extract_topics(content))
            sentiment_task = asyncio.create_task(self._analyze_sentiment(content))
            structure_task = asyncio.create_task(
                self._analyze_structure(content, doc_type)
            )
            summary_task = asyncio.create_task(self._generate_summary(content))

            # Wait for all analyses to complete
            metrics = await metrics_task
            topics = await topics_task
            sentiment = await sentiment_task
            structure = await structure_task
            summary = await summary_task

            # Calculate overall quality score
            quality_score = self._calculate_quality_score(metrics, sentiment, structure)

            # Generate metadata
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            metadata = {
                "analysis_timestamp": end_time.isoformat(),
                "processing_time_seconds": processing_time,
                "document_type": doc_type,
                "content_length": len(content),
                "analysis_version": "1.0.0",
                "context": context,
            }

            # Compile statistics
            self._compile_statistics(content, metrics, topics, sentiment, structure)

            return DocumentAnalysisResult(
                document_type=doc_type,
                structure_analysis={
                    "structure": structure.dict() if hasattr(structure, "dict") else {}
                },
                content_summary=summary,
                readability_score=(
                    metrics.flesch_reading_ease / 100.0
                    if metrics.flesch_reading_ease > 0
                    else None
                ),
                complexity_score=metrics.complexity_score,
                information_density=quality_score,
                key_concepts=[topic.topic for topic in topics[:10]],
                main_topics=[topic.topic for topic in topics[:5]],
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Error during document analysis: {e}")
            return DocumentAnalysisResult(
                document_type="unknown",
                structure_analysis={},
                content_summary="Analysis failed",
                key_concepts=[],
                main_topics=[],
                metadata={
                    "error": str(e),
                    "analysis_timestamp": datetime.now().isoformat(),
                    "status": "failed",
                },
            )

    async def analyze_document(
        self,
        content: str,
        entities: Optional[List[Dict[str, Any]]] = None,
        document_path: Optional[str] = None,
    ) -> DocumentAnalysisResult:
        """
        Analyze document content with extracted entities context.
        This is the interface method expected by external callers (app.py).

        Args:
            content: The document content to analyze
            entities: Previously extracted entities to enhance analysis
            document_path: Path to the document being analyzed

        Returns:
            DocumentAnalysisResult with comprehensive analysis enhanced by entity context
        """
        try:
            logger.info(f"Starting document analysis for: {document_path}")
            logger.info(f"Content length: {len(content)} characters")
            logger.info(f"Entities provided: {len(entities) if entities else 0}")

            # Determine document type from path
            doc_type = "text"
            if document_path:
                if document_path.lower().endswith((".html", ".htm")):
                    doc_type = "html"
                elif document_path.lower().endswith((".md", ".markdown")):
                    doc_type = "markdown"
                elif document_path.lower().endswith((".json",)):
                    doc_type = "json"
                elif document_path.lower().endswith((".xml",)):
                    doc_type = "xml"

            # Use the existing analyze method as the core implementation
            result = await self.analyze(content, doc_type=doc_type, context=None)

            # Enhance the result with entity-based insights if entities are provided
            if entities:
                # Add entity-enhanced metadata
                # Handle both dict and Pydantic object entity types
                entity_types = Counter(
                    getattr(
                        entity,
                        "entity_type",
                        (
                            entity.get("entity_type", "UNKNOWN")
                            if isinstance(entity, dict)
                            else "UNKNOWN"
                        ),
                    )
                    for entity in entities
                )
                entity_confidence_avg = sum(
                    getattr(
                        entity,
                        "confidence_score",
                        (
                            entity.get("confidence", 0.0)
                            if isinstance(entity, dict)
                            else 0.0
                        ),
                    )
                    for entity in entities
                ) / max(len(entities), 1)

                result.metadata.update(
                    {
                        "entity_enhancement": {
                            "entities_analyzed": len(entities),
                            "entity_types_found": dict(entity_types),
                            "average_entity_confidence": round(
                                entity_confidence_avg, 3
                            ),
                            "entity_density": round(
                                len(entities) / max(len(content.split()), 1) * 100, 2
                            ),
                        }
                    }
                )

                # Enhance quality score based on entity richness
                entity_richness_bonus = min(
                    0.2, len(entities) / max(len(content.split()), 1) * 10
                )
                result.quality_score = min(
                    1.0, result.quality_score + entity_richness_bonus
                )

            # Add document path to metadata
            if document_path:
                result.metadata["document_path"] = document_path

            logger.info(f"Document analysis completed for: {document_path}")
            return result

        except Exception as e:
            logger.error(f"Document analysis failed for {document_path}: {e}")
            return DocumentAnalysisResult(
                document_type="unknown",
                structure_analysis={},
                content_summary="Analysis failed",
                key_concepts=[],
                main_topics=[],
                metadata={
                    "document_path": document_path,
                    "error": str(e),
                    "analysis_timestamp": datetime.now().isoformat(),
                    "status": "failed",
                },
            )

    async def _calculate_metrics(self, content: str) -> DocumentMetrics:
        """Calculate comprehensive document metrics"""
        # Basic counts
        words = self._extract_words(content)
        sentences = self._extract_sentences(content)
        paragraphs = self._extract_paragraphs(content)

        word_count = len(words)
        sentence_count = len(sentences)
        paragraph_count = len(paragraphs)
        character_count = len(content)
        character_count_no_spaces = len(content.replace(" ", ""))

        # Calculate averages
        avg_sentence_length = word_count / max(sentence_count, 1)
        avg_word_length = sum(len(word) for word in words) / max(word_count, 1)

        # Lexical diversity (Type-Token Ratio)
        unique_words = len(set(word.lower() for word in words))
        lexical_diversity = unique_words / max(word_count, 1)

        # Readability scores
        syllable_count = sum(self._count_syllables(word) for word in words)
        complex_words = sum(1 for word in words if self._count_syllables(word) >= 3)

        # Flesch-Kincaid Grade Level
        if sentence_count > 0 and word_count > 0:
            fk_grade = (
                0.39 * (word_count / sentence_count)
                + 11.8 * (syllable_count / word_count)
                - 15.59
            )
        else:
            fk_grade = 0.0

        # Flesch Reading Ease
        if sentence_count > 0 and word_count > 0:
            flesch_ease = (
                206.835
                - 1.015 * (word_count / sentence_count)
                - 84.6 * (syllable_count / word_count)
            )
        else:
            flesch_ease = 0.0

        # Gunning Fog Index
        if sentence_count > 0 and word_count > 0:
            fog_index = 0.4 * (
                (word_count / sentence_count) + 100 * (complex_words / word_count)
            )
        else:
            fog_index = 0.0

        # SMOG Index (simplified)
        if sentence_count >= 30:
            smog = 1.043 * math.sqrt(complex_words * (30 / sentence_count)) + 3.1291
        else:
            smog = 0.0

        # Automated Readability Index
        if sentence_count > 0 and word_count > 0:
            ari = (
                4.71 * (character_count_no_spaces / word_count)
                + 0.5 * (word_count / sentence_count)
                - 21.43
            )
        else:
            ari = 0.0

        # Coleman-Liau Index
        if word_count > 0:
            l_value = (character_count_no_spaces / word_count) * 100
            s_value = (sentence_count / word_count) * 100
            cli = 0.0588 * l_value - 0.296 * s_value - 15.8
        else:
            cli = 0.0

        # Complexity scores
        vocabulary_complexity = min(1.0, unique_words / max(word_count, 1) * 2)
        sentence_complexity = min(1.0, avg_sentence_length / 20)
        complexity_score = (vocabulary_complexity + sentence_complexity) / 2

        # Structure counts
        heading_count = len(re.findall(r"^#+\s+", content, re.MULTILINE)) + len(
            re.findall(r"<h[1-6]>", content, re.IGNORECASE)
        )
        list_count = len(re.findall(r"^\s*[-*+]\s+", content, re.MULTILINE)) + len(
            re.findall(r"^\s*\d+\.\s+", content, re.MULTILINE)
        )
        link_count = len(re.findall(r"https?://[^\s]+", content)) + len(
            re.findall(r"\[.*?\]\(.*?\)", content)
        )
        image_count = len(re.findall(r"!\[.*?\]\(.*?\)", content)) + len(
            re.findall(r"<img[^>]*>", content, re.IGNORECASE)
        )

        return DocumentMetrics(
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            character_count=character_count,
            character_count_no_spaces=character_count_no_spaces,
            average_sentence_length=avg_sentence_length,
            average_word_length=avg_word_length,
            lexical_diversity=lexical_diversity,
            flesch_kincaid_grade=max(0.0, fk_grade),
            flesch_reading_ease=max(0.0, min(100.0, flesch_ease)),
            gunning_fog_index=max(0.0, fog_index),
            smog_index=max(0.0, smog),
            automated_readability_index=max(0.0, ari),
            coleman_liau_index=max(0.0, cli),
            complexity_score=complexity_score,
            vocabulary_complexity=vocabulary_complexity,
            sentence_complexity=sentence_complexity,
            heading_count=heading_count,
            list_count=list_count,
            link_count=link_count,
            image_count=image_count,
        )

    async def _extract_topics(self, content: str) -> List[TopicInfo]:
        """Extract key topics from document content"""
        words = self._extract_words(content)

        # Filter out stop words and short words
        significant_words = [
            word.lower()
            for word in words
            if len(word) > 3 and word.lower() not in self.stop_words
        ]

        # Count word frequencies
        word_freq = Counter(significant_words)

        # Extract potential topics (noun phrases and frequent words)
        topics = []

        # Simple topic extraction based on word frequency
        for word, freq in word_freq.most_common(10):
            if freq >= 2:  # Only include words that appear multiple times
                confidence = min(1.0, freq / len(significant_words) * 10)
                topics.append(
                    TopicInfo(
                        topic=word,
                        confidence=confidence,
                        keywords=[word],
                        frequency=freq,
                    )
                )

        # Extract potential noun phrases (simple approach)
        noun_phrases = self._extract_noun_phrases(content)
        for phrase, freq in noun_phrases.most_common(5):
            if freq >= 2 and len(phrase.split()) >= 2:
                confidence = min(1.0, freq / len(significant_words) * 15)
                topics.append(
                    TopicInfo(
                        topic=phrase,
                        confidence=confidence,
                        keywords=phrase.split(),
                        frequency=freq,
                    )
                )

        # Sort by confidence and return top topics
        topics.sort(key=lambda x: x.confidence, reverse=True)
        return topics[:8]  # Return top 8 topics

    async def _analyze_sentiment(self, content: str) -> SentimentAnalysis:
        """Analyze document sentiment"""
        words = [word.lower() for word in self._extract_words(content)]

        positive_count = sum(1 for word in words if word in self.positive_words)
        negative_count = sum(
            1 for word in words if word in words and word in self.negative_words
        )
        total_sentiment_words = positive_count + negative_count

        # Calculate sentiment scores
        if total_sentiment_words == 0:
            positive_score = 0.33
            negative_score = 0.33
            neutral_score = 0.34
            overall_sentiment = "neutral"
            confidence = 0.3
        else:
            positive_score = positive_count / total_sentiment_words
            negative_score = negative_count / total_sentiment_words
            neutral_score = 1.0 - positive_score - negative_score

            if positive_score > negative_score and positive_score > 0.4:
                overall_sentiment = "positive"
                confidence = positive_score
            elif negative_score > positive_score and negative_score > 0.4:
                overall_sentiment = "negative"
                confidence = negative_score
            else:
                overall_sentiment = "neutral"
                confidence = max(positive_score, negative_score, neutral_score)

        # Analyze emotional indicators
        emotional_indicators = {}
        for emotion, emotion_words in self.emotion_words.items():
            count = sum(1 for word in words if word in emotion_words)
            if count > 0:
                emotional_indicators[emotion] = count

        return SentimentAnalysis(
            overall_sentiment=overall_sentiment,
            confidence=confidence,
            positive_score=positive_score,
            negative_score=negative_score,
            neutral_score=neutral_score,
            emotional_indicators=emotional_indicators,
        )

    async def _analyze_structure(
        self, content: str, doc_type: str
    ) -> DocumentStructure:
        """Analyze document structure and organization"""
        # Detect various structural elements
        has_title = bool(
            re.search(r"^#\s+.+", content, re.MULTILINE)
            or re.search(r"<h1[^>]*>.+</h1>", content, re.IGNORECASE)
        )

        has_headings = bool(
            re.search(r"^#+\s+", content, re.MULTILINE)
            or re.search(r"<h[2-6][^>]*>", content, re.IGNORECASE)
        )

        has_lists = bool(
            re.search(r"^\s*[-*+]\s+", content, re.MULTILINE)
            or re.search(r"^\s*\d+\.\s+", content, re.MULTILINE)
            or re.search(r"<[uo]l[^>]*>", content, re.IGNORECASE)
        )

        has_tables = bool(
            re.search(r"\|.*\|", content)
            or re.search(r"<table[^>]*>", content, re.IGNORECASE)
        )

        has_links = bool(
            re.search(r"https?://[^\s]+", content)
            or re.search(r"\[.*?\]\(.*?\)", content)
        )

        has_images = bool(
            re.search(r"!\[.*?\]\(.*?\)", content)
            or re.search(r"<img[^>]*>", content, re.IGNORECASE)
        )

        has_code_blocks = bool(
            re.search(r"```[\s\S]*?```", content)
            or re.search(r"`[^`]+`", content)
            or re.search(r"<code[^>]*>", content, re.IGNORECASE)
        )

        # Determine document type
        structure_type = self._determine_structure_type(
            content, has_headings, has_lists, has_tables, has_code_blocks
        )

        # Calculate organization score
        organization_score = self._calculate_organization_score(
            content, has_title, has_headings, has_lists, has_tables
        )

        return DocumentStructure(
            has_title=has_title,
            has_headings=has_headings,
            has_lists=has_lists,
            has_tables=has_tables,
            has_links=has_links,
            has_images=has_images,
            has_code_blocks=has_code_blocks,
            structure_type=structure_type,
            organization_score=organization_score,
        )

    async def _generate_summary(self, content: str) -> str:
        """Generate a concise summary of the document"""
        sentences = self._extract_sentences(content)

        if len(sentences) <= 3:
            return " ".join(sentences)

        # Simple extractive summarization
        # Score sentences based on word frequency and position
        words = self._extract_words(content)
        word_freq = Counter(
            word.lower() for word in words if word.lower() not in self.stop_words
        )

        sentence_scores = []
        for i, sentence in enumerate(sentences):
            sentence_words = self._extract_words(sentence)
            score = sum(word_freq.get(word.lower(), 0) for word in sentence_words)

            # Boost score for sentences at the beginning
            if i < len(sentences) * 0.3:
                score *= 1.5

            sentence_scores.append((score, sentence))

        # Select top sentences for summary
        sentence_scores.sort(key=lambda x: x[0], reverse=True)
        top_sentences = [sent for score, sent in sentence_scores[:3]]

        return " ".join(top_sentences)

    def _extract_words(self, text: str) -> List[str]:
        """Extract words from text, filtering out punctuation"""
        return re.findall(r"\b[a-zA-Z]+\b", text)

    def _extract_sentences(self, text: str) -> List[str]:
        """Extract sentences from text"""
        sentences = re.split(r"[.!?]+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_paragraphs(self, text: str) -> List[str]:
        """Extract paragraphs from text"""
        paragraphs = re.split(r"\n\s*\n", text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word (simplified approach)"""
        word = word.lower()
        vowels = "aeiouy"
        syllable_count = 0
        prev_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            prev_was_vowel = is_vowel

        # Handle silent 'e'
        if word.endswith("e") and syllable_count > 1:
            syllable_count -= 1

        return max(1, syllable_count)

    def _extract_noun_phrases(self, content: str) -> Counter:
        """Extract potential noun phrases (simple approach)"""
        # Simple noun phrase extraction using patterns
        phrases = []

        # Look for patterns like "adjective noun" or "noun noun"
        words = self._extract_words(content)
        for i in range(len(words) - 1):
            if len(words[i]) > 3 and len(words[i + 1]) > 3:
                phrase = f"{words[i].lower()} {words[i + 1].lower()}"
                if phrase not in self.stop_words:
                    phrases.append(phrase)

        return Counter(phrases)

    def _determine_structure_type(
        self,
        content: str,
        has_headings: bool,
        has_lists: bool,
        has_tables: bool,
        has_code: bool,
    ) -> str:
        """Determine the type of document structure"""
        content_lower = content.lower()

        if has_code and (
            "function" in content_lower
            or "class" in content_lower
            or "def " in content_lower
        ):
            return "technical_documentation"
        elif (
            has_tables
            and has_headings
            and ("analysis" in content_lower or "report" in content_lower)
        ):
            return "analytical_report"
        elif (
            has_headings
            and has_lists
            and ("abstract" in content_lower or "conclusion" in content_lower)
        ):
            return "academic_paper"
        elif has_headings and (
            "introduction" in content_lower or "overview" in content_lower
        ):
            return "structured_article"
        elif has_lists and not has_headings:
            return "list_document"
        elif has_headings:
            return "structured_document"
        else:
            return "plain_text"

    def _calculate_organization_score(
        self,
        content: str,
        has_title: bool,
        has_headings: bool,
        has_lists: bool,
        has_tables: bool,
    ) -> float:
        """Calculate how well-organized the document is"""
        score = 0.0

        if has_title:
            score += 0.2
        if has_headings:
            score += 0.3
        if has_lists:
            score += 0.2
        if has_tables:
            score += 0.1

        # Check for logical flow (simple heuristic)
        paragraphs = self._extract_paragraphs(content)
        if len(paragraphs) > 3:
            # Basic coherence check - consistent paragraph lengths suggest good organization
            para_lengths = [len(p.split()) for p in paragraphs]
            if para_lengths:
                avg_length = sum(para_lengths) / len(para_lengths)
                variance = sum(
                    (length - avg_length) ** 2 for length in para_lengths
                ) / len(para_lengths)
                coherence_score = max(
                    0, 0.2 - variance / 1000
                )  # Penalize high variance
                score += coherence_score

        return min(1.0, score)

    def _calculate_quality_score(
        self,
        metrics: DocumentMetrics,
        sentiment: SentimentAnalysis,
        structure: DocumentStructure,
    ) -> float:
        """Calculate overall document quality score"""
        score = 0.0

        # Readability contribution (30%)
        readability_score = 0.0
        if 30 <= metrics.flesch_reading_ease <= 70:  # Good readability range
            readability_score = 0.8
        elif 70 < metrics.flesch_reading_ease <= 90:
            readability_score = 1.0
        elif metrics.flesch_reading_ease > 90:
            readability_score = 0.9
        else:
            readability_score = max(0.0, metrics.flesch_reading_ease / 100)

        score += readability_score * 0.3

        # Structure contribution (25%)
        score += structure.organization_score * 0.25

        # Content richness (20%)
        content_richness = min(1.0, metrics.lexical_diversity * 2)
        score += content_richness * 0.2

        # Sentiment stability (15%)
        sentiment_stability = (
            sentiment.confidence
            if sentiment.overall_sentiment != "negative"
            else (1 - sentiment.confidence)
        )
        score += sentiment_stability * 0.15

        # Length appropriateness (10%)
        if 100 <= metrics.word_count <= 5000:  # Good length range
            length_score = 1.0
        elif metrics.word_count < 100:
            length_score = metrics.word_count / 100
        else:
            length_score = max(0.5, 5000 / metrics.word_count)
        score += length_score * 0.1

        return min(1.0, score)

    def _compile_statistics(
        self,
        content: str,
        metrics: DocumentMetrics,
        topics: List[TopicInfo],
        sentiment: SentimentAnalysis,
        structure: DocumentStructure,
    ) -> Dict[str, Any]:
        """Compile comprehensive analysis statistics"""
        return {
            "readability_assessment": {
                "grade_level": metrics.flesch_kincaid_grade,
                "reading_ease": metrics.flesch_reading_ease,
                "complexity_rating": (
                    "simple"
                    if metrics.flesch_reading_ease > 70
                    else "moderate" if metrics.flesch_reading_ease > 30 else "complex"
                ),
            },
            "content_analysis": {
                "total_topics_found": len(topics),
                "most_confident_topic": topics[0].topic if topics else None,
                "lexical_diversity_rating": (
                    "high"
                    if metrics.lexical_diversity > 0.7
                    else "moderate" if metrics.lexical_diversity > 0.4 else "low"
                ),
            },
            "sentiment_breakdown": {
                "dominant_sentiment": sentiment.overall_sentiment,
                "sentiment_strength": sentiment.confidence,
                "emotional_range": len(sentiment.emotional_indicators),
            },
            "structural_analysis": {
                "document_type": structure.structure_type,
                "organization_rating": (
                    "excellent"
                    if structure.organization_score > 0.8
                    else (
                        "good"
                        if structure.organization_score > 0.6
                        else "fair" if structure.organization_score > 0.4 else "poor"
                    )
                ),
                "structural_elements": {
                    "headings": structure.has_headings,
                    "lists": structure.has_lists,
                    "tables": structure.has_tables,
                    "code": structure.has_code_blocks,
                },
            },
            "quantitative_summary": {
                "words_per_sentence": round(metrics.average_sentence_length, 1),
                "characters_per_word": round(metrics.average_word_length, 1),
                "unique_word_ratio": round(metrics.lexical_diversity, 3),
                "total_structural_elements": sum(
                    [
                        metrics.heading_count,
                        metrics.list_count,
                        int(structure.has_tables),
                        int(structure.has_links),
                    ]
                ),
            },
        }
