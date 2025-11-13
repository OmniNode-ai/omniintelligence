"""
Phase 4: Pattern Traceability & Metrics

Track pattern lineage, collect usage analytics, and implement feedback loops.

Components:
- Usage Analytics Reducer: Pattern usage metrics aggregation (Agent 2 - Complete)
- Lineage Tracker: Pattern evolution and dependency tracking (Pending)
- Feedback Loop Orchestrator: Pattern improvement workflows (Pending)

Author: Archon Intelligence Team
Date: 2025-10-02
Version: 1.0.0
"""

from uuid import UUID, uuid4

# Agent 2: Usage Analytics Reducer (Complete)
from src.archon_services.pattern_learning.phase4_traceability.model_contract_usage_analytics import (
    AnalyticsGranularity,
    ContextDistribution,
    ModelContractUsageAnalytics,
    ModelUsageAnalyticsInput,
    ModelUsageAnalyticsOutput,
    PerformanceMetrics,
    SuccessMetrics,
    TimeWindowType,
    TrendAnalysis,
    UsageFrequencyMetrics,
    UsageTrendType,
)
from src.archon_services.pattern_learning.phase4_traceability.node_usage_analytics_reducer import (
    NodeUsageAnalyticsReducer,
)

__version__ = "1.0.0"
__author__ = "Archon Intelligence Team"

__all__ = [
    # Usage Analytics Contracts
    "ModelContractUsageAnalytics",
    "ModelUsageAnalyticsInput",
    "ModelUsageAnalyticsOutput",
    # Usage Analytics Metrics
    "UsageFrequencyMetrics",
    "PerformanceMetrics",
    "SuccessMetrics",
    "TrendAnalysis",
    "ContextDistribution",
    # Usage Analytics Enums
    "UsageTrendType",
    "TimeWindowType",
    "AnalyticsGranularity",
    # Usage Analytics Nodes
    "NodeUsageAnalyticsReducer",
]
