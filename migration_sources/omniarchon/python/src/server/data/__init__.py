"""
Data Access Layer

This module provides pure data access functionality separated from
presentation and API concerns. All data access classes return plain
data structures that can be consumed by any layer.

Modules:
- intelligence_data_access: Intelligence data fetching and parsing
"""

from server.data.intelligence_data_access import BreakingChangeData  # Data structures
from server.data.intelligence_data_access import (
    DiffAnalysisData,
    IntelligenceDataAccess,
    IntelligenceDocumentData,
    IntelligenceStatsData,
    QueryParameters,
    SecurityAnalysisData,
    SemanticCorrelationData,
    TemporalCorrelationData,
    TimeRange,
    create_intelligence_data_access,
)

__all__ = [
    "IntelligenceDataAccess",
    "create_intelligence_data_access",
    "QueryParameters",
    "TimeRange",
    # Data structures
    "DiffAnalysisData",
    "TemporalCorrelationData",
    "SemanticCorrelationData",
    "BreakingChangeData",
    "SecurityAnalysisData",
    "IntelligenceDocumentData",
    "IntelligenceStatsData",
]
