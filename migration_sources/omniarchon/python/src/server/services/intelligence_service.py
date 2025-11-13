"""
Intelligence Service

Presentation layer service for intelligence operations. This service provides:
- API response formatting using Pydantic models
- Integration with the intelligence data access layer
- HTTP-specific response structures
- Backward compatibility for existing API consumers

This service uses the new intelligence_data_access module for all data operations
and focuses purely on API response formatting and presentation concerns.
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel
from server.data.intelligence_data_access import (
    IntelligenceDataAccess,
    IntelligenceDocumentData,
    IntelligenceStatsData,
    QueryParameters,
    create_intelligence_data_access,
)
from server.services.client_manager import get_database_client

logger = logging.getLogger(__name__)


# Pydantic models for API responses (presentation layer)
class DiffAnalysis(BaseModel):
    total_changes: int
    added_lines: int
    removed_lines: int
    modified_files: list[str]


class TemporalCorrelation(BaseModel):
    repository: str
    commit_sha: str
    time_diff_hours: float
    correlation_strength: float


class SemanticCorrelation(BaseModel):
    repository: str
    commit_sha: str
    semantic_similarity: float
    common_keywords: list[str]
    file_information: Optional[dict[str, Any]] = None


class BreakingChange(BaseModel):
    type: str
    severity: str
    description: str
    files_affected: list[str]


class CorrelationAnalysis(BaseModel):
    temporal_correlations: list[TemporalCorrelation]
    semantic_correlations: list[SemanticCorrelation]
    breaking_changes: list[BreakingChange]


class SecurityAnalysis(BaseModel):
    patterns_detected: list[str]
    risk_level: str
    secure_patterns: int


class IntelligenceData(BaseModel):
    diff_analysis: Optional[DiffAnalysis]
    correlation_analysis: Optional[CorrelationAnalysis]
    security_analysis: Optional[SecurityAnalysis]


class IntelligenceDocument(BaseModel):
    id: str
    created_at: str
    repository: str
    commit_sha: str
    author: str
    change_type: str
    intelligence_data: IntelligenceData


class IntelligenceResponse(BaseModel):
    documents: list[IntelligenceDocument]
    total_count: int
    filtered_count: int
    time_range: str
    repositories: list[str]


class IntelligenceStats(BaseModel):
    total_changes: int
    total_correlations: int
    average_correlation_strength: float
    breaking_changes: int
    repositories_active: int
    time_range: str


# Shared data access instance (singleton pattern)
_data_access_instance = None


def get_intelligence_data_access() -> IntelligenceDataAccess:
    """Get shared intelligence data access instance."""
    global _data_access_instance
    if _data_access_instance is None:
        client = get_database_client()
        _data_access_instance = create_intelligence_data_access(client)
    return _data_access_instance


def parse_time_range(time_range: str) -> int:
    """Parse time range string to hours (backward compatibility)."""
    data_access = get_intelligence_data_access()
    return data_access.parse_time_range(time_range)


def convert_document_data_to_api_model(
    doc_data: IntelligenceDocumentData,
) -> IntelligenceDocument:
    """
    Convert data access model to API response model.

    Args:
        doc_data: IntelligenceDocumentData from data access layer

    Returns:
        IntelligenceDocument for API response
    """
    # Convert diff analysis
    diff_analysis = None
    if doc_data.diff_analysis:
        diff_analysis = DiffAnalysis(
            total_changes=doc_data.diff_analysis.total_changes,
            added_lines=doc_data.diff_analysis.added_lines,
            removed_lines=doc_data.diff_analysis.removed_lines,
            modified_files=doc_data.diff_analysis.modified_files,
        )

    # Convert correlations
    temporal_correlations = [
        TemporalCorrelation(
            repository=tc.repository,
            commit_sha=tc.commit_sha,
            time_diff_hours=tc.time_diff_hours,
            correlation_strength=tc.correlation_strength,
        )
        for tc in doc_data.temporal_correlations
    ]

    semantic_correlations = [
        SemanticCorrelation(
            repository=sc.repository,
            commit_sha=sc.commit_sha,
            semantic_similarity=sc.semantic_similarity,
            common_keywords=sc.common_keywords,
            file_information=getattr(sc, "file_information", None),
        )
        for sc in doc_data.semantic_correlations
    ]

    breaking_changes = [
        BreakingChange(
            type=bc.type,
            severity=bc.severity,
            description=bc.description,
            files_affected=bc.files_affected,
        )
        for bc in doc_data.breaking_changes
    ]

    correlation_analysis = CorrelationAnalysis(
        temporal_correlations=temporal_correlations,
        semantic_correlations=semantic_correlations,
        breaking_changes=breaking_changes,
    )

    # Convert security analysis
    security_analysis = None
    if doc_data.security_analysis:
        security_analysis = SecurityAnalysis(
            patterns_detected=doc_data.security_analysis.patterns_detected,
            risk_level=doc_data.security_analysis.risk_level,
            secure_patterns=doc_data.security_analysis.secure_patterns,
        )

    # Create intelligence data
    intelligence_data = IntelligenceData(
        diff_analysis=diff_analysis,
        correlation_analysis=correlation_analysis,
        security_analysis=security_analysis,
    )

    # Create document model
    return IntelligenceDocument(
        id=doc_data.id,
        created_at=doc_data.created_at,
        repository=doc_data.repository,
        commit_sha=doc_data.commit_sha,
        author=doc_data.author,
        change_type=doc_data.change_type,
        intelligence_data=intelligence_data,
    )


def convert_stats_data_to_api_model(
    stats_data: IntelligenceStatsData, time_range: str
) -> IntelligenceStats:
    """
    Convert data access stats model to API response model.

    Args:
        stats_data: IntelligenceStatsData from data access layer
        time_range: Time range string for API response

    Returns:
        IntelligenceStats for API response
    """
    return IntelligenceStats(
        total_changes=stats_data.total_changes,
        total_correlations=stats_data.total_correlations,
        average_correlation_strength=stats_data.average_correlation_strength,
        breaking_changes=stats_data.breaking_changes,
        repositories_active=stats_data.repositories_active,
        time_range=time_range,
    )


async def get_intelligence_documents_from_db(
    repository: Optional[str] = None,
    time_range: str = "24h",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Get intelligence documents from database (backward compatibility wrapper).

    Returns raw data that can be processed by different layers.
    """
    try:
        data_access = get_intelligence_data_access()
        params = QueryParameters(
            repository=repository, time_range=time_range, limit=limit, offset=offset
        )

        result = data_access.get_raw_documents(params)
        return result

    except Exception as e:
        logger.error(f"Error fetching intelligence documents: {e}")
        return {"documents": [], "success": False, "error": str(e)}


async def calculate_intelligence_stats(
    repository: Optional[str] = None, time_range: str = "24h"
) -> dict[str, Any]:
    """
    Calculate intelligence statistics from raw data (backward compatibility wrapper).

    This is a shared function that can be used by both API and WebSocket handlers.
    """
    try:
        data_access = get_intelligence_data_access()
        params = QueryParameters(repository=repository, time_range=time_range)

        stats_data = data_access.calculate_statistics(params)

        return {
            "total_changes": stats_data.total_changes,
            "total_correlations": stats_data.total_correlations,
            "average_correlation_strength": stats_data.average_correlation_strength,
            "breaking_changes": stats_data.breaking_changes,
            "repositories_active": stats_data.repositories_active,
            "time_range": time_range,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Error calculating intelligence stats: {e}")
        return {
            "total_changes": 0,
            "total_correlations": 0,
            "average_correlation_strength": 0.0,
            "breaking_changes": 0,
            "repositories_active": 0,
            "time_range": time_range,
            "error": str(e),
        }


def parse_intelligence_content(content: dict[str, Any]) -> IntelligenceData:
    """Parse intelligence data from document content (backward compatibility wrapper)."""
    try:
        data_access = get_intelligence_data_access()

        # Parse using data access layer
        diff_analysis = data_access.parse_diff_analysis(content)
        (
            temporal_correlations,
            semantic_correlations,
            breaking_changes,
        ) = data_access.parse_correlations(content)
        security_analysis = data_access.parse_security_analysis(content)

        # Convert to API models
        diff_analysis_api = None
        if diff_analysis:
            diff_analysis_api = DiffAnalysis(
                total_changes=diff_analysis.total_changes,
                added_lines=diff_analysis.added_lines,
                removed_lines=diff_analysis.removed_lines,
                modified_files=diff_analysis.modified_files,
            )

        temporal_correlations_api = [
            TemporalCorrelation(
                repository=tc.repository,
                commit_sha=tc.commit_sha,
                time_diff_hours=tc.time_diff_hours,
                correlation_strength=tc.correlation_strength,
            )
            for tc in temporal_correlations
        ]

        semantic_correlations_api = [
            SemanticCorrelation(
                repository=sc.repository,
                commit_sha=sc.commit_sha,
                semantic_similarity=sc.semantic_similarity,
                common_keywords=sc.common_keywords,
                file_information=getattr(sc, "file_information", None),
            )
            for sc in semantic_correlations
        ]

        breaking_changes_api = [
            BreakingChange(
                type=bc.type,
                severity=bc.severity,
                description=bc.description,
                files_affected=bc.files_affected,
            )
            for bc in breaking_changes
        ]

        correlation_analysis = CorrelationAnalysis(
            temporal_correlations=temporal_correlations_api,
            semantic_correlations=semantic_correlations_api,
            breaking_changes=breaking_changes_api,
        )

        security_analysis_api = None
        if security_analysis:
            security_analysis_api = SecurityAnalysis(
                patterns_detected=security_analysis.patterns_detected,
                risk_level=security_analysis.risk_level,
                secure_patterns=security_analysis.secure_patterns,
            )

        return IntelligenceData(
            diff_analysis=diff_analysis_api,
            correlation_analysis=correlation_analysis,
            security_analysis=security_analysis_api,
        )

    except Exception as e:
        logger.error(f"Error parsing intelligence content: {e}")
        return IntelligenceData(
            diff_analysis=None,
            correlation_analysis=CorrelationAnalysis(
                temporal_correlations=[], semantic_correlations=[], breaking_changes=[]
            ),
            security_analysis=None,
        )


async def get_intelligence_documents(
    repository: Optional[str] = None,
    time_range: str = "24h",
    limit: int = 50,
    offset: int = 0,
) -> IntelligenceResponse:
    """
    Get intelligence documents with optional filtering.

    Returns properly parsed IntelligenceResponse with typed data.
    """
    try:
        data_access = get_intelligence_data_access()
        params = QueryParameters(
            repository=repository, time_range=time_range, limit=limit, offset=offset
        )

        # Get parsed documents from data access layer
        documents_data = data_access.get_parsed_documents(params)

        # Convert to API models
        documents = [
            convert_document_data_to_api_model(doc_data) for doc_data in documents_data
        ]

        # Get total count and repositories
        raw_result = data_access.get_raw_documents(
            QueryParameters(
                repository=repository,
                time_range=time_range,
                limit=10000,  # Large limit to get total count
                offset=0,
            )
        )

        total_count = raw_result.get("total_count", 0)

        # Extract repositories from documents
        repositories = sorted({doc.repository for doc in documents})

        return IntelligenceResponse(
            documents=documents,
            total_count=total_count,
            filtered_count=len(documents),
            time_range=time_range,
            repositories=repositories,
        )

    except Exception as e:
        logger.error(f"Error fetching intelligence documents: {e}")
        return IntelligenceResponse(
            documents=[],
            total_count=0,
            filtered_count=0,
            time_range=time_range,
            repositories=[],
        )


async def get_intelligence_stats(
    repository: Optional[str] = None, time_range: str = "24h"
) -> IntelligenceStats:
    """
    Get aggregated statistics about intelligence activity.

    Returns properly typed IntelligenceStats with all metrics.
    """
    try:
        data_access = get_intelligence_data_access()
        params = QueryParameters(repository=repository, time_range=time_range)

        stats_data = data_access.calculate_statistics(params)
        return convert_stats_data_to_api_model(stats_data, time_range)

    except Exception as e:
        logger.error(f"Error calculating intelligence stats: {e}")
        return IntelligenceStats(
            total_changes=0,
            total_correlations=0,
            average_correlation_strength=0.0,
            breaking_changes=0,
            repositories_active=0,
            time_range=time_range,
        )


async def get_active_repositories() -> list[str]:
    """Get list of repositories that have generated intelligence data."""
    try:
        data_access = get_intelligence_data_access()
        return data_access.get_active_repositories()

    except Exception as e:
        logger.error(f"Error fetching repositories: {e}")
        return []
