"""
Pattern Usage Tracking Module

Tracks pattern usage across the system by monitoring:
- Agent manifest injections (patterns referenced in manifests)
- Agent actions (patterns used in tool calls)
- Routing decisions (patterns influencing agent selection)

Updates pattern_lineage_nodes with:
- usage_count: Incremented when pattern is used
- last_used_at: Timestamp of most recent usage
- used_by_agents: Array of agent names that have used the pattern

Created: 2025-10-28
Purpose: Phase 3 - Pattern usage tracking and analytics
"""

from .analytics import UsageAnalytics
from .kafka_consumer import UsageTrackingConsumer
from .usage_tracker import UsageTracker

__all__ = ["UsageTracker", "UsageTrackingConsumer", "UsageAnalytics"]
