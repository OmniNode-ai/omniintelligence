"""
Correlation Analyzer Service

Automated correlation analysis system for intelligence documents with empty correlations.
Provides temporal and semantic correlation detection across repositories and commits.

This service implements:
- Temporal correlation analysis (time-based relationship detection)
- Semantic similarity analysis (content-based relationship detection)
- Breaking change detection and analysis
- Background processing with queue management
- Performance optimization for large document sets

Architecture follows ONEX principles:
- Single responsibility (correlation analysis only)
- Clean separation from data access
- Testable algorithms with clear inputs/outputs
- Performance-optimized with configurable thresholds
"""

import asyncio
import difflib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CorrelationStrength(Enum):
    """Correlation strength levels."""

    HIGH = 0.8
    MEDIUM = 0.6
    LOW = 0.3


class TimeWindow(Enum):
    """Time windows for temporal correlation analysis."""

    ONE_HOUR = 1
    SIX_HOURS = 6
    TWENTY_FOUR_HOURS = 24
    SEVENTY_TWO_HOURS = 72


@dataclass
class DocumentContext:
    """Document context for correlation analysis."""

    id: str
    repository: str
    commit_sha: str
    author: str
    created_at: datetime
    change_type: str
    content: dict[str, Any]
    modified_files: list[str]
    commit_message: Optional[str] = None


@dataclass
class TemporalCorrelationResult:
    """Result of temporal correlation analysis."""

    repository: str
    commit_sha: str
    time_diff_hours: float
    correlation_strength: float
    correlation_factors: list[str]  # Why this correlation was detected


@dataclass
class SemanticCorrelationResult:
    """Result of semantic correlation analysis."""

    repository: str
    commit_sha: str
    semantic_similarity: float
    common_keywords: list[str]
    similarity_factors: list[str]  # Why this correlation was detected


@dataclass
class BreakingChangeResult:
    """Result of breaking change analysis."""

    type: str
    severity: str
    description: str
    files_affected: list[str]
    confidence: float


@dataclass
class CorrelationAnalysisResult:
    """Complete correlation analysis result."""

    document_id: str
    temporal_correlations: list[TemporalCorrelationResult]
    semantic_correlations: list[SemanticCorrelationResult]
    breaking_changes: list[BreakingChangeResult]
    analysis_metadata: dict[str, Any]


class CorrelationAnalyzer:
    """
    Main correlation analyzer with temporal and semantic analysis capabilities.

    This class provides comprehensive correlation analysis for intelligence documents
    using multiple algorithms and heuristics to detect relationships between commits.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        """
        Initialize correlation analyzer with configuration.

        Args:
            config: Configuration dictionary with analysis parameters
        """
        self.config = config or {}

        # Default configuration values
        self.temporal_threshold_hours = self.config.get("temporal_threshold_hours", 72)
        self.semantic_threshold = self.config.get("semantic_threshold", 0.3)
        self.max_correlations_per_document = self.config.get(
            "max_correlations_per_document", 10
        )
        self.keyword_weight = self.config.get("keyword_weight", 0.4)
        self.file_path_weight = self.config.get("file_path_weight", 0.3)
        self.author_weight = self.config.get("author_weight", 0.2)
        self.commit_message_weight = self.config.get("commit_message_weight", 0.1)

        # Compile regex patterns for performance
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for keyword and change type detection."""
        self.breaking_change_patterns = [
            re.compile(
                r"\b(break|breaking|deprecated?|remov[ed]|delet[ed])\b", re.IGNORECASE
            ),
            re.compile(r"\b(major|critical|incompatible)\b", re.IGNORECASE),
            re.compile(r"\bv?\d+\.\d+\.\d+", re.IGNORECASE),  # Version patterns
        ]

        self.feature_keywords = [
            re.compile(r"\b(feat|feature|add|new|implement|create)\b", re.IGNORECASE),
            re.compile(r"\b(fix|bug|patch|correct|repair)\b", re.IGNORECASE),
            re.compile(r"\b(refactor|clean|reorganize|restructure)\b", re.IGNORECASE),
            re.compile(r"\b(test|spec|coverage|validation)\b", re.IGNORECASE),
            re.compile(r"\b(docs?|documentation|readme)\b", re.IGNORECASE),
            re.compile(r"\b(perf|performance|optimize|speed)\b", re.IGNORECASE),
            re.compile(
                r"\b(security|auth|authentication|authorization)\b", re.IGNORECASE
            ),
        ]

    async def analyze_document_correlations(
        self, target_document: DocumentContext, context_documents: list[DocumentContext]
    ) -> CorrelationAnalysisResult:
        """
        Analyze correlations for a single document against context documents.

        Args:
            target_document: Document to analyze correlations for
            context_documents: Other documents to compare against

        Returns:
            CorrelationAnalysisResult with all detected correlations
        """
        analysis_start = datetime.now(UTC)

        try:
            # Run temporal and semantic analysis in parallel
            temporal_task = asyncio.create_task(
                self._analyze_temporal_correlations(target_document, context_documents)
            )
            semantic_task = asyncio.create_task(
                self._analyze_semantic_correlations(target_document, context_documents)
            )
            breaking_changes_task = asyncio.create_task(
                self._analyze_breaking_changes(target_document, context_documents)
            )

            # Wait for all analysis tasks to complete
            (
                temporal_correlations,
                semantic_correlations,
                breaking_changes,
            ) = await asyncio.gather(
                temporal_task, semantic_task, breaking_changes_task
            )

            analysis_duration = (datetime.now(UTC) - analysis_start).total_seconds()

            # Create analysis metadata
            metadata = {
                "analysis_timestamp": analysis_start.isoformat(),
                "analysis_duration_seconds": analysis_duration,
                "context_documents_analyzed": len(context_documents),
                "temporal_correlations_found": len(temporal_correlations),
                "semantic_correlations_found": len(semantic_correlations),
                "breaking_changes_detected": len(breaking_changes),
                "analyzer_version": "1.0.0",
                "configuration": {
                    "temporal_threshold_hours": self.temporal_threshold_hours,
                    "semantic_threshold": self.semantic_threshold,
                    "max_correlations": self.max_correlations_per_document,
                },
            }

            return CorrelationAnalysisResult(
                document_id=target_document.id,
                temporal_correlations=temporal_correlations,
                semantic_correlations=semantic_correlations,
                breaking_changes=breaking_changes,
                analysis_metadata=metadata,
            )

        except Exception as e:
            logger.error(
                f"Error analyzing correlations for document {target_document.id}: {e}"
            )

            # Return empty result with error metadata
            return CorrelationAnalysisResult(
                document_id=target_document.id,
                temporal_correlations=[],
                semantic_correlations=[],
                breaking_changes=[],
                analysis_metadata={
                    "analysis_timestamp": analysis_start.isoformat(),
                    "analysis_error": str(e),
                    "analyzer_version": "1.0.0",
                },
            )

    async def _analyze_temporal_correlations(
        self, target_document: DocumentContext, context_documents: list[DocumentContext]
    ) -> list[TemporalCorrelationResult]:
        """
        Analyze temporal correlations based on time proximity and related factors.

        Args:
            target_document: Document to analyze
            context_documents: Context documents to compare against

        Returns:
            List of temporal correlations
        """
        temporal_correlations = []
        target_time = target_document.created_at

        for context_doc in context_documents:
            # Skip self-correlation
            if context_doc.id == target_document.id:
                continue

            # Calculate time difference
            time_diff = (
                abs((target_time - context_doc.created_at).total_seconds()) / 3600.0
            )

            # Skip if outside temporal threshold
            if time_diff > self.temporal_threshold_hours:
                continue

            # Calculate correlation strength based on multiple factors
            correlation_factors = []
            strength_components = []

            # Time proximity factor (closer in time = stronger correlation)
            time_proximity = max(0, 1.0 - (time_diff / self.temporal_threshold_hours))
            strength_components.append(time_proximity * 0.4)
            correlation_factors.append(f"Time proximity: {time_diff:.1f}h")

            # Author similarity factor
            if target_document.author == context_doc.author:
                strength_components.append(0.2)
                correlation_factors.append("Same author")

            # Repository similarity factor
            if target_document.repository == context_doc.repository:
                strength_components.append(0.2)
                correlation_factors.append("Same repository")
            else:
                # Cross-repository correlation (slightly lower weight)
                strength_components.append(0.1)
                correlation_factors.append("Cross-repository")

            # File overlap factor
            target_files = set(target_document.modified_files)
            context_files = set(context_doc.modified_files)
            file_overlap = len(target_files.intersection(context_files))

            if file_overlap > 0:
                overlap_ratio = file_overlap / len(target_files.union(context_files))
                strength_components.append(overlap_ratio * 0.3)
                correlation_factors.append(f"File overlap: {file_overlap} files")

            # Change type similarity
            if target_document.change_type == context_doc.change_type:
                strength_components.append(0.1)
                correlation_factors.append("Similar change type")

            # Calculate final strength
            correlation_strength = sum(strength_components)

            # Only include if above minimum threshold
            if correlation_strength >= CorrelationStrength.LOW.value:
                temporal_correlations.append(
                    TemporalCorrelationResult(
                        repository=context_doc.repository,
                        commit_sha=context_doc.commit_sha,
                        time_diff_hours=time_diff,
                        correlation_strength=round(correlation_strength, 3),
                        correlation_factors=correlation_factors,
                    )
                )

        # Sort by correlation strength and limit results
        temporal_correlations.sort(key=lambda x: x.correlation_strength, reverse=True)
        return temporal_correlations[: self.max_correlations_per_document]

    async def _analyze_semantic_correlations(
        self, target_document: DocumentContext, context_documents: list[DocumentContext]
    ) -> list[SemanticCorrelationResult]:
        """
        Analyze semantic correlations based on content similarity.

        Args:
            target_document: Document to analyze
            context_documents: Context documents to compare against

        Returns:
            List of semantic correlations
        """
        semantic_correlations = []

        # Extract keywords and content from target document
        target_keywords = self._extract_keywords(target_document)
        target_content = self._extract_content_text(target_document)

        for context_doc in context_documents:
            # Skip self-correlation and very recent documents (temporal handles those)
            if context_doc.id == target_document.id:
                continue

            time_diff = (
                abs(
                    (
                        target_document.created_at - context_doc.created_at
                    ).total_seconds()
                )
                / 3600.0
            )
            if (
                time_diff < 1.0
            ):  # Skip documents within 1 hour (temporal correlation territory)
                continue

            # Extract keywords and content from context document
            context_keywords = self._extract_keywords(context_doc)
            context_content = self._extract_content_text(context_doc)

            # Calculate semantic similarity
            similarity_factors = []
            similarity_components = []

            # Keyword similarity
            common_keywords = target_keywords.intersection(context_keywords)
            if common_keywords:
                keyword_similarity = len(common_keywords) / len(
                    target_keywords.union(context_keywords)
                )
                similarity_components.append(keyword_similarity * self.keyword_weight)
                similarity_factors.append(
                    f"Keyword overlap: {len(common_keywords)} keywords"
                )

            # File path similarity
            target_paths = [
                self._extract_path_components(f) for f in target_document.modified_files
            ]
            context_paths = [
                self._extract_path_components(f) for f in context_doc.modified_files
            ]

            path_similarity = self._calculate_path_similarity(
                target_paths, context_paths
            )
            if path_similarity > 0:
                similarity_components.append(path_similarity * self.file_path_weight)
                similarity_factors.append(f"Path similarity: {path_similarity:.2f}")

            # Content similarity (using difflib for text comparison)
            if target_content and context_content:
                content_similarity = difflib.SequenceMatcher(
                    None, target_content, context_content
                ).ratio()
                similarity_components.append(content_similarity * 0.3)
                similarity_factors.append(
                    f"Content similarity: {content_similarity:.2f}"
                )

            # Calculate final similarity
            semantic_similarity = sum(similarity_components)

            # Only include if above minimum threshold
            if semantic_similarity >= self.semantic_threshold:
                semantic_correlations.append(
                    SemanticCorrelationResult(
                        repository=context_doc.repository,
                        commit_sha=context_doc.commit_sha,
                        semantic_similarity=round(semantic_similarity, 3),
                        common_keywords=sorted(common_keywords),
                        similarity_factors=similarity_factors,
                    )
                )

        # Sort by similarity and limit results
        semantic_correlations.sort(key=lambda x: x.semantic_similarity, reverse=True)
        return semantic_correlations[: self.max_correlations_per_document]

    async def _analyze_breaking_changes(
        self, target_document: DocumentContext, context_documents: list[DocumentContext]
    ) -> list[BreakingChangeResult]:
        """
        Analyze breaking changes in the target document.

        Args:
            target_document: Document to analyze
            context_documents: Context documents for additional context

        Returns:
            List of breaking changes detected
        """
        breaking_changes = []

        # Analyze commit message and content for breaking change indicators
        content_text = self._extract_content_text(target_document)
        commit_message = target_document.commit_message or ""

        # Check for breaking change patterns in commit message
        breaking_indicators = []
        for pattern in self.breaking_change_patterns:
            if pattern.search(commit_message):
                breaking_indicators.append(f"Commit message: {pattern.pattern}")

        # Check for breaking change patterns in content
        if pattern.search(content_text):
            breaking_indicators.append(f"Content: {pattern.pattern}")

        # Analyze file changes for potential breaking changes
        high_risk_files = [
            f
            for f in target_document.modified_files
            if any(
                keyword in f.lower()
                for keyword in [
                    "api",
                    "interface",
                    "schema",
                    "migration",
                    "config",
                    "public",
                ]
            )
        ]

        if high_risk_files:
            breaking_indicators.append(f"High-risk files: {len(high_risk_files)} files")

        # Create breaking change entries based on detected indicators
        if breaking_indicators:
            # Determine severity based on number of indicators
            severity = (
                "HIGH"
                if len(breaking_indicators) >= 3
                else "MEDIUM" if len(breaking_indicators) >= 2 else "LOW"
            )

            breaking_changes.append(
                BreakingChangeResult(
                    type="potential_breaking_change",
                    severity=severity,
                    description=f"Breaking change indicators detected: {'; '.join(breaking_indicators)}",
                    files_affected=target_document.modified_files,
                    confidence=min(0.9, len(breaking_indicators) * 0.3),
                )
            )

        return breaking_changes

    def _extract_keywords(self, document: DocumentContext) -> set[str]:
        """Extract keywords from document content and metadata."""
        keywords = set()

        # Extract from commit message if available
        if document.commit_message:
            for pattern in self.feature_keywords:
                matches = pattern.findall(document.commit_message)
                keywords.update(match.lower() for match in matches)

        # Extract from change type
        if document.change_type:
            keywords.add(document.change_type.lower())

        # Extract from file paths
        for file_path in document.modified_files:
            path_parts = file_path.split("/")
            for part in path_parts:
                # Extract meaningful path components
                if len(part) > 2 and not part.startswith("."):
                    keywords.add(part.lower())

        # Extract from content
        content_text = self._extract_content_text(document)
        for pattern in self.feature_keywords:
            matches = pattern.findall(content_text)
            keywords.update(match.lower() for match in matches)

        return keywords

    def _extract_content_text(self, document: DocumentContext) -> str:
        """Extract text content from document for analysis."""
        content_parts = []

        # Extract from various content fields
        content = document.content

        # Add analysis type/description
        if isinstance(content.get("analysis_type"), str):
            content_parts.append(content["analysis_type"])

        # Add diff analysis information
        if "diff_analysis" in content:
            diff_data = content["diff_analysis"]
            content_parts.extend(diff_data.get("modified_files", []))

        # Add correlation analysis text
        if "correlation_analysis" in content:
            corr_data = content["correlation_analysis"]
            # Extract text from correlation descriptions
            for bc in corr_data.get("breaking_changes", []):
                if isinstance(bc.get("description"), str):
                    content_parts.append(bc["description"])

        # Add security analysis text
        if "security_analysis" in content:
            sec_data = content["security_analysis"]
            content_parts.extend(sec_data.get("patterns_detected", []))

        # Join all text content
        return " ".join(content_parts).lower()

    def _extract_path_components(self, file_path: str) -> list[str]:
        """Extract meaningful components from file path."""
        components = []
        path_parts = file_path.split("/")

        for part in path_parts:
            if part and not part.startswith("."):
                # Remove file extension for comparison
                name = part.split(".")[0] if "." in part else part
                if len(name) > 1:
                    components.append(name.lower())

        return components

    def _calculate_path_similarity(
        self, target_paths: list[list[str]], context_paths: list[list[str]]
    ) -> float:
        """Calculate similarity between file path components."""
        if not target_paths or not context_paths:
            return 0.0

        # Flatten path components
        target_components = set()
        for path in target_paths:
            target_components.update(path)

        context_components = set()
        for path in context_paths:
            context_components.update(path)

        # Calculate Jaccard similarity
        intersection = len(target_components.intersection(context_components))
        union = len(target_components.union(context_components))

        return intersection / union if union > 0 else 0.0


# Factory function for creating analyzer instances
def create_correlation_analyzer(
    config: Optional[dict[str, Any]] = None,
) -> CorrelationAnalyzer:
    """
    Create a correlation analyzer instance with configuration.

    Args:
        config: Optional configuration dictionary

    Returns:
        CorrelationAnalyzer instance
    """
    return CorrelationAnalyzer(config)
