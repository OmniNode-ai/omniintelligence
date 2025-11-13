"""
Intelligence Data Structures Module

Defines all data structures and models used for intelligence operations.
Focused on data representation without business logic.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class TimeRange(Enum):
    """Enumeration of supported time ranges."""

    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    TWENTY_FOUR_HOURS = "24h"
    SEVENTY_TWO_HOURS = "72h"
    SEVEN_DAYS = "7d"


@dataclass
class QueryParameters:
    """Parameters for querying intelligence documents."""

    repository: Optional[str] = None
    time_range: str = "24h"
    limit: int = 50
    offset: int = 0


@dataclass
class DiffAnalysisData:
    """Raw diff analysis data structure."""

    total_changes: int
    added_lines: int
    removed_lines: int
    modified_files: list[str]


@dataclass
class TemporalCorrelationData:
    """Raw temporal correlation data structure."""

    repository: str
    commit_sha: str
    time_diff_hours: float
    correlation_strength: float


@dataclass
class SemanticCorrelationData:
    """Raw semantic correlation data structure."""

    repository: str
    commit_sha: str
    semantic_similarity: float
    common_keywords: list[str]
    file_information: Optional[dict[str, Any]] = None  # File-level analysis data


@dataclass
class BreakingChangeData:
    """Raw breaking change data structure."""

    type: str
    severity: str
    description: str
    files_affected: list[str]


@dataclass
class SecurityAnalysisData:
    """Raw security analysis data structure."""

    patterns_detected: list[str]
    risk_level: str
    secure_patterns: int


@dataclass
class IntelligenceDocumentData:
    """Complete intelligence document data structure."""

    id: str
    created_at: str
    repository: str
    commit_sha: str
    author: str
    change_type: str
    diff_analysis: Optional[DiffAnalysisData]
    temporal_correlations: list[TemporalCorrelationData]
    semantic_correlations: list[SemanticCorrelationData]
    breaking_changes: list[BreakingChangeData]
    security_analysis: Optional[SecurityAnalysisData]


@dataclass
class IntelligenceStatsData:
    """Intelligence statistics data structure."""

    total_changes: int
    total_correlations: int
    average_correlation_strength: float
    breaking_changes: int
    repositories_active: int
    repositories_list: list[str]
    correlation_strengths: list[float]
