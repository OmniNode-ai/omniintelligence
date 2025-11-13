"""
Bridge Intelligence Generator Service

Orchestrates intelligence gathering from multiple Archon sources to generate
OmniNode Tool Metadata Standard v0.1 compliant metadata enriched with:
- LangExtract semantic analysis
- QualityScorer ONEX compliance assessment
- Pattern tracking data from database

Performance targets:
- Complete generation: <2000ms
- LangExtract semantic analysis: <500ms
- Quality scoring: <200ms
- Pattern queries: <500ms
"""

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple
from uuid import UUID, uuid4

if TYPE_CHECKING:
    import asyncpg

# Import intelligence components
from scoring.quality_scorer import QualityScorer

# Import API models
from src.api.bridge.models import (
    BridgeIntelligenceRequest,
    BridgeIntelligenceResponse,
    OmniNodeMetadataClassification,
    OmniNodeToolMetadata,
    PatternIntelligence,
    QualityMetrics,
    SemanticIntelligence,
)
from src.archon_services.pattern_learning.phase2_matching.client_langextract_http import (
    ClientLangextractHttp,
)
from src.archon_services.pattern_learning.phase2_matching.model_semantic_analysis import (
    SemanticAnalysisResult,
)
from src.models.entity_models import EntityMetadata, EntityType, KnowledgeEntity

logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class BridgeIntelligenceGenerator:
    """
    Orchestrates intelligence gathering from Archon services to generate
    OmniNode protocol-compliant metadata.

    Integrates:
    1. LangExtract HTTP Client - Semantic analysis
    2. QualityScorer - ONEX compliance and quality assessment
    3. Pattern Tracking Database - Usage analytics and pattern intelligence
    """

    def __init__(
        self,
        langextract_url: Optional[str] = None,
        db_pool: Optional["asyncpg.Pool[asyncpg.Record]"] = None,
    ):
        """
        Initialize Bridge Intelligence Generator.

        Args:
            langextract_url: LangExtract service URL (defaults to env or http://archon-langextract:8156)
            db_pool: Database connection pool for pattern queries (optional)
        """
        # Initialize LangExtract client
        self.langextract_url = langextract_url or os.getenv(
            "LANGEXTRACT_URL", "http://archon-langextract:8156"
        )
        self.langextract_client = ClientLangextractHttp(base_url=self.langextract_url)
        self._langextract_connected = False

        # Initialize QualityScorer
        self.quality_scorer = QualityScorer()

        # Database pool for pattern queries
        self.db_pool = db_pool

        logger.info(
            f"BridgeIntelligenceGenerator initialized with LangExtract at {self.langextract_url}"
        )

    async def initialize(self) -> None:
        """
        Initialize async resources (must be called after __init__).

        Connects the LangExtract HTTP client and starts health checks.
        """
        if not self._langextract_connected:
            await self.langextract_client.connect()
            self._langextract_connected = True
            logger.info("LangExtract client connected successfully")

    async def shutdown(self) -> None:
        """
        Cleanup async resources.

        Closes the LangExtract HTTP client and stops health checks.
        """
        if self._langextract_connected:
            await self.langextract_client.close()
            self._langextract_connected = False
            logger.info("LangExtract client closed successfully")

    async def generate_intelligence(
        self, request: BridgeIntelligenceRequest
    ) -> BridgeIntelligenceResponse:
        """
        Generate OmniNode protocol-compliant metadata enriched with Archon intelligence.

        Args:
            request: Bridge intelligence generation request

        Returns:
            BridgeIntelligenceResponse with protocol-compliant metadata

        Performance: <2000ms target for complete generation
        """
        start_time = time.time()
        intelligence_sources = []
        recommendations = []

        try:
            # Step 1: Get or read file content
            content, file_size = await self._get_file_content(
                request.file_path, request.content
            )

            if content is None:
                return BridgeIntelligenceResponse(
                    success=False,
                    processing_metadata={
                        "processing_time_ms": (time.time() - start_time) * 1000,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    intelligence_sources=[],
                    error=f"Could not read file content: {request.file_path}",
                )

            # Step 2: Extract file metadata
            file_name = Path(request.file_path).stem
            language = self._detect_language(request.file_path)

            # Step 3: Gather intelligence from multiple sources in parallel
            semantic_result = None
            quality_result = None
            pattern_result = None

            # LangExtract semantic analysis (if requested)
            if request.include_semantic:
                try:
                    semantic_result = await self._get_semantic_intelligence(
                        content, request.min_confidence
                    )
                    intelligence_sources.append("langextract")
                except Exception as e:
                    logger.warning(f"LangExtract analysis failed: {e}")
                    # Continue without semantic intelligence

            # Quality scoring with ONEX compliance (if requested)
            if request.include_compliance:
                try:
                    quality_result = await self._get_quality_intelligence(
                        content, request.file_path, language
                    )
                    intelligence_sources.append("quality_scorer")

                    # Extract recommendations from quality assessment
                    if quality_result:
                        recommendations.extend(
                            self._generate_recommendations(quality_result)
                        )
                except Exception as e:
                    logger.warning(f"Quality scoring failed: {e}")
                    # Continue without quality intelligence

            # Pattern tracking intelligence (if requested and DB available)
            if request.include_patterns and self.db_pool:
                try:
                    pattern_result = await self._get_pattern_intelligence(
                        request.file_path
                    )
                    intelligence_sources.append("pattern_tracking")
                except Exception as e:
                    logger.warning(f"Pattern tracking query failed: {e}")
                    # Continue without pattern intelligence

            # Step 4: Build OmniNode protocol-compliant metadata
            metadata = self._build_omninode_metadata(
                file_name=file_name,
                file_path=request.file_path,
                language=language,
                semantic_result=semantic_result,
                quality_result=quality_result,
                pattern_result=pattern_result,
            )

            processing_time_ms = (time.time() - start_time) * 1000

            return BridgeIntelligenceResponse(
                success=True,
                metadata=metadata,
                processing_metadata={
                    "processing_time_ms": round(processing_time_ms, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "file_size_bytes": file_size,
                    "language": language,
                },
                intelligence_sources=intelligence_sources,
                recommendations=recommendations if recommendations else None,
            )

        except Exception as e:
            logger.error(f"Bridge intelligence generation failed: {e}", exc_info=True)
            processing_time_ms = (time.time() - start_time) * 1000

            return BridgeIntelligenceResponse(
                success=False,
                processing_metadata={
                    "processing_time_ms": round(processing_time_ms, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                intelligence_sources=intelligence_sources,
                error=f"Intelligence generation failed: {str(e)}",
            )

    async def _get_file_content(
        self, file_path: str, provided_content: Optional[str]
    ) -> Tuple[Optional[str], int]:
        """Get file content either from provided content or by reading file"""
        if provided_content:
            return provided_content, len(provided_content.encode("utf-8"))

        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                content = path.read_text(encoding="utf-8")
                return content, path.stat().st_size
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")

        return None, 0

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension"""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
        }
        ext = Path(file_path).suffix.lower()
        return extension_map.get(ext, "python")

    async def _get_semantic_intelligence(
        self, content: str, min_confidence: float
    ) -> Optional[SemanticIntelligence]:
        """Get semantic analysis from LangExtract"""
        try:
            # Call LangExtract service
            result: SemanticAnalysisResult = (
                await self.langextract_client.analyze_semantic(
                    content=content,
                    context="code_analysis",
                    min_confidence=min_confidence,
                )
            )

            # Convert to SemanticIntelligence model
            return SemanticIntelligence(
                concepts=[
                    {
                        "concept": c.concept,
                        "score": c.score,
                        "context": c.context,
                    }
                    for c in result.concepts
                ],
                themes=[
                    {
                        "theme": t.theme,
                        "weight": t.weight,
                        "related_concepts": t.related_concepts,
                    }
                    for t in result.themes
                ],
                domains=[
                    {
                        "domain": d.domain,
                        "confidence": d.confidence,
                        "subdomain": d.subdomain,
                    }
                    for d in result.domains
                ],
                patterns=[
                    {
                        "pattern_type": p.pattern_type,
                        "description": p.description,
                        "strength": p.strength,
                        "indicators": p.indicators,
                    }
                    for p in result.patterns
                ],
                processing_time_ms=result.processing_time_ms,
            )

        except Exception as e:
            logger.error(f"LangExtract semantic analysis failed: {e}")
            return None

    async def _get_quality_intelligence(
        self, content: str, file_path: str, language: str
    ) -> Optional[QualityMetrics]:
        """Get quality and ONEX compliance assessment"""
        try:
            # Create entity for quality scoring
            entity = KnowledgeEntity(
                entity_id=f"file_{Path(file_path).stem}",
                name=Path(file_path).name,
                entity_type=EntityType.MODULE,
                description=f"{language.capitalize()} module for quality assessment",
                source_path=file_path,
                metadata=EntityMetadata(
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                properties={
                    "content": content,
                    "language": language,
                },
            )

            # Score the entity
            quality_score = self.quality_scorer.score_entity(entity, content)

            # Extract architectural compliance score
            arch_score, arch_reason = (
                self.quality_scorer._calculate_architectural_compliance(entity, content)
            )

            return QualityMetrics(
                quality_score=quality_score.overall_score,
                onex_compliance=arch_score,
                complexity_score=quality_score.complexity_score or 0.5,
                maintainability_score=quality_score.maintainability_score or 0.5,
                documentation_score=quality_score.documentation_score or 0.5,
                temporal_relevance=quality_score.temporal_relevance,
            )

        except Exception as e:
            logger.error(f"Quality intelligence generation failed: {e}")
            return None

    async def _get_pattern_intelligence(
        self, file_path: str
    ) -> Optional[PatternIntelligence]:
        """Query pattern tracking database for file-specific intelligence"""
        if not self.db_pool:
            return None

        try:
            async with self.db_pool.acquire() as conn:
                # Query patterns for this file
                query = """
                    SELECT
                        COUNT(*) as pattern_count,
                        AVG((pln.metadata->>'quality_score')::float) as avg_quality,
                        MAX(pln.created_at) as last_modified,
                        ARRAY_AGG(DISTINCT pln.pattern_type) as pattern_types
                    FROM pattern_lineage_nodes pln
                    WHERE pln.file_path = $1
                """
                result = await conn.fetchrow(query, file_path)

                if result and result["pattern_count"] > 0:
                    return PatternIntelligence(
                        pattern_count=result["pattern_count"],
                        total_executions=0,  # TODO: Add execution count query
                        avg_quality_score=result["avg_quality"],
                        last_modified=(
                            result["last_modified"].isoformat()
                            if result["last_modified"]
                            else None
                        ),
                        pattern_types=result["pattern_types"] or [],
                    )

        except Exception as e:
            logger.error(f"Pattern intelligence query failed: {e}")
            return None

        return None

    def _build_omninode_metadata(
        self,
        file_name: str,
        file_path: str,
        language: str,
        semantic_result: Optional[SemanticIntelligence],
        quality_result: Optional[QualityMetrics],
        pattern_result: Optional[PatternIntelligence],
    ) -> OmniNodeToolMetadata:
        """
        Build OmniNode Tool Metadata Standard v0.1 compliant metadata structure.

        Enriches with Archon intelligence and converts quality scores to trust scores.
        """
        # Default quality metrics if not available
        if quality_result is None:
            quality_result = QualityMetrics(
                quality_score=0.5,
                onex_compliance=0.5,
                complexity_score=0.5,
                maintainability_score=0.5,
                documentation_score=0.5,
                temporal_relevance=0.5,
            )

        # Calculate trust_score (0-100) from quality_score (0-1)
        trust_score = int(quality_result.quality_score * 100)

        # Determine maturity level from quality and compliance scores
        maturity = self._determine_maturity(
            quality_result.quality_score, quality_result.onex_compliance
        )

        # Extract description from semantic intelligence if available
        description = None
        if semantic_result and semantic_result.themes:
            top_themes = sorted(
                semantic_result.themes,
                key=lambda t: t.get("weight", 0.0),
                reverse=True,
            )[:3]
            description = f"Component with themes: {', '.join(t.get('theme', 'unknown') for t in top_themes)}"

        # Extract tags from semantic intelligence
        tags = ["archon-intelligence"]
        if semantic_result:
            # Add domain tags
            for domain in semantic_result.domains[:3]:
                tags.append(domain.get("domain", "").replace("_", "-"))

        return OmniNodeToolMetadata(
            metadata_version="0.1",
            name=file_name,
            namespace="omninode.archon.intelligence",
            version="1.0.0",
            entrypoint=file_path,
            protocols_supported=["O.N.E. v0.1"],
            classification=OmniNodeMetadataClassification(
                maturity=maturity,
                trust_score=trust_score,
            ),
            quality_metrics=quality_result,
            semantic_intelligence=semantic_result,
            pattern_intelligence=pattern_result,
            title=f"{file_name} (Archon Intelligence)",
            description=description,
            type="component",
            language=language,
            tags=tags,
            author="Archon Intelligence",
        )

    def _determine_maturity(self, quality_score: float, onex_compliance: float) -> str:
        """
        Determine maturity level from quality and compliance scores.

        Maturity levels:
        - production: quality >= 0.9 and onex_compliance >= 0.9
        - stable: quality >= 0.8 and onex_compliance >= 0.8
        - beta: quality >= 0.6 and onex_compliance >= 0.6
        - alpha: anything below beta threshold
        """
        combined_score = (quality_score + onex_compliance) / 2

        if combined_score >= 0.9:
            return "production"
        elif combined_score >= 0.8:
            return "stable"
        elif combined_score >= 0.6:
            return "beta"
        else:
            return "alpha"

    def _generate_recommendations(self, quality_metrics: QualityMetrics) -> List[str]:
        """Generate improvement recommendations from quality metrics"""
        recommendations = []

        if quality_metrics.documentation_score < 0.6:
            recommendations.append(
                "Consider adding more comprehensive documentation and docstrings"
            )

        if quality_metrics.complexity_score < 0.6:
            recommendations.append(
                "Consider reducing cyclomatic complexity by breaking down large functions"
            )

        if quality_metrics.maintainability_score < 0.6:
            recommendations.append(
                "Consider improving code structure and maintainability"
            )

        if quality_metrics.onex_compliance < 0.7:
            recommendations.append(
                "Consider improving ONEX architectural compliance (reduce Any types, use dependency injection)"
            )

        if quality_metrics.temporal_relevance < 0.5:
            recommendations.append(
                "Code appears outdated - consider reviewing and updating to modern patterns"
            )

        return recommendations
