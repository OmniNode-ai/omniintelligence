"""
Semantic Enricher - Advanced Implementation

This module provides comprehensive semantic enrichment capabilities for the LangExtract service,
including concept identification, semantic relationships, knowledge graph integration,
and contextual understanding enhancement.
"""

import asyncio
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SemanticConcept(BaseModel):
    """A semantic concept with comprehensive metadata"""

    concept: str
    confidence: float = Field(ge=0.0, le=1.0)
    category: str = "general"
    related_concepts: List[str] = Field(default_factory=list)
    synonyms: List[str] = Field(default_factory=list)
    broader_concepts: List[str] = Field(default_factory=list)
    narrower_concepts: List[str] = Field(default_factory=list)
    context_score: float = Field(ge=0.0, le=1.0, default=0.0)
    frequency: int = 0
    positions: List[int] = Field(default_factory=list)


class EntityEnrichment(BaseModel):
    """Enrichment information for entities"""

    original_entity: str
    enriched_type: str
    canonical_form: str
    semantic_roles: List[str] = Field(default_factory=list)
    domain_category: str = ""
    contextual_meaning: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    knowledge_links: List[str] = Field(default_factory=list)


class SemanticGraph(BaseModel):
    """Semantic graph representation"""

    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    clusters: List[List[str]] = Field(default_factory=list)
    centrality_scores: Dict[str, float] = Field(default_factory=dict)


class SemanticEnrichmentResult(BaseModel):
    """Comprehensive result model for semantic enrichment"""

    concepts: List[SemanticConcept] = Field(default_factory=list)
    entity_enrichments: List[EntityEnrichment] = Field(default_factory=list)
    semantic_graph: SemanticGraph = Field(default_factory=SemanticGraph)
    enriched_text: str = ""
    context_insights: Dict[str, Any] = Field(default_factory=dict)
    domain_classification: Dict[str, float] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    enrichment_type: str = "semantic"
    statistics: Dict[str, Any] = Field(default_factory=dict)


class SemanticEnricher:
    """
    Advanced semantic enricher for enhancing text with semantic information,
    concept identification, knowledge graph integration, and contextual understanding.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the semantic enricher"""
        self.config = config or {}
        self.initialized = False

        # Domain categories and their indicators
        self.domain_indicators = {
            "technology": {
                "keywords": [
                    "software",
                    "hardware",
                    "algorithm",
                    "database",
                    "server",
                    "network",
                    "programming",
                    "development",
                    "api",
                    "framework",
                    "architecture",
                    "system",
                    "application",
                    "platform",
                    "interface",
                    "protocol",
                    "security",
                    "encryption",
                ],
                "patterns": [
                    r"\b(?:AI|ML|API|UI|UX|IoT|VR|AR)\b",
                    r"\b\w+\.(?:com|net|org)\b",
                ],
            },
            "business": {
                "keywords": [
                    "revenue",
                    "profit",
                    "market",
                    "customer",
                    "strategy",
                    "management",
                    "sales",
                    "marketing",
                    "operations",
                    "finance",
                    "investment",
                    "budget",
                    "growth",
                    "performance",
                    "analytics",
                    "metrics",
                    "ROI",
                    "KPI",
                ],
                "patterns": [r"\$[\d,]+(?:\.\d{2})?", r"\b\d+%\b", r"\bQ[1-4]\b"],
            },
            "science": {
                "keywords": [
                    "research",
                    "study",
                    "experiment",
                    "hypothesis",
                    "analysis",
                    "data",
                    "methodology",
                    "results",
                    "conclusion",
                    "theory",
                    "evidence",
                    "statistical",
                    "significant",
                    "correlation",
                    "model",
                    "framework",
                    "validation",
                ],
                "patterns": [
                    r"\bp\s*[<>=]\s*0\.\d+",
                    r"\b[A-Z][a-z]+\s+et\s+al\.",
                    r"\b\d{4}\b(?=\s*study|research)",
                ],
            },
            "academic": {
                "keywords": [
                    "university",
                    "professor",
                    "student",
                    "course",
                    "degree",
                    "education",
                    "learning",
                    "knowledge",
                    "curriculum",
                    "assessment",
                    "thesis",
                    "dissertation",
                    "academic",
                    "scholarly",
                    "peer-reviewed",
                    "publication",
                    "conference",
                ],
                "patterns": [
                    r"\b(?:PhD|MSc|BSc|MA|BA)\b",
                    r"\bvol\.\s*\d+",
                    r"\bpp\.\s*\d+-\d+",
                ],
            },
            "medical": {
                "keywords": [
                    "patient",
                    "treatment",
                    "diagnosis",
                    "symptoms",
                    "disease",
                    "therapy",
                    "medication",
                    "clinical",
                    "medical",
                    "health",
                    "hospital",
                    "doctor",
                    "surgery",
                    "procedure",
                    "pharmaceutical",
                    "dosage",
                    "adverse",
                ],
                "patterns": [r"\b\d+\s*mg\b", r"\b\d+\s*ml\b", r"\bICD-\d+"],
            },
            "legal": {
                "keywords": [
                    "law",
                    "legal",
                    "court",
                    "judge",
                    "attorney",
                    "case",
                    "statute",
                    "regulation",
                    "compliance",
                    "contract",
                    "agreement",
                    "liability",
                    "defendant",
                    "plaintiff",
                    "evidence",
                    "testimony",
                    "verdict",
                ],
                "patterns": [
                    r"\bv\.\s+[A-Z][a-z]+",
                    r"\b\d+\s+U\.S\.C\.",
                    r"\bCFR\s+\d+",
                ],
            },
        }

        # Semantic role patterns
        self.semantic_roles = {
            "agent": [
                r"(\w+(?:\s+\w+)*)\s+(?:performs?|executes?|carries?\s+out|conducts?)",
                r"(\w+(?:\s+\w+)*)\s+(?:is\s+responsible\s+for|manages?|leads?)",
            ],
            "patient": [
                r"(\w+(?:\s+\w+)*)\s+(?:receives?|undergoes?|experiences?)",
                r"(?:affects?|impacts?)\s+(\w+(?:\s+\w+)*)",
            ],
            "instrument": [
                r"(?:using|with|via|through)\s+(\w+(?:\s+\w+)*)",
                r"(\w+(?:\s+\w+)*)\s+(?:is\s+used|serves?\s+as|functions?\s+as)",
            ],
            "location": [
                r"(?:at|in|on|within)\s+(\w+(?:\s+\w+)*)",
                r"(\w+(?:\s+\w+)*)\s+(?:is\s+located|situated|positioned)",
            ],
            "time": [
                r"(?:during|at|on|in)\s+(\w+(?:\s+\w+)*\s+(?:time|period|phase|stage))",
                r"(\w+(?:\s+\w+)*)\s+(?:occurred|happened|took\s+place)",
            ],
        }

        # Concept hierarchies (simplified knowledge base)
        self.concept_hierarchies = {
            "technology": {
                "broader": ["science", "innovation", "advancement"],
                "narrower": [
                    "software",
                    "hardware",
                    "artificial_intelligence",
                    "networking",
                ],
            },
            "software": {
                "broader": ["technology", "computing"],
                "narrower": ["application", "program", "system", "framework"],
            },
            "artificial_intelligence": {
                "broader": ["technology", "computer_science"],
                "narrower": ["machine_learning", "neural_networks", "deep_learning"],
                "synonyms": ["AI", "artificial intelligence", "machine intelligence"],
            },
            "machine_learning": {
                "broader": ["artificial_intelligence", "data_science"],
                "narrower": [
                    "supervised_learning",
                    "unsupervised_learning",
                    "reinforcement_learning",
                ],
                "synonyms": ["ML", "machine learning", "automated learning"],
            },
            "business": {
                "broader": ["commerce", "economy"],
                "narrower": ["marketing", "sales", "operations", "finance"],
            },
            "marketing": {
                "broader": ["business", "communication"],
                "narrower": [
                    "digital_marketing",
                    "content_marketing",
                    "social_media_marketing",
                ],
                "synonyms": ["promotion", "advertising", "branding"],
            },
        }

        # Stop words for concept extraction
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
            "is",
            "are",
            "was",
            "were",
        }

    async def initialize(self):
        """Initialize the enricher with knowledge bases and patterns"""
        try:
            # Compile regex patterns for better performance
            self.compiled_domain_patterns = {}
            for domain, info in self.domain_indicators.items():
                self.compiled_domain_patterns[domain] = [
                    re.compile(pattern, re.IGNORECASE)
                    for pattern in info.get("patterns", [])
                ]

            self.compiled_role_patterns = {}
            for role, patterns in self.semantic_roles.items():
                self.compiled_role_patterns[role] = [
                    re.compile(pattern, re.IGNORECASE) for pattern in patterns
                ]

            self.initialized = True
            logger.info("Semantic enricher initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize semantic enricher: {e}")
            self.initialized = False

    async def enrich(
        self, content: str, context: Optional[Dict[str, Any]] = None
    ) -> SemanticEnrichmentResult:
        """
        Enrich content with comprehensive semantic information

        Args:
            content: The content to enrich
            context: Additional context for enrichment

        Returns:
            SemanticEnrichmentResult with comprehensive semantic enrichment
        """
        if not self.initialized:
            await self.initialize()

        start_time = datetime.now()

        try:
            # Run enrichment tasks concurrently
            concepts_task = asyncio.create_task(self._extract_concepts(content))
            domain_task = asyncio.create_task(self._classify_domain(content))
            semantic_graph_task = asyncio.create_task(
                self._build_semantic_graph(content)
            )
            context_task = asyncio.create_task(self._analyze_context(content, context))
            enriched_text_task = asyncio.create_task(self._enhance_text(content))

            # Wait for all tasks to complete
            concepts = await concepts_task
            domain_classification = await domain_task
            semantic_graph = await semantic_graph_task
            context_insights = await context_task
            enriched_text = await enriched_text_task

            # Generate metadata
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            metadata = {
                "enrichment_timestamp": end_time.isoformat(),
                "processing_time_seconds": processing_time,
                "content_length": len(content),
                "concepts_extracted": len(concepts),
                "dominant_domain": (
                    max(domain_classification.items(), key=lambda x: x[1])[0]
                    if domain_classification
                    else "unknown"
                ),
                "enrichment_version": "1.0.0",
                "context_provided": context is not None,
            }

            # Compile statistics
            statistics = self._compile_statistics(
                content, concepts, domain_classification, semantic_graph
            )

            return SemanticEnrichmentResult(
                concepts=concepts,
                semantic_graph=semantic_graph,
                enriched_text=enriched_text,
                context_insights=context_insights,
                domain_classification=domain_classification,
                metadata=metadata,
                statistics=statistics,
            )

        except Exception as e:
            logger.error(f"Error during semantic enrichment: {e}")
            return SemanticEnrichmentResult(
                concepts=[],
                semantic_graph=SemanticGraph(),
                enriched_text=content,  # Return original content on failure
                metadata={
                    "error": str(e),
                    "enrichment_timestamp": datetime.now().isoformat(),
                    "status": "failed",
                },
            )

    async def enrich_entities(
        self, entities: List[Any], content: str = ""
    ) -> List[EntityEnrichment]:
        """
        Enrich entities with semantic information

        Args:
            entities: List of entities to enrich
            content: Original content for context

        Returns:
            List of EntityEnrichment objects
        """
        if not self.initialized:
            await self.initialize()

        enriched_entities = []

        for entity in entities:
            try:
                # Extract entity text (handle different entity formats)
                entity_text = getattr(entity, "text", str(entity))
                entity_type = getattr(entity, "entity_type", "UNKNOWN")

                # Determine canonical form
                canonical_form = self._get_canonical_form(entity_text, entity_type)

                # Extract semantic roles
                semantic_roles = self._extract_semantic_roles(entity_text, content)

                # Classify domain
                domain_category = self._classify_entity_domain(entity_text, entity_type)

                # Generate contextual meaning
                contextual_meaning = self._generate_contextual_meaning(
                    entity_text, content, entity_type
                )

                # Calculate confidence
                confidence = self._calculate_enrichment_confidence(
                    entity_text, entity_type, semantic_roles
                )

                # Generate knowledge links (simplified)
                knowledge_links = self._generate_knowledge_links(
                    entity_text, entity_type
                )

                enrichment = EntityEnrichment(
                    original_entity=entity_text,
                    enriched_type=self._enhance_entity_type(entity_type),
                    canonical_form=canonical_form,
                    semantic_roles=semantic_roles,
                    domain_category=domain_category,
                    contextual_meaning=contextual_meaning,
                    confidence=confidence,
                    knowledge_links=knowledge_links,
                )

                enriched_entities.append(enrichment)

            except Exception as e:
                logger.warning(f"Failed to enrich entity {entity}: {e}")
                # Create basic enrichment for failed entities
                entity_text = str(entity)
                enriched_entities.append(
                    EntityEnrichment(
                        original_entity=entity_text,
                        enriched_type="UNKNOWN",
                        canonical_form=entity_text,
                        confidence=0.1,
                    )
                )

        return enriched_entities

    async def _extract_concepts(self, content: str) -> List[SemanticConcept]:
        """Extract semantic concepts from content"""
        concepts = []

        # Extract words and filter
        words = re.findall(r"\b[a-zA-Z]{3,}\b", content.lower())
        word_positions = {word: [] for word in set(words)}

        # Build position mapping
        for i, word in enumerate(words):
            word_positions[word].append(i)

        # Filter significant words
        significant_words = [
            word for word in words if word not in self.stop_words and len(word) > 3
        ]

        # Count frequencies
        word_freq = Counter(significant_words)

        # Extract concepts from frequent words
        for word, frequency in word_freq.most_common(20):
            if frequency >= 2:  # Only concepts that appear multiple times
                concept_info = self.concept_hierarchies.get(word, {})

                concept = SemanticConcept(
                    concept=word,
                    confidence=min(1.0, frequency / len(significant_words) * 10),
                    category=self._determine_concept_category(word),
                    related_concepts=concept_info.get("narrower", [])[:5],
                    synonyms=concept_info.get("synonyms", []),
                    broader_concepts=concept_info.get("broader", []),
                    narrower_concepts=concept_info.get("narrower", [])[:3],
                    frequency=frequency,
                    positions=word_positions.get(word, [])[:10],  # Limit positions
                    context_score=self._calculate_context_score(word, content),
                )
                concepts.append(concept)

        # Extract compound concepts (noun phrases)
        compound_concepts = await self._extract_compound_concepts(content)
        concepts.extend(compound_concepts)

        # Sort by confidence and return top concepts
        concepts.sort(key=lambda x: x.confidence, reverse=True)
        return concepts[:15]  # Return top 15 concepts

    async def _classify_domain(self, content: str) -> Dict[str, float]:
        """Classify content into domain categories"""
        domain_scores = {}
        content_lower = content.lower()

        for domain, indicators in self.domain_indicators.items():
            score = 0.0

            # Check keyword indicators
            keywords = indicators.get("keywords", [])
            keyword_matches = sum(1 for keyword in keywords if keyword in content_lower)

            if keywords:
                keyword_score = keyword_matches / len(keywords)
                score += keyword_score * 0.7  # 70% weight for keywords

            # Check pattern indicators
            patterns = self.compiled_domain_patterns.get(domain, [])
            pattern_matches = sum(len(pattern.findall(content)) for pattern in patterns)

            if patterns:
                pattern_score = min(1.0, pattern_matches / len(patterns))
                score += pattern_score * 0.3  # 30% weight for patterns

            domain_scores[domain] = min(1.0, score)

        # Normalize scores
        total_score = sum(domain_scores.values())
        if total_score > 0:
            domain_scores = {k: v / total_score for k, v in domain_scores.items()}

        return domain_scores

    async def _build_semantic_graph(self, content: str) -> SemanticGraph:
        """Build semantic graph from content concepts"""
        # Extract entities and concepts for graph nodes
        words = re.findall(r"\b[a-zA-Z]{3,}\b", content.lower())
        significant_words = [
            word for word in words if word not in self.stop_words and len(word) > 3
        ]

        word_freq = Counter(significant_words)
        top_words = [word for word, freq in word_freq.most_common(10) if freq >= 2]

        # Create nodes
        nodes = []
        for word in top_words:
            nodes.append(
                {
                    "id": word,
                    "label": word,
                    "type": self._determine_concept_category(word),
                    "frequency": word_freq[word],
                    "size": min(100, word_freq[word] * 20),
                }
            )

        # Create edges based on co-occurrence
        edges = []
        edge_id = 0
        for i, word1 in enumerate(top_words):
            for word2 in top_words[i + 1 :]:
                # Simple co-occurrence within sentences
                cooccurrence = self._calculate_cooccurrence(word1, word2, content)
                if cooccurrence > 0.1:
                    edges.append(
                        {
                            "id": edge_id,
                            "source": word1,
                            "target": word2,
                            "weight": cooccurrence,
                            "type": "cooccurrence",
                        }
                    )
                    edge_id += 1

        # Simple clustering based on semantic similarity
        clusters = self._cluster_concepts(top_words)

        # Calculate centrality scores (simplified PageRank-like algorithm)
        centrality_scores = self._calculate_centrality_scores(nodes, edges)

        return SemanticGraph(
            nodes=nodes,
            edges=edges,
            clusters=clusters,
            centrality_scores=centrality_scores,
        )

    async def _analyze_context(
        self, content: str, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze contextual information"""
        insights = {
            "content_type": self._determine_content_type(content),
            "discourse_markers": self._extract_discourse_markers(content),
            "temporal_references": self._extract_temporal_references(content),
            "modal_expressions": self._extract_modal_expressions(content),
            "cohesion_score": self._calculate_cohesion_score(content),
        }

        if context:
            insights["external_context"] = {
                "context_keys": list(context.keys()),
                "context_influence": self._assess_context_influence(content, context),
            }

        return insights

    async def _enhance_text(self, content: str) -> str:
        """Enhance text with semantic annotations (simplified)"""
        # For now, return original content with minimal enhancement
        # In a full implementation, this would add semantic markup
        enhanced = content

        # Add simple concept highlighting markers (for demonstration)
        concepts = await self._extract_concepts(content)
        for concept in concepts[:5]:  # Only top 5 concepts
            if concept.confidence > 0.7:
                pattern = re.compile(
                    r"\b" + re.escape(concept.concept) + r"\b", re.IGNORECASE
                )
                enhanced = pattern.sub(
                    f"[CONCEPT:{concept.concept}:{concept.category}]\\g<0>[/CONCEPT]",
                    enhanced,
                    count=3,  # Limit replacements
                )

        return enhanced

    async def _extract_compound_concepts(self, content: str) -> List[SemanticConcept]:
        """Extract compound concepts (noun phrases)"""
        concepts = []

        # Simple noun phrase patterns
        noun_phrase_patterns = [
            r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",  # Proper noun phrases
            r"\b(?:machine|artificial|deep|natural|computer)\s+(?:learning|intelligence|network|language|science)\b",
            r"\b(?:data|information|knowledge|content)\s+(?:science|management|analysis|processing)\b",
        ]

        for pattern in noun_phrase_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if len(match.split()) >= 2:  # Multi-word concepts
                    concept = SemanticConcept(
                        concept=match.lower(),
                        confidence=0.8,  # Higher confidence for compound concepts
                        category=self._determine_concept_category(match.lower()),
                        frequency=len(
                            re.findall(re.escape(match), content, re.IGNORECASE)
                        ),
                        context_score=0.7,
                    )
                    concepts.append(concept)

        return concepts

    def _determine_concept_category(self, concept: str) -> str:
        """Determine the category of a concept"""
        concept_lower = concept.lower()

        # Check against domain keywords
        for domain, indicators in self.domain_indicators.items():
            if concept_lower in [kw.lower() for kw in indicators["keywords"]]:
                return domain

        # Check against known hierarchies
        if concept_lower in self.concept_hierarchies:
            # Try to infer category from broader concepts
            broader = self.concept_hierarchies[concept_lower].get("broader", [])
            for broad_concept in broader:
                if broad_concept in self.domain_indicators:
                    return broad_concept

        return "general"

    def _calculate_context_score(self, concept: str, content: str) -> float:
        """Calculate how well a concept fits the context"""
        concept_positions = []
        words = content.lower().split()

        for i, word in enumerate(words):
            if concept in word:
                concept_positions.append(i)

        if not concept_positions:
            return 0.0

        # Higher score for concepts that appear in important positions
        # (beginning, end, near other important concepts)
        score = 0.0
        total_words = len(words)

        for pos in concept_positions:
            # Position weight (higher for beginning and end)
            if pos < total_words * 0.1 or pos > total_words * 0.9:
                score += 0.3
            else:
                score += 0.1

        return min(1.0, score)

    def _extract_semantic_roles(self, entity_text: str, content: str) -> List[str]:
        """Extract semantic roles for an entity"""
        roles = []
        entity_lower = entity_text.lower()

        for role, patterns in self.compiled_role_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(content.lower())
                for match in matches:
                    if isinstance(match, tuple):
                        match = " ".join(match)
                    if entity_lower in match.lower():
                        roles.append(role)
                        break

        return list(set(roles))  # Remove duplicates

    def _get_canonical_form(self, entity_text: str, entity_type: str) -> str:
        """Get canonical form of entity"""
        # Simple canonicalization
        canonical = entity_text.strip().lower()

        # Remove common prefixes/suffixes for certain entity types
        if entity_type in ["ORGANIZATION", "COMPANY"]:
            canonical = re.sub(r"\b(?:inc|corp|ltd|llc|co)\b\.?", "", canonical).strip()
        elif entity_type == "PERSON":
            # Remove titles
            canonical = re.sub(
                r"\b(?:mr|mrs|ms|dr|prof|sir|madam)\.?\s+", "", canonical
            ).strip()

        return canonical or entity_text

    def _classify_entity_domain(self, entity_text: str, entity_type: str) -> str:
        """Classify entity into domain category"""
        entity_lower = entity_text.lower()

        # Check against domain keywords
        for domain, indicators in self.domain_indicators.items():
            keywords = [kw.lower() for kw in indicators["keywords"]]
            if any(keyword in entity_lower for keyword in keywords):
                return domain

        # Default classification based on entity type
        type_domain_mapping = {
            "ORGANIZATION": "business",
            "COMPANY": "business",
            "TECHNOLOGY": "technology",
            "PRODUCT": "business",
            "PERSON": "general",
            "LOCATION": "geographic",
        }

        return type_domain_mapping.get(entity_type, "general")

    def _generate_contextual_meaning(
        self, entity_text: str, content: str, entity_type: str
    ) -> str:
        """Generate contextual meaning for entity"""
        # Extract context around entity mentions
        entity_pattern = re.compile(re.escape(entity_text), re.IGNORECASE)
        contexts = []

        for match in entity_pattern.finditer(content):
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 50)
            context = content[start:end].strip()
            contexts.append(context)

        if not contexts:
            return f"A {entity_type.lower()} mentioned in the document"

        # Simple contextual meaning generation
        if len(contexts) == 1:
            return f"Referenced as: {contexts[0][:100]}..."
        else:
            return f"Multiple references found ({len(contexts)} instances)"

    def _calculate_enrichment_confidence(
        self, entity_text: str, entity_type: str, semantic_roles: List[str]
    ) -> float:
        """Calculate confidence score for entity enrichment"""
        confidence = 0.5  # Base confidence

        # Higher confidence for longer, more specific entities
        if len(entity_text) > 10:
            confidence += 0.2

        # Higher confidence for entities with clear semantic roles
        if semantic_roles:
            confidence += len(semantic_roles) * 0.1

        # Higher confidence for specific entity types
        if entity_type in ["PERSON", "ORGANIZATION", "EMAIL", "URL"]:
            confidence += 0.2

        return min(1.0, confidence)

    def _generate_knowledge_links(
        self, entity_text: str, entity_type: str
    ) -> List[str]:
        """Generate knowledge base links (simplified)"""
        links = []
        entity_lower = entity_text.lower().replace(" ", "_")

        # Generate potential knowledge base URLs (simplified)
        if entity_type == "PERSON":
            links.append(f"kb://person/{entity_lower}")
        elif entity_type in ["ORGANIZATION", "COMPANY"]:
            links.append(f"kb://organization/{entity_lower}")
        elif entity_type == "LOCATION":
            links.append(f"kb://location/{entity_lower}")

        # Add general concept link
        links.append(f"kb://concept/{entity_lower}")

        return links

    def _enhance_entity_type(self, entity_type: str) -> str:
        """Enhance entity type with more specific classification"""
        type_mapping = {
            "PERSON": "HUMAN_ENTITY",
            "ORGANIZATION": "BUSINESS_ENTITY",
            "LOCATION": "GEOGRAPHIC_ENTITY",
            "DATE": "TEMPORAL_ENTITY",
            "MONEY": "FINANCIAL_ENTITY",
            "PERCENTAGE": "QUANTITATIVE_ENTITY",
            "EMAIL": "DIGITAL_IDENTIFIER",
            "URL": "WEB_RESOURCE",
            "TECHNICAL_TERM": "DOMAIN_CONCEPT",
        }

        return type_mapping.get(entity_type, entity_type)

    def _calculate_cooccurrence(self, word1: str, word2: str, content: str) -> float:
        """Calculate co-occurrence score between two words"""
        sentences = re.split(r"[.!?]+", content)
        cooccurrence_count = 0
        total_sentences = len(sentences)

        for sentence in sentences:
            sentence_lower = sentence.lower()
            if word1 in sentence_lower and word2 in sentence_lower:
                cooccurrence_count += 1

        return cooccurrence_count / max(total_sentences, 1)

    def _cluster_concepts(self, concepts: List[str]) -> List[List[str]]:
        """Simple concept clustering based on semantic similarity"""
        clusters = []
        used_concepts = set()

        for concept in concepts:
            if concept in used_concepts:
                continue

            cluster = [concept]
            used_concepts.add(concept)

            # Find related concepts
            concept_info = self.concept_hierarchies.get(concept, {})
            related = concept_info.get("narrower", []) + concept_info.get("broader", [])

            for other_concept in concepts:
                if other_concept != concept and other_concept not in used_concepts:
                    if other_concept in related or self._are_concepts_related(
                        concept, other_concept
                    ):
                        cluster.append(other_concept)
                        used_concepts.add(other_concept)

            if len(cluster) >= 2:  # Only include clusters with multiple concepts
                clusters.append(cluster)

        return clusters

    def _are_concepts_related(self, concept1: str, concept2: str) -> bool:
        """Check if two concepts are semantically related"""
        # Simple relatedness check based on string similarity and domain
        category1 = self._determine_concept_category(concept1)
        category2 = self._determine_concept_category(concept2)

        # Same category concepts are related
        if category1 == category2 and category1 != "general":
            return True

        # Check for partial string matches (compound concepts)
        if concept1 in concept2 or concept2 in concept1:
            return True

        return False

    def _calculate_centrality_scores(
        self, nodes: List[Dict], edges: List[Dict]
    ) -> Dict[str, float]:
        """Calculate centrality scores for graph nodes"""
        centrality = {}

        # Simple degree centrality
        node_connections = defaultdict(int)
        for edge in edges:
            node_connections[edge["source"]] += 1
            node_connections[edge["target"]] += 1

        max_connections = max(node_connections.values()) if node_connections else 1

        for node in nodes:
            node_id = node["id"]
            centrality[node_id] = node_connections[node_id] / max_connections

        return centrality

    def _determine_content_type(self, content: str) -> str:
        """Determine the type of content"""
        content_lower = content.lower()

        if "abstract" in content_lower and "conclusion" in content_lower:
            return "academic_paper"
        elif "executive summary" in content_lower or "recommendation" in content_lower:
            return "business_report"
        elif "function" in content_lower and "return" in content_lower:
            return "technical_documentation"
        elif len(re.findall(r"\b\w+\?\b", content)) > 3:
            return "faq_content"
        else:
            return "general_text"

    def _extract_discourse_markers(self, content: str) -> List[str]:
        """Extract discourse markers from content"""
        discourse_patterns = [
            r"\b(?:however|therefore|moreover|furthermore|nevertheless|consequently)\b",
            r"\b(?:first|second|third|finally|in conclusion|in summary)\b",
            r"\b(?:on the other hand|in contrast|similarly|likewise)\b",
        ]

        markers = []
        for pattern in discourse_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            markers.extend(matches)

        return list(set([marker.lower() for marker in markers]))

    def _extract_temporal_references(self, content: str) -> List[str]:
        """Extract temporal references"""
        temporal_patterns = [
            r"\b(?:yesterday|today|tomorrow|now|currently|recently|previously)\b",
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b",
            r"\b\d{4}\b",  # Years
            r"\b(?:morning|afternoon|evening|night)\b",
        ]

        references = []
        for pattern in temporal_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            references.extend(matches)

        return list(set([ref.lower() for ref in references]))

    def _extract_modal_expressions(self, content: str) -> List[str]:
        """Extract modal expressions indicating certainty, possibility, etc."""
        modal_patterns = [
            r"\b(?:must|should|could|might|may|will|would|can)\b",
            r"\b(?:certainly|probably|possibly|definitely|likely|unlikely)\b",
            r"\b(?:seems?|appears?|suggests?|indicates?)\b",
        ]

        expressions = []
        for pattern in modal_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            expressions.extend(matches)

        return list(set([expr.lower() for expr in expressions]))

    def _calculate_cohesion_score(self, content: str) -> float:
        """Calculate text cohesion score"""
        sentences = re.split(r"[.!?]+", content)
        if len(sentences) < 2:
            return 1.0

        # Simple cohesion measure based on word overlap between adjacent sentences
        cohesion_scores = []

        for i in range(len(sentences) - 1):
            words1 = set(re.findall(r"\b\w+\b", sentences[i].lower()))
            words2 = set(re.findall(r"\b\w+\b", sentences[i + 1].lower()))

            if words1 and words2:
                overlap = len(words1.intersection(words2))
                union = len(words1.union(words2))
                cohesion_scores.append(overlap / union if union > 0 else 0)

        return sum(cohesion_scores) / len(cohesion_scores) if cohesion_scores else 0.0

    def _assess_context_influence(self, content: str, context: Dict[str, Any]) -> float:
        """Assess how much external context influences understanding"""
        # Simple heuristic: more context keys that relate to content = higher influence
        content_words = set(re.findall(r"\b\w+\b", content.lower()))
        context_words = set()

        for key, value in context.items():
            context_words.add(key.lower())
            if isinstance(value, str):
                context_words.update(re.findall(r"\b\w+\b", value.lower()))

        if not context_words:
            return 0.0

        overlap = len(content_words.intersection(context_words))
        return overlap / len(context_words)

    def _compile_statistics(
        self,
        content: str,
        concepts: List[SemanticConcept],
        domain_classification: Dict[str, float],
        semantic_graph: SemanticGraph,
    ) -> Dict[str, Any]:
        """Compile enrichment statistics"""
        return {
            "concept_analysis": {
                "total_concepts": len(concepts),
                "high_confidence_concepts": len(
                    [c for c in concepts if c.confidence > 0.7]
                ),
                "most_confident_concept": concepts[0].concept if concepts else None,
                "average_confidence": (
                    sum(c.confidence for c in concepts) / len(concepts)
                    if concepts
                    else 0.0
                ),
            },
            "domain_analysis": {
                "dominant_domain": (
                    max(domain_classification.items(), key=lambda x: x[1])[0]
                    if domain_classification
                    else "unknown"
                ),
                "domain_confidence": (
                    max(domain_classification.values())
                    if domain_classification
                    else 0.0
                ),
                "multi_domain": len(
                    [score for score in domain_classification.values() if score > 0.3]
                )
                > 1,
            },
            "graph_analysis": {
                "total_nodes": len(semantic_graph.nodes),
                "total_edges": len(semantic_graph.edges),
                "total_clusters": len(semantic_graph.clusters),
                "most_central_concept": (
                    max(semantic_graph.centrality_scores.items(), key=lambda x: x[1])[0]
                    if semantic_graph.centrality_scores
                    else None
                ),
            },
            "enrichment_summary": {
                "content_length": len(content),
                "enrichment_density": (
                    len(concepts) / len(content.split()) if content.split() else 0.0
                ),
                "semantic_richness": min(
                    1.0, len(concepts) * len(semantic_graph.edges) / 100
                ),
            },
        }
