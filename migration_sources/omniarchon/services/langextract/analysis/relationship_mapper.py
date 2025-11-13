"""
Relationship Mapper - Advanced Implementation

This module provides comprehensive relationship mapping capabilities for the LangExtract service,
including entity relationship detection, graph construction, semantic relationship analysis,
and knowledge graph integration.
"""

import asyncio
import logging
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Entity(BaseModel):
    """An entity in the relationship graph with comprehensive metadata"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    entity_type: str = "unknown"
    canonical_name: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    properties: Dict[str, Any] = Field(default_factory=dict)
    positions: List[int] = Field(default_factory=list)
    context_snippets: List[str] = Field(default_factory=list)
    domain_category: str = "general"


class Relationship(BaseModel):
    """A relationship between entities with detailed metadata"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    target: str
    relationship_type: str = "unknown"
    relationship_subtype: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    weight: float = Field(ge=0.0, le=1.0, default=1.0)
    evidence: List[str] = Field(default_factory=list)
    context: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)
    bidirectional: bool = False
    temporal_indicator: Optional[str] = None


class GraphMetrics(BaseModel):
    """Metrics about the relationship graph"""

    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0
    average_degree: float = 0.0
    clustering_coefficient: float = 0.0
    connected_components: int = 0
    centrality_scores: Dict[str, float] = Field(default_factory=dict)


class RelationshipMappingResult(BaseModel):
    """Comprehensive result model for relationship mapping"""

    entities: List[Entity] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    graph_metrics: GraphMetrics = Field(default_factory=GraphMetrics)
    relationship_types: Dict[str, int] = Field(default_factory=dict)
    entity_types: Dict[str, int] = Field(default_factory=dict)
    graph_data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    mapping_type: str = "relationship"
    statistics: Dict[str, Any] = Field(default_factory=dict)


class RelationshipMapper:
    """
    Advanced relationship mapper for identifying and mapping relationships
    between entities, concepts, and other semantic elements with graph construction
    and analysis capabilities.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the relationship mapper"""
        self.config = config or {}
        self.initialized = False

        # Relationship patterns with confidence weights
        self.relationship_patterns = {
            "OWNERSHIP": {
                "patterns": [
                    r"(\w+(?:\s+\w+)*)\s+(?:owns?|possesses?|has\s+ownership\s+of)\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+belongs?\s+to\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+is\s+(?:owned\s+by|possessed\s+by)\s+(\w+(?:\s+\w+)*)",
                ],
                "weight": 0.9,
                "bidirectional": False,
            },
            "EMPLOYMENT": {
                "patterns": [
                    r"(\w+(?:\s+\w+)*)\s+(?:works?\s+(?:for|at)|is\s+employed\s+by)\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+is\s+(?:a|an)\s+(\w+(?:\s+\w+)*)\s+at\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+(?:manages?|leads?|supervises?)\s+(\w+(?:\s+\w+)*)",
                ],
                "weight": 0.8,
                "bidirectional": False,
            },
            "LOCATION": {
                "patterns": [
                    r"(\w+(?:\s+\w+)*)\s+(?:is\s+(?:located\s+)?in|is\s+at|is\s+based\s+in)\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+(?:lives?\s+in|resides?\s+in|operates?\s+in)\s+(\w+(?:\s+\w+)*)",
                    r"(?:at|in)\s+(\w+(?:\s+\w+)*),\s+(\w+(?:\s+\w+)*)",
                ],
                "weight": 0.7,
                "bidirectional": False,
            },
            "COLLABORATION": {
                "patterns": [
                    r"(\w+(?:\s+\w+)*)\s+(?:collaborates?\s+with|partners?\s+with|works?\s+with)\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+and\s+(\w+(?:\s+\w+)*)\s+(?:work\s+together|collaborate|partner)",
                    r"(?:joint\s+venture|partnership|collaboration)\s+between\s+(\w+(?:\s+\w+)*)\s+and\s+(\w+(?:\s+\w+)*)",
                ],
                "weight": 0.8,
                "bidirectional": True,
            },
            "DEPENDENCY": {
                "patterns": [
                    r"(\w+(?:\s+\w+)*)\s+(?:depends?\s+on|relies?\s+on|requires?)\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+(?:needs?|uses?|utilizes?)\s+(\w+(?:\s+\w+)*)",
                    r"without\s+(\w+(?:\s+\w+)*),\s+(\w+(?:\s+\w+)*)\s+(?:cannot|would\s+not)",
                ],
                "weight": 0.6,
                "bidirectional": False,
            },
            "CAUSE_EFFECT": {
                "patterns": [
                    r"(\w+(?:\s+\w+)*)\s+(?:causes?|leads?\s+to|results?\s+in)\s+(\w+(?:\s+\w+)*)",
                    r"(?:because\s+of|due\s+to)\s+(\w+(?:\s+\w+)*),\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+(?:triggers?|initiates?|brings?\s+about)\s+(\w+(?:\s+\w+)*)",
                ],
                "weight": 0.7,
                "bidirectional": False,
            },
            "SIMILARITY": {
                "patterns": [
                    r"(\w+(?:\s+\w+)*)\s+(?:is\s+)?(?:like|similar\s+to|resembles?)\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+and\s+(\w+(?:\s+\w+)*)\s+are\s+(?:similar|alike|comparable)",
                    r"both\s+(\w+(?:\s+\w+)*)\s+and\s+(\w+(?:\s+\w+)*)",
                ],
                "weight": 0.5,
                "bidirectional": True,
            },
            "OPPOSITION": {
                "patterns": [
                    r"(\w+(?:\s+\w+)*)\s+(?:opposes?|conflicts?\s+with|disagrees?\s+with)\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+(?:versus|vs\.?|against)\s+(\w+(?:\s+\w+)*)",
                    r"conflict\s+between\s+(\w+(?:\s+\w+)*)\s+and\s+(\w+(?:\s+\w+)*)",
                ],
                "weight": 0.6,
                "bidirectional": True,
            },
            "HIERARCHY": {
                "patterns": [
                    r"(\w+(?:\s+\w+)*)\s+(?:reports?\s+to|is\s+under|is\s+subordinate\s+to)\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+is\s+(?:a\s+type\s+of|a\s+kind\s+of|part\s+of)\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+(?:includes?|contains?|comprises?)\s+(\w+(?:\s+\w+)*)",
                ],
                "weight": 0.7,
                "bidirectional": False,
            },
            "TEMPORAL": {
                "patterns": [
                    r"(\w+(?:\s+\w+)*)\s+(?:before|after|during|while)\s+(\w+(?:\s+\w+)*)",
                    r"(\w+(?:\s+\w+)*)\s+(?:then|next|subsequently)\s+(\w+(?:\s+\w+)*)",
                    r"(?:first|initially)\s+(\w+(?:\s+\w+)*),?\s+(?:then|later)\s+(\w+(?:\s+\w+)*)",
                ],
                "weight": 0.6,
                "bidirectional": False,
            },
        }

        # Entity type patterns for better recognition
        self.entity_type_patterns = {
            "PERSON": [
                r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sir|Madam)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*",
                r"\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
            ],
            "ORGANIZATION": [
                r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Inc|Corp|Ltd|LLC|Co|Company|Corporation|Group|Institute|University|College)\b",
                r"\b(?:The\s+)?[A-Z][A-Z\s&]+(?:Inc|Corp|Ltd|LLC|Co)\b",
            ],
            "LOCATION": [
                r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s+[A-Z]{2}\b",
                r"\b(?:New York|Los Angeles|Chicago|Houston|Phoenix|San Francisco|Boston|Seattle|Denver|Miami|Atlanta|Washington)\b",
            ],
            "PRODUCT": [
                r"\b[A-Z][a-z]+\s+(?:product|service|software|application|system|platform)\b",
                r"\b(?:software|app|system|platform|tool|service)\s+[A-Z][a-z]+\b",
            ],
            "CONCEPT": [
                r"\b[a-z]+\s+(?:concept|idea|theory|principle|methodology|approach)\b",
                r"\b(?:concept|theory|principle)\s+of\s+[a-z]+\b",
            ],
        }

        # Contextual indicators for relationship strength
        self.context_indicators = {
            "strong": ["explicitly", "clearly", "definitely", "certainly", "obviously"],
            "moderate": ["likely", "probably", "seems", "appears", "suggests"],
            "weak": ["possibly", "might", "could", "may", "perhaps"],
        }

    async def initialize(self):
        """Initialize the relationship mapper with compiled patterns"""
        try:
            # Compile regex patterns for better performance
            self.compiled_relationship_patterns = {}
            for rel_type, rel_info in self.relationship_patterns.items():
                self.compiled_relationship_patterns[rel_type] = {
                    "patterns": [
                        re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                        for pattern in rel_info["patterns"]
                    ],
                    "weight": rel_info["weight"],
                    "bidirectional": rel_info["bidirectional"],
                }

            self.compiled_entity_patterns = {}
            for entity_type, patterns in self.entity_type_patterns.items():
                self.compiled_entity_patterns[entity_type] = [
                    re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                    for pattern in patterns
                ]

            self.initialized = True
            logger.info("Relationship mapper initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize relationship mapper: {e}")
            self.initialized = False

    async def map_relationships(
        self,
        content: str,
        entities: Optional[List[Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> RelationshipMappingResult:
        """
        Map relationships in content with comprehensive analysis

        Args:
            content: The content to analyze for relationships
            entities: Pre-identified entities (optional)
            context: Additional context for relationship mapping

        Returns:
            RelationshipMappingResult with comprehensive relationship analysis
        """
        if not self.initialized:
            await self.initialize()

        start_time = datetime.now()

        try:
            # Run relationship mapping tasks concurrently
            entities_task = asyncio.create_task(
                self._extract_entities(content, entities)
            )
            relationships_task = asyncio.create_task(
                self._extract_relationships(content)
            )

            # Wait for entity and relationship extraction
            extracted_entities = await entities_task
            raw_relationships = await relationships_task

            # Build comprehensive relationship graph
            graph_task = asyncio.create_task(
                self._build_relationship_graph(extracted_entities, raw_relationships)
            )
            metrics_task = asyncio.create_task(
                self._calculate_graph_metrics(extracted_entities, raw_relationships)
            )

            # Wait for graph construction and metrics
            graph_data = await graph_task
            graph_metrics = await metrics_task

            # Compile relationship and entity type statistics
            relationship_types = Counter(
                rel.relationship_type for rel in raw_relationships
            )
            entity_types = Counter(entity.entity_type for entity in extracted_entities)

            # Generate metadata
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            metadata = {
                "mapping_timestamp": end_time.isoformat(),
                "processing_time_seconds": processing_time,
                "content_length": len(content),
                "entities_found": len(extracted_entities),
                "relationships_found": len(raw_relationships),
                "relationship_types_found": len(relationship_types),
                "entity_types_found": len(entity_types),
                "mapping_version": "1.0.0",
                "context_provided": context is not None,
            }

            # Compile comprehensive statistics
            statistics = self._compile_statistics(
                content, extracted_entities, raw_relationships, graph_metrics
            )

            return RelationshipMappingResult(
                entities=extracted_entities,
                relationships=raw_relationships,
                graph_metrics=graph_metrics,
                relationship_types=dict(relationship_types),
                entity_types=dict(entity_types),
                graph_data=graph_data,
                metadata=metadata,
                statistics=statistics,
            )

        except Exception as e:
            logger.error(f"Error during relationship mapping: {e}")
            return RelationshipMappingResult(
                entities=[],
                relationships=[],
                graph_metrics=GraphMetrics(),
                metadata={
                    "error": str(e),
                    "mapping_timestamp": datetime.now().isoformat(),
                    "status": "failed",
                },
            )

    async def _extract_entities(
        self, content: str, provided_entities: Optional[List[Any]] = None
    ) -> List[Entity]:
        """Extract entities from content or use provided entities"""
        entities = []
        entity_names = set()

        # Use provided entities if available
        if provided_entities:
            for entity in provided_entities:
                entity_text = getattr(entity, "text", str(entity))
                entity_type = getattr(entity, "entity_type", "UNKNOWN")

                if entity_text.lower() not in entity_names:
                    entities.append(
                        Entity(
                            name=entity_text,
                            entity_type=entity_type,
                            canonical_name=self._canonicalize_entity_name(entity_text),
                            confidence=getattr(entity, "confidence_score", 0.8),
                            positions=self._find_entity_positions(entity_text, content),
                            context_snippets=self._extract_context_snippets(
                                entity_text, content
                            ),
                            domain_category=self._classify_entity_domain(
                                entity_text, entity_type
                            ),
                            properties={
                                "source": "provided",
                                "original_entity": entity,
                            },
                        )
                    )
                    entity_names.add(entity_text.lower())

        # Extract additional entities using patterns
        for entity_type, patterns in self.compiled_entity_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(content):
                    entity_text = match.group().strip()
                    canonical_name = self._canonicalize_entity_name(entity_text)

                    if (
                        canonical_name.lower() not in entity_names
                        and len(entity_text) > 2
                    ):
                        entities.append(
                            Entity(
                                name=entity_text,
                                entity_type=entity_type,
                                canonical_name=canonical_name,
                                confidence=self._calculate_entity_confidence(
                                    entity_text, entity_type, content
                                ),
                                positions=self._find_entity_positions(
                                    entity_text, content
                                ),
                                context_snippets=self._extract_context_snippets(
                                    entity_text, content
                                ),
                                domain_category=self._classify_entity_domain(
                                    entity_text, entity_type
                                ),
                                properties={
                                    "source": "pattern_extraction",
                                    "pattern_type": entity_type,
                                },
                            )
                        )
                        entity_names.add(canonical_name.lower())

        # Sort by confidence and return top entities
        entities.sort(key=lambda x: x.confidence, reverse=True)
        return entities[:50]  # Limit to top 50 entities for performance

    async def _extract_relationships(self, content: str) -> List[Relationship]:
        """Extract relationships from content using patterns"""
        relationships = []

        for rel_type, rel_info in self.compiled_relationship_patterns.items():
            patterns = rel_info["patterns"]
            base_weight = rel_info["weight"]
            is_bidirectional = rel_info["bidirectional"]

            for pattern in patterns:
                for match in pattern.finditer(content):
                    groups = match.groups()
                    if len(groups) >= 2:
                        source = groups[0].strip()
                        target = groups[-1].strip()

                        # Skip if entities are too similar or too short
                        if (
                            len(source) < 3
                            or len(target) < 3
                            or source.lower() == target.lower()
                        ):
                            continue

                        # Extract context around the match
                        context_start = max(0, match.start() - 100)
                        context_end = min(len(content), match.end() + 100)
                        context = content[context_start:context_end].strip()

                        # Calculate confidence based on context
                        confidence = self._calculate_relationship_confidence(
                            source, target, rel_type, context, base_weight
                        )

                        # Extract evidence and temporal indicators
                        evidence = [match.group().strip()]
                        temporal_indicator = self._extract_temporal_indicator(context)

                        # Create primary relationship
                        relationship = Relationship(
                            source=self._canonicalize_entity_name(source),
                            target=self._canonicalize_entity_name(target),
                            relationship_type=rel_type,
                            confidence=confidence,
                            weight=base_weight,
                            evidence=evidence,
                            context=context[:200],  # Limit context length
                            bidirectional=is_bidirectional,
                            temporal_indicator=temporal_indicator,
                            properties={
                                "pattern_matched": match.group().strip(),
                                "source_position": match.start(),
                                "extraction_method": "pattern_matching",
                            },
                        )
                        relationships.append(relationship)

                        # Create reverse relationship if bidirectional
                        if is_bidirectional:
                            reverse_relationship = Relationship(
                                source=self._canonicalize_entity_name(target),
                                target=self._canonicalize_entity_name(source),
                                relationship_type=rel_type,
                                confidence=confidence
                                * 0.9,  # Slightly lower confidence for reverse
                                weight=base_weight,
                                evidence=evidence,
                                context=context[:200],
                                bidirectional=True,
                                temporal_indicator=temporal_indicator,
                                properties={
                                    "pattern_matched": match.group().strip(),
                                    "source_position": match.start(),
                                    "extraction_method": "reverse_bidirectional",
                                    "original_relationship_id": relationship.id,
                                },
                            )
                            relationships.append(reverse_relationship)

        # Remove duplicate relationships and sort by confidence
        relationships = self._deduplicate_relationships(relationships)
        relationships.sort(key=lambda x: x.confidence, reverse=True)

        return relationships[:100]  # Limit to top 100 relationships

    async def _build_relationship_graph(
        self, entities: List[Entity], relationships: List[Relationship]
    ) -> Dict[str, Any]:
        """Build comprehensive graph data structure"""
        # Create entity lookup
        entity_lookup = {entity.canonical_name: entity for entity in entities}

        # Build adjacency lists
        adjacency_list = defaultdict(list)
        edge_weights = {}

        # Process relationships
        valid_relationships = []
        for rel in relationships:
            # Only include relationships between known entities
            if rel.source in entity_lookup and rel.target in entity_lookup:
                valid_relationships.append(rel)
                adjacency_list[rel.source].append(rel.target)
                edge_weights[(rel.source, rel.target)] = rel.weight

        # Create graph structure
        nodes = [
            {
                "id": entity.canonical_name,
                "name": entity.name,
                "type": entity.entity_type,
                "confidence": entity.confidence,
                "domain": entity.domain_category,
                "size": min(100, len(entity.context_snippets) * 10 + 20),
                "properties": entity.properties,
            }
            for entity in entities
            if entity.canonical_name in adjacency_list
            or any(rel.target == entity.canonical_name for rel in valid_relationships)
        ]

        edges = [
            {
                "id": rel.id,
                "source": rel.source,
                "target": rel.target,
                "type": rel.relationship_type,
                "weight": rel.weight,
                "confidence": rel.confidence,
                "bidirectional": rel.bidirectional,
                "properties": {
                    "evidence": rel.evidence[:3],  # Limit evidence
                    "context": rel.context[:100],
                    "temporal": rel.temporal_indicator,
                },
            }
            for rel in valid_relationships
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "adjacency_list": dict(adjacency_list),
            "edge_weights": edge_weights,
            "graph_type": "directed",
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    async def _calculate_graph_metrics(
        self, entities: List[Entity], relationships: List[Relationship]
    ) -> GraphMetrics:
        """Calculate comprehensive graph metrics"""
        node_count = len(entities)
        edge_count = len(relationships)

        if node_count == 0:
            return GraphMetrics()

        # Calculate density
        max_edges = node_count * (node_count - 1)
        density = edge_count / max_edges if max_edges > 0 else 0.0

        # Calculate average degree
        degree_sum = defaultdict(int)
        for rel in relationships:
            degree_sum[rel.source] += 1
            degree_sum[rel.target] += 1

        average_degree = (
            sum(degree_sum.values()) / node_count if node_count > 0 else 0.0
        )

        # Simple clustering coefficient approximation
        clustering_coefficient = self._approximate_clustering_coefficient(
            entities, relationships
        )

        # Count connected components (simplified)
        connected_components = self._count_connected_components(entities, relationships)

        # Calculate centrality scores
        centrality_scores = self._calculate_centrality_scores(entities, relationships)

        return GraphMetrics(
            node_count=node_count,
            edge_count=edge_count,
            density=density,
            average_degree=average_degree,
            clustering_coefficient=clustering_coefficient,
            connected_components=connected_components,
            centrality_scores=centrality_scores,
        )

    def _canonicalize_entity_name(self, entity_text: str) -> str:
        """Canonicalize entity name for consistent matching"""
        # Remove extra whitespace and normalize case
        canonical = re.sub(r"\s+", " ", entity_text.strip())

        # Remove common prefixes/suffixes
        canonical = re.sub(r"\b(?:the|a|an)\s+", "", canonical, flags=re.IGNORECASE)
        canonical = re.sub(
            r"\s+(?:inc|corp|ltd|llc|co)\.?$", "", canonical, flags=re.IGNORECASE
        )
        canonical = re.sub(
            r"^\s*(?:mr|mrs|ms|dr|prof)\.?\s+", "", canonical, flags=re.IGNORECASE
        )

        return canonical.strip()

    def _find_entity_positions(self, entity_text: str, content: str) -> List[int]:
        """Find all positions of entity in content"""
        positions = []
        pattern = re.compile(re.escape(entity_text), re.IGNORECASE)

        for match in pattern.finditer(content):
            positions.append(match.start())

        return positions[:10]  # Limit to first 10 positions

    def _extract_context_snippets(self, entity_text: str, content: str) -> List[str]:
        """Extract context snippets around entity mentions"""
        snippets = []
        pattern = re.compile(re.escape(entity_text), re.IGNORECASE)

        for match in pattern.finditer(content):
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 50)
            snippet = content[start:end].strip()
            snippets.append(snippet)

        return snippets[:5]  # Limit to first 5 snippets

    def _classify_entity_domain(self, entity_text: str, entity_type: str) -> str:
        """Classify entity into domain category"""
        entity_lower = entity_text.lower()

        # Domain keywords
        domain_keywords = {
            "technology": [
                "software",
                "system",
                "platform",
                "application",
                "api",
                "database",
            ],
            "business": ["company", "corporation", "organization", "market", "revenue"],
            "academic": ["university", "college", "professor", "research", "study"],
            "medical": ["hospital", "doctor", "patient", "treatment", "diagnosis"],
            "legal": ["court", "judge", "attorney", "law", "legal"],
        }

        for domain, keywords in domain_keywords.items():
            if any(keyword in entity_lower for keyword in keywords):
                return domain

        # Default classification based on entity type
        type_mapping = {
            "ORGANIZATION": "business",
            "PERSON": "general",
            "LOCATION": "geographic",
            "PRODUCT": "technology",
        }

        return type_mapping.get(entity_type, "general")

    def _calculate_entity_confidence(
        self, entity_text: str, entity_type: str, content: str
    ) -> float:
        """Calculate confidence score for entity recognition"""
        confidence = 0.6  # Base confidence

        # Length bonus
        if len(entity_text) > 10:
            confidence += 0.1

        # Frequency bonus
        frequency = len(re.findall(re.escape(entity_text), content, re.IGNORECASE))
        if frequency > 1:
            confidence += min(0.2, frequency * 0.05)

        # Type-specific bonuses
        if entity_type in ["PERSON", "ORGANIZATION"]:
            confidence += 0.1

        return min(1.0, confidence)

    def _calculate_relationship_confidence(
        self, source: str, target: str, rel_type: str, context: str, base_weight: float
    ) -> float:
        """Calculate confidence score for relationship"""
        confidence = base_weight * 0.7  # Start with pattern weight

        # Context strength indicators
        context_lower = context.lower()

        if any(
            indicator in context_lower
            for indicator in self.context_indicators["strong"]
        ):
            confidence += 0.2
        elif any(
            indicator in context_lower
            for indicator in self.context_indicators["moderate"]
        ):
            confidence += 0.1
        elif any(
            indicator in context_lower for indicator in self.context_indicators["weak"]
        ):
            confidence -= 0.1

        # Entity specificity bonus
        if len(source) > 5 and len(target) > 5:
            confidence += 0.1

        # Distance penalty (entities far apart are less likely to be related)
        source_pos = context_lower.find(source.lower())
        target_pos = context_lower.find(target.lower())
        if source_pos >= 0 and target_pos >= 0:
            distance = abs(source_pos - target_pos)
            if distance > 100:
                confidence -= 0.1

        return max(0.1, min(1.0, confidence))

    def _extract_temporal_indicator(self, context: str) -> Optional[str]:
        """Extract temporal indicators from context"""
        temporal_patterns = [
            r"\b(?:before|after|during|while|when|since|until)\b",
            r"\b(?:yesterday|today|tomorrow|now|currently|recently|previously)\b",
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b",
            r"\b\d{4}\b",  # Years
        ]

        for pattern in temporal_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                return match.group().lower()

        return None

    def _deduplicate_relationships(
        self, relationships: List[Relationship]
    ) -> List[Relationship]:
        """Remove duplicate relationships"""
        seen = set()
        unique_relationships = []

        for rel in relationships:
            # Create key for deduplication
            key = (rel.source.lower(), rel.target.lower(), rel.relationship_type)

            if key not in seen:
                seen.add(key)
                unique_relationships.append(rel)
            else:
                # If duplicate, keep the one with higher confidence
                existing_rel = next(
                    r
                    for r in unique_relationships
                    if (r.source.lower(), r.target.lower(), r.relationship_type) == key
                )
                if rel.confidence > existing_rel.confidence:
                    unique_relationships.remove(existing_rel)
                    unique_relationships.append(rel)

        return unique_relationships

    def _approximate_clustering_coefficient(
        self, entities: List[Entity], relationships: List[Relationship]
    ) -> float:
        """Approximate clustering coefficient calculation"""
        # Build adjacency for clustering calculation
        adjacency = defaultdict(set)
        for rel in relationships:
            adjacency[rel.source].add(rel.target)
            if rel.bidirectional:
                adjacency[rel.target].add(rel.source)

        clustering_scores = []
        for entity in entities:
            neighbors = adjacency[entity.canonical_name]
            if len(neighbors) < 2:
                continue

            # Count connections between neighbors
            connections = 0
            total_possible = len(neighbors) * (len(neighbors) - 1) / 2

            for neighbor1 in neighbors:
                for neighbor2 in neighbors:
                    if neighbor1 != neighbor2 and neighbor2 in adjacency[neighbor1]:
                        connections += 1

            if total_possible > 0:
                clustering_scores.append(connections / (2 * total_possible))

        return (
            sum(clustering_scores) / len(clustering_scores)
            if clustering_scores
            else 0.0
        )

    def _count_connected_components(
        self, entities: List[Entity], relationships: List[Relationship]
    ) -> int:
        """Count connected components in the graph"""
        # Build adjacency list
        adjacency = defaultdict(set)
        all_nodes = set(entity.canonical_name for entity in entities)

        for rel in relationships:
            adjacency[rel.source].add(rel.target)
            adjacency[rel.target].add(rel.source)  # Treat as undirected for components

        visited = set()
        components = 0

        def dfs(node):
            visited.add(node)
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    dfs(neighbor)

        for node in all_nodes:
            if node not in visited:
                dfs(node)
                components += 1

        return components

    def _calculate_centrality_scores(
        self, entities: List[Entity], relationships: List[Relationship]
    ) -> Dict[str, float]:
        """Calculate centrality scores for entities"""
        # Simple degree centrality
        degree_counts = defaultdict(int)

        for rel in relationships:
            degree_counts[rel.source] += 1
            degree_counts[rel.target] += 1

        max_degree = max(degree_counts.values()) if degree_counts else 1

        centrality_scores = {}
        for entity in entities:
            centrality_scores[entity.canonical_name] = (
                degree_counts[entity.canonical_name] / max_degree
            )

        return centrality_scores

    def _compile_statistics(
        self,
        content: str,
        entities: List[Entity],
        relationships: List[Relationship],
        graph_metrics: GraphMetrics,
    ) -> Dict[str, Any]:
        """Compile comprehensive relationship mapping statistics"""
        # Entity statistics
        entity_confidence_scores = [entity.confidence for entity in entities]
        avg_entity_confidence = (
            sum(entity_confidence_scores) / len(entity_confidence_scores)
            if entity_confidence_scores
            else 0.0
        )

        # Relationship statistics
        relationship_confidence_scores = [rel.confidence for rel in relationships]
        avg_relationship_confidence = (
            sum(relationship_confidence_scores) / len(relationship_confidence_scores)
            if relationship_confidence_scores
            else 0.0
        )

        # Relationship type distribution
        rel_type_counts = Counter(rel.relationship_type for rel in relationships)

        # Entity type distribution
        entity_type_counts = Counter(entity.entity_type for entity in entities)

        return {
            "entity_analysis": {
                "total_entities": len(entities),
                "average_confidence": round(avg_entity_confidence, 3),
                "entity_types": dict(entity_type_counts),
                "most_common_entity_type": (
                    entity_type_counts.most_common(1)[0][0]
                    if entity_type_counts
                    else None
                ),
            },
            "relationship_analysis": {
                "total_relationships": len(relationships),
                "average_confidence": round(avg_relationship_confidence, 3),
                "relationship_types": dict(rel_type_counts),
                "most_common_relationship": (
                    rel_type_counts.most_common(1)[0][0] if rel_type_counts else None
                ),
                "bidirectional_relationships": len(
                    [r for r in relationships if r.bidirectional]
                ),
            },
            "graph_analysis": {
                "graph_density": round(graph_metrics.density, 3),
                "average_degree": round(graph_metrics.average_degree, 1),
                "clustering_coefficient": round(
                    graph_metrics.clustering_coefficient, 3
                ),
                "connected_components": graph_metrics.connected_components,
                "most_central_entity": (
                    max(graph_metrics.centrality_scores.items(), key=lambda x: x[1])[0]
                    if graph_metrics.centrality_scores
                    else None
                ),
            },
            "content_analysis": {
                "content_length": len(content),
                "entity_density": (
                    len(entities) / len(content.split()) if content.split() else 0.0
                ),
                "relationship_density": (
                    len(relationships) / len(content.split())
                    if content.split()
                    else 0.0
                ),
                "entities_per_relationship": (
                    len(entities) / len(relationships) if relationships else 0.0
                ),
            },
            "quality_metrics": {
                "high_confidence_entities": len(
                    [e for e in entities if e.confidence > 0.7]
                ),
                "high_confidence_relationships": len(
                    [r for r in relationships if r.confidence > 0.7]
                ),
                "entity_coverage": (
                    len(
                        set(r.source for r in relationships)
                        | set(r.target for r in relationships)
                    )
                    / len(entities)
                    if entities
                    else 0.0
                ),
                "relationship_complexity": (
                    "high"
                    if len(rel_type_counts) > 5
                    else "medium" if len(rel_type_counts) > 2 else "low"
                ),
            },
        }
