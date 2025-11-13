"""
Pattern Learning Engine - Storage Layer Module

Provides ONEX-compliant Effect nodes for pattern storage and analytics.

Track: Track 3-1.2 - PostgreSQL Storage Layer
AI Generated: 75% (Codestral base, human refinement)

Components:
- NodePatternStorageEffect: CRUD operations for patterns
- NodePatternQueryEffect: Pattern search and retrieval
- NodePatternUpdateEffect: Usage tracking and statistics
- NodePatternAnalyticsEffect: Analytics computation
- PatternDatabaseManager: Connection pooling and management

Example Usage:
    >>> from pattern_learning import get_pattern_db_manager, NodePatternStorageEffect
    >>> from pattern_learning import ModelContractEffect
    >>> from uuid import uuid4
    >>>
    >>> # Initialize database
    >>> db_manager = await get_pattern_db_manager()
    >>> await db_manager.initialize_schema()
    >>>
    >>> # Create storage node
    >>> storage_node = NodePatternStorageEffect(db_manager.pool)
    >>>
    >>> # Insert a pattern
    >>> contract = ModelContractEffect(
    ...     operation="insert",
    ...     data={
    ...         "pattern_name": "AsyncDatabasePattern",
    ...         "pattern_type": "code",
    ...         "language": "python",
    ...         "template_code": "async def execute_effect(...)...",
    ...         "confidence_score": 0.95
    ...     },
    ...     correlation_id=uuid4()
    ... )
    >>> result = await storage_node.execute_effect(contract)
    >>> print(result.success, result.data)
"""

from pattern_learning.node_pattern_analytics_effect import NodePatternAnalyticsEffect
from pattern_learning.node_pattern_query_effect import NodePatternQueryEffect
from pattern_learning.node_pattern_storage_effect import (
    ModelContractEffect,
    ModelResult,
    NodePatternStorageEffect,
)
from pattern_learning.node_pattern_update_effect import NodePatternUpdateEffect
from pattern_learning.pattern_database import (
    PatternDatabaseManager,
    close_pattern_db_manager,
    get_pattern_db_manager,
)

__all__ = [
    # Effect Nodes
    "NodePatternStorageEffect",
    "NodePatternQueryEffect",
    "NodePatternUpdateEffect",
    "NodePatternAnalyticsEffect",
    # Database Management
    "PatternDatabaseManager",
    "get_pattern_db_manager",
    "close_pattern_db_manager",
    # Contract Models
    "ModelResult",
    "ModelContractEffect",
]

__version__ = "1.0.0"
__author__ = "AI-Generated (Codestral + Human)"
__track__ = "Track 3-1.2 - PostgreSQL Storage Layer"
