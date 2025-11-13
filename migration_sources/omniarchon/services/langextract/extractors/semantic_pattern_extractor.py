"""
Semantic Pattern Extractor - Advanced Implementation

This module provides comprehensive semantic pattern extraction capabilities
for the LangExtract service, including entity recognition, relationship
mapping, conceptual patterns, and semantic analysis.
"""

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SemanticEntity(BaseModel):
    """Model for a semantic entity"""

    text: str
    entity_type: str
    start_position: int
    end_position: int
    confidence: float = Field(ge=0.0, le=1.0)
    context: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)


class SemanticRelationship(BaseModel):
    """Model for relationships between semantic entities"""

    subject: str
    predicate: str
    object: str
    confidence: float = Field(ge=0.0, le=1.0)
    context: str = ""
    relationship_type: str = ""


class ConceptualPattern(BaseModel):
    """Model for conceptual patterns in text"""

    pattern_name: str
    pattern_type: str
    elements: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    context: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)


class SemanticPattern(BaseModel):
    """Model for a semantic pattern"""

    pattern_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    text: str
    start_position: int = 0
    end_position: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    entities: List[SemanticEntity] = Field(default_factory=list)
    relationships: List[SemanticRelationship] = Field(default_factory=list)


class SemanticPatternResult(BaseModel):
    """Result model for semantic pattern extraction"""

    patterns: List[SemanticPattern] = Field(default_factory=list)
    entities: List[SemanticEntity] = Field(default_factory=list)
    relationships: List[SemanticRelationship] = Field(default_factory=list)
    concepts: List[ConceptualPattern] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    extraction_type: str = "semantic_pattern"
    statistics: Dict[str, Any] = Field(default_factory=dict)


class SemanticPatternExtractor:
    """
    Advanced semantic pattern extractor for identifying semantic patterns,
    entities, relationships, and meaningful structures in text content.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the semantic pattern extractor"""
        self.config = config or {}
        self.initialized = False

        # Entity patterns
        self.entity_patterns = {
            "PERSON": [
                r"\b[A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
                r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sir|Madam)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
            ],
            "ORGANIZATION": [
                r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Inc|Corp|Ltd|LLC|Co|Company|Corporation|Group|Institute|University|College)\b",
                r"\b(?:The\s+)?[A-Z][A-Z\s&]+(?:Inc|Corp|Ltd|LLC|Co)\b",
            ],
            "LOCATION": [
                r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s+[A-Z]{2}\b",
                r"\b(?:New York|Los Angeles|Chicago|Houston|Phoenix|Philadelphia|San Antonio|San Diego|Dallas|San Jose|Austin|Jacksonville|Fort Worth|Columbus|Charlotte|San Francisco|Indianapolis|Seattle|Denver|Boston|El Paso|Detroit|Nashville|Portland|Memphis|Oklahoma City|Las Vegas|Louisville|Baltimore|Milwaukee|Albuquerque|Tucson|Fresno|Sacramento|Long Beach|Kansas City|Mesa|Virginia Beach|Atlanta|Colorado Springs|Omaha|Raleigh|Miami|Oakland|Minneapolis|Tulsa|Cleveland|Wichita|Arlington|New Orleans|Bakersfield|Tampa|Honolulu|Aurora|Anaheim|Santa Ana|St. Louis|Riverside|Corpus Christi|Lexington|Pittsburgh|Anchorage|Stockton|Cincinnati|St. Paul|Toledo|Greensboro|Newark|Plano|Henderson|Lincoln|Buffalo|Jersey City|Chula Vista|Orlando|Norfolk|Chandler|Laredo|Madison|Durham|Lubbock|Winston-Salem|Garland|Glendale|Hialeah|Reno|Baton Rouge|Irvine|Chesapeake|Irving|Scottsdale|North Las Vegas|Fremont|Gilbert|San Bernardino|Boise|Birmingham)\b",
            ],
            "DATE": [
                r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
                r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
                r"\b\d{4}-\d{2}-\d{2}\b",
            ],
            "TIME": [
                r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b",
            ],
            "MONEY": [
                r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b",
                r"\b\d+(?:\.\d{2})?\s*(?:dollars?|USD|cents?)\b",
            ],
            "PERCENTAGE": [
                r"\b\d+(?:\.\d+)?%\b",
                r"\b\d+(?:\.\d+)?\s*percent\b",
            ],
            "EMAIL": [
                r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
            ],
            "PHONE": [
                r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
            ],
            "URL": [
                r"https?://[^\s]+",
                r"www\.[^\s]+\.[a-zA-Z]{2,}",
            ],
            "TECHNICAL_TERM": [
                r"\b[A-Z]{2,}(?:[A-Z][a-z]+)*\b",  # Acronyms
                r"\b[a-z]+(?:[A-Z][a-z]+)+\b",  # CamelCase
                r"\b[a-z_]+_[a-z_]+\b",  # snake_case
            ],
        }

        # Relationship patterns
        self.relationship_patterns = {
            "OWNERSHIP": [
                r"(\w+(?:\s+\w+)*)\s+(?:owns?|possesses?|has)\s+(\w+(?:\s+\w+)*)",
                r"(\w+(?:\s+\w+)*)\s+belongs?\s+to\s+(\w+(?:\s+\w+)*)",
            ],
            "EMPLOYMENT": [
                r"(\w+(?:\s+\w+)*)\s+(?:works?\s+(?:for|at)|is\s+employed\s+by)\s+(\w+(?:\s+\w+)*)",
                r"(\w+(?:\s+\w+)*)\s+is\s+(?:a|an)\s+(\w+(?:\s+\w+)*)\s+at\s+(\w+(?:\s+\w+)*)",
            ],
            "LOCATION_RELATIONSHIP": [
                r"(\w+(?:\s+\w+)*)\s+(?:is\s+(?:located\s+)?in|is\s+at)\s+(\w+(?:\s+\w+)*)",
                r"(\w+(?:\s+\w+)*)\s+(?:lives?\s+in|resides?\s+in)\s+(\w+(?:\s+\w+)*)",
            ],
            "CAUSE_EFFECT": [
                r"(\w+(?:\s+\w+)*)\s+(?:causes?|leads?\s+to|results?\s+in)\s+(\w+(?:\s+\w+)*)",
                r"(?:because\s+of|due\s+to)\s+(\w+(?:\s+\w+)*),?\s+(\w+(?:\s+\w+)*)",
            ],
            "TEMPORAL": [
                r"(\w+(?:\s+\w+)*)\s+(?:before|after|during)\s+(\w+(?:\s+\w+)*)",
                r"(\w+(?:\s+\w+)*)\s+(?:then|next|subsequently)\s+(\w+(?:\s+\w+)*)",
            ],
            "COMPARISON": [
                r"(\w+(?:\s+\w+)*)\s+(?:is\s+)?(?:better|worse|bigger|smaller|faster|slower)\s+than\s+(\w+(?:\s+\w+)*)",
                r"(\w+(?:\s+\w+)*)\s+(?:like|unlike|similar\s+to|different\s+from)\s+(\w+(?:\s+\w+)*)",
            ],
        }

        # Conceptual patterns
        self.conceptual_patterns = {
            "PROBLEM_SOLUTION": [
                r"(?:problem|issue|challenge|difficulty).*?(?:solution|answer|resolution|fix|resolve)",
                r"(?:trouble|error|bug|failure).*?(?:solution|fix|repair|correct)",
            ],
            "QUESTION_ANSWER": [
                r"(?:question|query|inquiry).*?(?:answer|response|reply)",
                r"\?.*?(?:answer|response|reply)",
            ],
            "PROCESS_STEPS": [
                r"(?:step\s+\d+|first|second|third|next|then|finally)",
                r"(?:process|procedure|method|approach).*?(?:steps|phases|stages)",
            ],
            "PROS_CONS": [
                r"(?:advantages?|benefits?|pros?).*?(?:disadvantages?|drawbacks?|cons?)",
                r"(?:positive|good|benefit).*?(?:negative|bad|drawback)",
            ],
            "DEFINITION": [
                r"(\w+(?:\s+\w+)*)\s+(?:is|means?|refers?\s+to|defined\s+as)\s+(.+?)(?:\.|$)",
                r"(?:define|definition\s+of)\s+(\w+(?:\s+\w+)*)",
            ],
        }

        # Sentiment patterns
        self.sentiment_patterns = {
            "POSITIVE": [
                r"\b(?:excellent|amazing|wonderful|fantastic|great|good|positive|happy|satisfied|pleased|delighted|thrilled|excited|love|like|enjoy|appreciate|recommend|perfect|outstanding|brilliant|superb|magnificent|exceptional|remarkable|impressive|awesome)\b",
            ],
            "NEGATIVE": [
                r"\b(?:terrible|awful|horrible|bad|worst|hate|dislike|disappointed|frustrated|angry|annoyed|upset|sad|depressed|disgusting|unacceptable|poor|inadequate|unsatisfactory|regret|complaint|problem|issue|error|failure|wrong)\b",
            ],
            "NEUTRAL": [
                r"\b(?:okay|ok|fine|average|normal|standard|typical|regular|usual|moderate|fair|acceptable|neutral)\b",
            ],
        }

    async def initialize(self):
        """Initialize the extractor with compiled patterns"""
        try:
            # Compile regex patterns for better performance
            self.compiled_entity_patterns = {}
            for entity_type, patterns in self.entity_patterns.items():
                self.compiled_entity_patterns[entity_type] = [
                    re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                    for pattern in patterns
                ]

            self.compiled_relationship_patterns = {}
            for rel_type, patterns in self.relationship_patterns.items():
                self.compiled_relationship_patterns[rel_type] = [
                    re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                    for pattern in patterns
                ]

            self.compiled_conceptual_patterns = {}
            for concept_type, patterns in self.conceptual_patterns.items():
                self.compiled_conceptual_patterns[concept_type] = [
                    re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                    for pattern in patterns
                ]

            self.compiled_sentiment_patterns = {}
            for sentiment_type, patterns in self.sentiment_patterns.items():
                self.compiled_sentiment_patterns[sentiment_type] = [
                    re.compile(pattern, re.IGNORECASE) for pattern in patterns
                ]

            self.initialized = True
            logger.info("Semantic pattern extractor initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize semantic pattern extractor: {e}")
            self.initialized = False

    async def extract(
        self, content: str, language: str = "en"
    ) -> SemanticPatternResult:
        """
        Extract comprehensive semantic patterns from content

        Args:
            content: The content to extract from
            language: Language code for processing

        Returns:
            SemanticPatternResult with extracted patterns, entities, and relationships
        """
        if not self.initialized:
            await self.initialize()

        start_time = datetime.now()

        try:
            # Run all extraction methods concurrently
            entities_task = asyncio.create_task(self.extract_entities(content))
            relationships_task = asyncio.create_task(
                self.extract_relationships(content)
            )
            concepts_task = asyncio.create_task(self.extract_concepts(content))
            patterns_task = asyncio.create_task(
                self._extract_semantic_patterns(content)
            )

            # Wait for all tasks to complete
            entities = await entities_task
            relationships = await relationships_task
            concepts = await concepts_task
            patterns = await patterns_task

            # Calculate processing statistics
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            # Generate metadata
            metadata = {
                "content_length": len(content),
                "language": language,
                "processing_time_seconds": processing_time,
                "extraction_timestamp": end_time.isoformat(),
                "entities_found": len(entities),
                "relationships_found": len(relationships),
                "concepts_found": len(concepts),
                "patterns_found": len(patterns),
                "content_complexity": self._assess_content_complexity(content),
                "sentiment_analysis": self._analyze_sentiment(content),
            }

            # Compile statistics
            statistics = self._compile_statistics(
                content, entities, relationships, concepts, patterns
            )

            return SemanticPatternResult(
                patterns=patterns,
                entities=[SemanticEntity(**entity) for entity in entities],
                relationships=[SemanticRelationship(**rel) for rel in relationships],
                concepts=[ConceptualPattern(**concept) for concept in concepts],
                metadata=metadata,
                statistics=statistics,
            )

        except Exception as e:
            logger.error(f"Error during semantic pattern extraction: {e}")
            return SemanticPatternResult(
                patterns=[],
                entities=[],
                relationships=[],
                concepts=[],
                metadata={
                    "content_length": len(content),
                    "language": language,
                    "error": str(e),
                    "status": "extraction_failed",
                },
            )

    async def extract_entities(self, content: str) -> List[Dict[str, Any]]:
        """Extract named entities from content with position and confidence"""
        entities = []

        for entity_type, patterns in self.compiled_entity_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(content):
                    entity_text = match.group().strip()
                    start_pos = match.start()
                    end_pos = match.end()

                    # Calculate context (50 chars before and after)
                    context_start = max(0, start_pos - 50)
                    context_end = min(len(content), end_pos + 50)
                    context = content[context_start:context_end].strip()

                    # Calculate confidence based on pattern specificity and context
                    confidence = self._calculate_entity_confidence(
                        entity_text, entity_type, context
                    )

                    entities.append(
                        {
                            "text": entity_text,
                            "entity_type": entity_type,
                            "start_position": start_pos,
                            "end_position": end_pos,
                            "confidence": confidence,
                            "context": context,
                            "properties": self._extract_entity_properties(
                                entity_text, entity_type
                            ),
                        }
                    )

        # Remove duplicates and sort by confidence
        entities = self._deduplicate_entities(entities)
        return sorted(entities, key=lambda x: x["confidence"], reverse=True)

    async def extract_relationships(self, content: str) -> List[Dict[str, Any]]:
        """Extract relationships between entities with confidence scoring"""
        relationships = []

        for rel_type, patterns in self.compiled_relationship_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(content):
                    full_match = match.group().strip()
                    groups = match.groups()

                    if len(groups) >= 2:
                        subject = groups[0].strip()
                        obj = groups[-1].strip()  # Last group is typically the object

                        # Determine predicate based on relationship type
                        predicate = self._determine_predicate(rel_type, full_match)

                        # Calculate context
                        context_start = max(0, match.start() - 30)
                        context_end = min(len(content), match.end() + 30)
                        context = content[context_start:context_end].strip()

                        # Calculate confidence
                        confidence = self._calculate_relationship_confidence(
                            subject, predicate, obj, context, rel_type
                        )

                        relationships.append(
                            {
                                "subject": subject,
                                "predicate": predicate,
                                "object": obj,
                                "confidence": confidence,
                                "context": context,
                                "relationship_type": rel_type,
                            }
                        )

        return sorted(relationships, key=lambda x: x["confidence"], reverse=True)

    async def extract_concepts(self, content: str) -> List[Dict[str, Any]]:
        """Extract conceptual patterns from content"""
        concepts = []

        for concept_type, patterns in self.compiled_conceptual_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(content):
                    concept_text = match.group().strip()

                    # Extract elements of the conceptual pattern
                    elements = self._extract_concept_elements(
                        concept_text, concept_type
                    )

                    # Calculate context
                    context_start = max(0, match.start() - 100)
                    context_end = min(len(content), match.end() + 100)
                    context = content[context_start:context_end].strip()

                    # Calculate confidence
                    confidence = self._calculate_concept_confidence(
                        concept_text, concept_type, elements
                    )

                    concepts.append(
                        {
                            "pattern_name": f"{concept_type.lower()}_pattern",
                            "pattern_type": concept_type,
                            "elements": elements,
                            "confidence": confidence,
                            "context": context,
                            "properties": {
                                "full_text": concept_text,
                                "length": len(concept_text),
                                "complexity": len(elements),
                            },
                        }
                    )

        return sorted(concepts, key=lambda x: x["confidence"], reverse=True)

    async def extract_semantic_patterns(
        self,
        content: str,
        entities: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> "SemanticAnalysisResult":
        """
        Public method to extract semantic patterns from content.
        This is the interface method expected by external callers.

        Args:
            content: The text content to analyze
            entities: Previously extracted entities to enhance pattern detection
            context: Additional context for semantic analysis

        Returns:
            SemanticAnalysisResult with comprehensive semantic analysis
        """
        if not self.initialized:
            await self.initialize()

        try:
            logger.info(
                f"[INTERFACE] extract_semantic_patterns called with content length: {len(content)}"
            )

            # Import here to avoid circular imports
            from models.extraction_models import SemanticAnalysisResult

            # Use provided entities to enhance pattern extraction
            if entities:
                self._provided_entities = entities

            # Use context for better analysis
            if context:
                self._analysis_context = context

            # Extract semantic patterns using existing method
            semantic_patterns = await self._extract_semantic_patterns(content)

            # Extract concepts, themes, and topics
            concepts = self._extract_concepts_list(content)
            themes = self._extract_themes_list(content)
            topics = self._extract_topics_list(content)

            # Calculate semantic metrics
            semantic_density = self._calculate_semantic_density(
                content, semantic_patterns
            )
            conceptual_coherence = self._calculate_conceptual_coherence(concepts)
            thematic_consistency = self._calculate_thematic_consistency(themes)

            # Build semantic context
            semantic_context = {
                "analysis_language": "en",
                "content_length": len(content),
                "analysis_context": context,
                "timestamp": datetime.now().isoformat(),
                "entity_count": len(entities) if entities else 0,
                "provided_context": bool(context),
            }

            # Extract domain indicators
            domain_indicators = self._extract_domain_indicators(content)

            # Topic analysis
            topic_weights = self._calculate_topic_weights(topics, content)
            primary_topics = sorted(
                topics, key=lambda t: topic_weights.get(t, 0), reverse=True
            )[:5]

            # Create the result object
            result = SemanticAnalysisResult(
                semantic_patterns=[
                    {
                        "pattern_id": f"pattern_{i}",
                        "pattern_type": pattern.pattern_type,
                        "pattern_name": f"{pattern.pattern_type.lower()}_pattern_{i}",
                        "description": f"Semantic pattern of type {pattern.pattern_type}",
                        "examples": [pattern.text] if pattern.text else [],
                        "frequency": 1,
                        "confidence_score": pattern.confidence,
                        "significance_score": pattern.confidence * 0.8,
                        "context": pattern.metadata or {},
                        "properties": pattern.metadata or {},
                        "related_entity_ids": [],
                    }
                    for i, pattern in enumerate(semantic_patterns)
                ],
                concepts=concepts,
                themes=themes,
                semantic_density=semantic_density,
                conceptual_coherence=conceptual_coherence,
                thematic_consistency=thematic_consistency,
                semantic_context=semantic_context,
                domain_indicators=domain_indicators,
                primary_topics=primary_topics,
                topic_weights=topic_weights,
            )

            logger.info(
                f"[INTERFACE] extract_semantic_patterns completed successfully - type: {type(result)}"
            )
            logger.info(
                f"[INTERFACE] Result has semantic_context: {hasattr(result, 'semantic_context')}"
            )
            logger.info(
                f"[INTERFACE] Result semantic_context type: {type(result.semantic_context)}"
            )

            return result

        except Exception as e:
            logger.error(f"[INTERFACE] extract_semantic_patterns failed: {e}")
            # Return empty result rather than failing
            from models.extraction_models import SemanticAnalysisResult

            return SemanticAnalysisResult(
                semantic_patterns=[],
                concepts=[],
                themes=[],
                semantic_context={"error": str(e), "status": "failed"},
            )

    async def analyze_semantic_content(
        self,
        content: str,
        context: Optional[str] = None,
        language: Optional[str] = None,
    ):
        """
        Analyze semantic content and return semantic analysis result.
        This method is called by the /analyze/semantic endpoint.

        Args:
            content: The text content to analyze
            context: Optional context for analysis
            language: Optional language hint

        Returns:
            SemanticAnalysisResult: Comprehensive semantic analysis
        """
        if not self.initialized:
            await self.initialize()

        try:
            logger.info(
                f"Starting semantic content analysis for {len(content)} characters"
            )

            # Import here to avoid circular imports
            from models.extraction_models import SemanticAnalysisResult

            # Extract semantic patterns using existing method
            semantic_patterns = await self.extract_semantic_patterns(content)

            # Extract concepts, themes, and topics
            concepts = self._extract_concepts_list(content)
            themes = self._extract_themes_list(content)
            topics = self._extract_topics_list(content)

            # Calculate semantic metrics
            semantic_density = self._calculate_semantic_density(
                content, semantic_patterns
            )
            conceptual_coherence = self._calculate_conceptual_coherence(concepts)
            thematic_consistency = self._calculate_thematic_consistency(themes)

            # Build semantic context
            semantic_context = {
                "analysis_language": language or "en",
                "content_length": len(content),
                "analysis_context": context,
                "timestamp": datetime.now().isoformat(),
            }

            # Extract domain indicators
            domain_indicators = self._extract_domain_indicators(content)

            # Topic analysis
            topic_weights = self._calculate_topic_weights(topics, content)
            primary_topics = sorted(
                topics, key=lambda t: topic_weights.get(t, 0), reverse=True
            )[:5]

            result = SemanticAnalysisResult(
                semantic_patterns=[
                    {
                        "pattern_id": f"pattern_{i}",
                        "pattern_type": pattern.pattern_type,
                        "pattern_name": f"{pattern.pattern_type.lower()}_pattern_{i}",
                        "description": f"Semantic pattern of type {pattern.pattern_type}",
                        "examples": [pattern.text] if pattern.text else [],
                        "frequency": 1,
                        "confidence_score": pattern.confidence,
                        "significance_score": pattern.confidence * 0.8,
                        "context": pattern.metadata or {},
                        "properties": pattern.metadata or {},
                        "related_entity_ids": [],
                    }
                    for i, pattern in enumerate(semantic_patterns)
                ],
                concepts=concepts,
                themes=themes,
                semantic_density=semantic_density,
                conceptual_coherence=conceptual_coherence,
                thematic_consistency=thematic_consistency,
                semantic_context=semantic_context,
                domain_indicators=domain_indicators,
                primary_topics=primary_topics,
                topic_weights=topic_weights,
            )

            logger.info(
                f"Semantic analysis completed - {len(concepts)} concepts, {len(themes)} themes"
            )
            return result

        except Exception as e:
            logger.error(f"Semantic content analysis failed: {e}")
            # Return empty result rather than failing
            from models.extraction_models import SemanticAnalysisResult

            return SemanticAnalysisResult(
                semantic_patterns=[],
                concepts=[],
                themes=[],
                semantic_context={"error": str(e), "status": "failed"},
            )

    def _extract_concepts_list(self, content: str) -> List[str]:
        """Extract a list of key concepts from content"""
        concepts = []

        # Use existing conceptual pattern detection
        for concept_type, patterns in self.compiled_conceptual_patterns.items():
            for pattern in patterns:
                matches = pattern.finditer(content)
                for match in matches:
                    concept_text = match.group().strip()
                    # Extract key terms from the concept
                    key_terms = re.findall(r"\b[a-zA-Z]{4,}\b", concept_text.lower())
                    concepts.extend(key_terms[:3])  # Add up to 3 key terms per concept

        # Add high-frequency meaningful words as concepts
        words = re.findall(r"\b[a-zA-Z]{4,}\b", content.lower())
        word_freq = Counter(words)
        frequent_concepts = [
            word for word, freq in word_freq.most_common(15) if freq > 2
        ]
        concepts.extend(frequent_concepts)

        return list(set(concepts))  # Remove duplicates

    def _extract_themes_list(self, content: str) -> List[str]:
        """Extract a list of themes from content"""
        themes = []

        # Use theme extraction from existing method
        theme_results = self._extract_themes(content)
        for theme in theme_results:
            themes.append(theme["text"])
            # Also add individual keywords as themes
            themes.extend(theme.get("keywords", [])[:3])

        return list(set(themes))

    def _extract_topics_list(self, content: str) -> List[str]:
        """Extract a list of topics from content"""
        topics = []

        # Use topic extraction from existing method
        topic_results = self._extract_topics(content)
        for topic in topic_results:
            topics.append(topic["text"])

        # Add sentence-level topics
        sentences = re.split(r"[.!?]+", content)
        for sentence in sentences[:10]:  # Analyze first 10 sentences
            if len(sentence.strip()) > 20:
                # Extract main nouns as potential topics
                nouns = re.findall(r"\b[A-Z][a-z]{3,}\b", sentence)
                topics.extend(nouns[:2])

        return list(set(topics))

    def _calculate_semantic_density(self, content: str, patterns: List) -> float:
        """Calculate how semantically dense the content is"""
        if not content or not patterns:
            return 0.0

        word_count = len(content.split())
        pattern_count = len(patterns)

        # Density based on patterns per 100 words
        density = min(1.0, (pattern_count / max(word_count, 1)) * 100)
        return round(density, 3)

    def _calculate_conceptual_coherence(self, concepts: List[str]) -> float:
        """Calculate how coherent the concepts are"""
        if len(concepts) < 2:
            return 0.5

        # Simple coherence based on concept overlap and frequency
        Counter(concepts)
        unique_concepts = len(set(concepts))
        total_concepts = len(concepts)

        # Higher coherence if there are repeated concepts (indicating consistency)
        coherence = min(
            1.0, (total_concepts - unique_concepts) / max(total_concepts, 1) + 0.3
        )
        return round(coherence, 3)

    def _calculate_thematic_consistency(self, themes: List[str]) -> float:
        """Calculate thematic consistency of the content"""
        if len(themes) < 2:
            return 0.5

        # Simple consistency measure based on theme overlap
        theme_words = []
        for theme in themes:
            theme_words.extend(theme.lower().split())

        word_freq = Counter(theme_words)
        repeated_words = sum(1 for freq in word_freq.values() if freq > 1)
        total_words = len(theme_words)

        consistency = min(1.0, repeated_words / max(total_words, 1) + 0.4)
        return round(consistency, 3)

    def _extract_domain_indicators(self, content: str) -> List[str]:
        """Extract domain-specific indicators from content"""
        indicators = []

        # Technical domain indicators
        technical_patterns = [
            r"\b(?:API|SDK|framework|library|module|class|function|method|variable)\b",
            r"\b(?:database|server|client|endpoint|protocol|authentication)\b",
            r"\b(?:algorithm|data|structure|pattern|implementation|architecture)\b",
        ]

        for pattern in technical_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            indicators.extend(matches)

        # Business domain indicators
        business_patterns = [
            r"\b(?:customer|user|client|business|market|product|service)\b",
            r"\b(?:requirement|specification|process|workflow|procedure)\b",
            r"\b(?:analysis|report|documentation|guidelines|standards)\b",
        ]

        for pattern in business_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            indicators.extend(matches)

        return list(set([indicator.lower() for indicator in indicators]))

    def _calculate_topic_weights(
        self, topics: List[str], content: str
    ) -> Dict[str, float]:
        """Calculate weights for topics based on frequency and context"""
        weights = {}
        content_lower = content.lower()

        for topic in topics:
            topic_lower = topic.lower()
            # Count occurrences
            frequency = content_lower.count(topic_lower)
            # Calculate weight based on frequency and topic length
            weight = min(
                1.0,
                (frequency / max(len(content.split()), 1)) * 100
                + len(topic.split()) * 0.1,
            )
            weights[topic] = round(weight, 3)

        return weights

    async def _extract_semantic_patterns(self, content: str) -> List[SemanticPattern]:
        """Extract high-level semantic patterns from content"""
        patterns = []

        # Theme extraction
        themes = self._extract_themes(content)
        for theme in themes:
            patterns.append(
                SemanticPattern(
                    pattern_type="THEME",
                    confidence=theme["confidence"],
                    text=theme["text"],
                    metadata={"theme_keywords": theme["keywords"]},
                )
            )

        # Topic extraction
        topics = self._extract_topics(content)
        for topic in topics:
            patterns.append(
                SemanticPattern(
                    pattern_type="TOPIC",
                    confidence=topic["confidence"],
                    text=topic["text"],
                    metadata={"topic_keywords": topic["keywords"]},
                )
            )

        # Structure patterns (lists, enumerations, etc.)
        structure_patterns = self._extract_structure_patterns(content)
        patterns.extend(structure_patterns)

        return sorted(patterns, key=lambda x: x.confidence, reverse=True)

    def _calculate_entity_confidence(
        self, entity_text: str, entity_type: str, context: str
    ) -> float:
        """Calculate confidence score for entity recognition"""
        base_confidence = 0.6

        # Length bonus for longer entities (typically more specific)
        if len(entity_text) > 10:
            base_confidence += 0.1

        # Context validation
        if entity_type in ["PERSON"] and any(
            title in context.lower() for title in ["mr.", "mrs.", "dr.", "prof."]
        ):
            base_confidence += 0.2

        if entity_type in ["ORGANIZATION"] and any(
            indicator in context.lower() for indicator in ["company", "corp", "inc"]
        ):
            base_confidence += 0.2

        # Pattern specificity (more specific patterns get higher confidence)
        if entity_type in ["EMAIL", "PHONE", "URL"]:
            base_confidence += 0.3

        return min(1.0, base_confidence)

    def _calculate_relationship_confidence(
        self, subject: str, predicate: str, obj: str, context: str, rel_type: str
    ) -> float:
        """Calculate confidence score for relationship extraction"""
        base_confidence = 0.5

        # Both entities should be meaningful
        if len(subject) > 2 and len(obj) > 2:
            base_confidence += 0.2

        # Specific relationship types are more confident
        if rel_type in ["OWNERSHIP", "EMPLOYMENT"]:
            base_confidence += 0.2

        # Clear predicate indicators
        if any(
            indicator in predicate.lower()
            for indicator in ["owns", "works for", "is located in"]
        ):
            base_confidence += 0.1

        return min(1.0, base_confidence)

    def _calculate_concept_confidence(
        self, concept_text: str, concept_type: str, elements: List[str]
    ) -> float:
        """Calculate confidence score for conceptual patterns"""
        base_confidence = 0.4

        # More elements typically indicate stronger patterns
        if len(elements) > 2:
            base_confidence += 0.2

        # Specific concept types
        if concept_type in ["DEFINITION", "PROBLEM_SOLUTION"]:
            base_confidence += 0.2

        # Length and structure indicators
        if len(concept_text) > 50:
            base_confidence += 0.1

        return min(1.0, base_confidence)

    def _extract_entity_properties(
        self, entity_text: str, entity_type: str
    ) -> Dict[str, Any]:
        """Extract additional properties for entities"""
        properties = {}

        if entity_type == "DATE":
            # Try to parse date formats
            properties["raw_text"] = entity_text
        elif entity_type == "MONEY":
            # Extract numerical value
            amount_match = re.search(r"[\d,]+\.?\d*", entity_text)
            if amount_match:
                properties["amount"] = amount_match.group()
        elif entity_type == "PERCENTAGE":
            # Extract numerical value
            percent_match = re.search(r"\d+(?:\.\d+)?", entity_text)
            if percent_match:
                properties["value"] = float(percent_match.group())

        return properties

    def _determine_predicate(self, rel_type: str, full_match: str) -> str:
        """Determine the predicate for a relationship based on type and text"""
        predicate_mapping = {
            "OWNERSHIP": "owns",
            "EMPLOYMENT": "works_for",
            "LOCATION_RELATIONSHIP": "located_in",
            "CAUSE_EFFECT": "causes",
            "TEMPORAL": "occurs_before",
            "COMPARISON": "compared_to",
        }

        # Try to extract actual predicate from text
        predicate_words = re.findall(
            r"\b(?:owns?|works?\s+for|is\s+located|causes?|before|after|better|worse)\b",
            full_match.lower(),
        )
        if predicate_words:
            return predicate_words[0].replace(" ", "_")

        return predicate_mapping.get(rel_type, "relates_to")

    def _extract_concept_elements(
        self, concept_text: str, concept_type: str
    ) -> List[str]:
        """Extract constituent elements from conceptual patterns"""
        elements = []

        if concept_type == "PROBLEM_SOLUTION":
            # Look for problem and solution parts
            problem_words = re.findall(
                r"\b\w+(?:\s+\w+)*(?=.*(?:problem|issue|challenge))",
                concept_text.lower(),
            )
            solution_words = re.findall(
                r"\b\w+(?:\s+\w+)*(?=.*(?:solution|answer|fix))", concept_text.lower()
            )
            elements.extend(problem_words[:3])  # Limit to first 3
            elements.extend(solution_words[:3])

        elif concept_type == "PROCESS_STEPS":
            # Extract step indicators and descriptions
            step_matches = re.findall(
                r"(?:step\s+\d+|first|second|third|next|then|finally)[:\s]+([^.]+)",
                concept_text.lower(),
            )
            elements.extend([match.strip() for match in step_matches])

        else:
            # Generic element extraction - split into meaningful phrases
            phrases = re.findall(r"\b\w+(?:\s+\w+){1,3}\b", concept_text)
            elements = phrases[:5]  # Limit to first 5 phrases

        return [elem for elem in elements if len(elem) > 2]

    def _extract_themes(self, content: str) -> List[Dict[str, Any]]:
        """Extract major themes from content"""
        themes = []

        # Word frequency analysis for theme detection
        words = re.findall(r"\b[a-zA-Z]{4,}\b", content.lower())
        word_freq = Counter(words)

        # Group related words into themes
        common_words = [word for word, freq in word_freq.most_common(20) if freq > 2]

        # Simple theme clustering (this could be enhanced with NLP libraries)
        if common_words:
            themes.append(
                {
                    "text": f"Primary theme involving: {', '.join(common_words[:5])}",
                    "confidence": 0.7,
                    "keywords": common_words[:10],
                }
            )

        return themes

    def _extract_topics(self, content: str) -> List[Dict[str, Any]]:
        """Extract topics from content"""
        topics = []

        # Look for topic indicators
        topic_patterns = [
            r"(?:topic|subject|about|regarding|concerning)[:\s]+([^.]+)",
            r"(?:discussion|talk|article|post)\s+(?:about|on|regarding)[:\s]+([^.]+)",
        ]

        for pattern in topic_patterns:
            matches = re.findall(pattern, content.lower())
            for match in matches:
                if len(match.strip()) > 5:
                    topics.append(
                        {
                            "text": match.strip(),
                            "confidence": 0.6,
                            "keywords": match.strip().split()[:5],
                        }
                    )

        return topics

    def _extract_structure_patterns(self, content: str) -> List[SemanticPattern]:
        """Extract structural patterns like lists, enumerations"""
        patterns = []

        # Numbered lists
        numbered_lists = re.findall(
            r"(?:\d+[\.\)]\s+.+(?:\n|$))+", content, re.MULTILINE
        )
        for list_text in numbered_lists:
            items = re.findall(r"\d+[\.\)]\s+(.+)", list_text)
            if len(items) >= 2:
                patterns.append(
                    SemanticPattern(
                        pattern_type="NUMBERED_LIST",
                        confidence=0.8,
                        text=list_text.strip(),
                        metadata={"items": items, "item_count": len(items)},
                    )
                )

        # Bullet points
        bullet_lists = re.findall(r"(?:[•\-\*]\s+.+(?:\n|$))+", content, re.MULTILINE)
        for list_text in bullet_lists:
            items = re.findall(r"[•\-\*]\s+(.+)", list_text)
            if len(items) >= 2:
                patterns.append(
                    SemanticPattern(
                        pattern_type="BULLET_LIST",
                        confidence=0.8,
                        text=list_text.strip(),
                        metadata={"items": items, "item_count": len(items)},
                    )
                )

        return patterns

    def _deduplicate_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate entities based on text and position"""
        unique_entities = []
        seen = set()

        for entity in entities:
            key = (
                entity["text"].lower(),
                entity["entity_type"],
                entity["start_position"] // 10,
            )  # Allow some position variance
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)

        return unique_entities

    def _assess_content_complexity(self, content: str) -> str:
        """Assess the complexity of the content"""
        word_count = len(content.split())
        sentence_count = len(re.findall(r"[.!?]+", content))
        avg_sentence_length = word_count / max(sentence_count, 1)

        if word_count < 100:
            return "simple"
        elif word_count < 500 and avg_sentence_length < 20:
            return "moderate"
        elif word_count < 1000 and avg_sentence_length < 30:
            return "complex"
        else:
            return "highly_complex"

    def _analyze_sentiment(self, content: str) -> Dict[str, Any]:
        """Basic sentiment analysis of content"""
        sentiment_scores = {"positive": 0, "negative": 0, "neutral": 0}

        for sentiment_type, patterns in self.compiled_sentiment_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(content)
                sentiment_scores[sentiment_type.lower()] += len(matches)

        total_sentiments = sum(sentiment_scores.values())
        if total_sentiments == 0:
            return {"overall": "neutral", "scores": sentiment_scores, "confidence": 0.3}

        # Calculate percentages
        for sentiment in sentiment_scores:
            sentiment_scores[sentiment] = sentiment_scores[sentiment] / total_sentiments

        # Determine overall sentiment
        overall = max(sentiment_scores, key=sentiment_scores.get)
        confidence = sentiment_scores[overall]

        return {
            "overall": overall,
            "scores": sentiment_scores,
            "confidence": min(1.0, confidence * 2),  # Boost confidence
            "total_indicators": total_sentiments,
        }

    def _compile_statistics(
        self,
        content: str,
        entities: List[Dict],
        relationships: List[Dict],
        concepts: List[Dict],
        patterns: List[SemanticPattern],
    ) -> Dict[str, Any]:
        """Compile comprehensive extraction statistics"""

        # Entity statistics
        entity_types = Counter(entity["entity_type"] for entity in entities)
        avg_entity_confidence = sum(entity["confidence"] for entity in entities) / max(
            len(entities), 1
        )

        # Relationship statistics
        relationship_types = Counter(rel["relationship_type"] for rel in relationships)
        avg_relationship_confidence = sum(
            rel["confidence"] for rel in relationships
        ) / max(len(relationships), 1)

        # Concept statistics
        concept_types = Counter(concept["pattern_type"] for concept in concepts)
        avg_concept_confidence = sum(
            concept["confidence"] for concept in concepts
        ) / max(len(concepts), 1)

        # Pattern statistics
        pattern_types = Counter(pattern.pattern_type for pattern in patterns)
        avg_pattern_confidence = sum(pattern.confidence for pattern in patterns) / max(
            len(patterns), 1
        )

        # Content statistics
        word_count = len(content.split())
        char_count = len(content)
        density_ratio = (
            (len(entities) + len(relationships) + len(concepts))
            / max(word_count, 1)
            * 100
        )

        return {
            "extraction_summary": {
                "total_entities": len(entities),
                "total_relationships": len(relationships),
                "total_concepts": len(concepts),
                "total_patterns": len(patterns),
                "extraction_density_percent": round(density_ratio, 2),
            },
            "entity_statistics": {
                "types_found": dict(entity_types),
                "average_confidence": round(avg_entity_confidence, 3),
                "most_common_type": (
                    entity_types.most_common(1)[0][0] if entity_types else None
                ),
            },
            "relationship_statistics": {
                "types_found": dict(relationship_types),
                "average_confidence": round(avg_relationship_confidence, 3),
                "most_common_type": (
                    relationship_types.most_common(1)[0][0]
                    if relationship_types
                    else None
                ),
            },
            "concept_statistics": {
                "types_found": dict(concept_types),
                "average_confidence": round(avg_concept_confidence, 3),
                "most_common_type": (
                    concept_types.most_common(1)[0][0] if concept_types else None
                ),
            },
            "pattern_statistics": {
                "types_found": dict(pattern_types),
                "average_confidence": round(avg_pattern_confidence, 3),
                "most_common_type": (
                    pattern_types.most_common(1)[0][0] if pattern_types else None
                ),
            },
            "content_statistics": {
                "word_count": word_count,
                "character_count": char_count,
                "complexity_assessment": self._assess_content_complexity(content),
            },
        }
