"""
Phase 4 Traceability - Test Fixtures

Shared pytest fixtures for Phase 4 testing with comprehensive test data.

Fixtures:
    - Node instances (lineage tracker, usage analytics, feedback loop)
    - Model instances (lineage nodes, edges, events, metrics, feedback)
    - Contract instances (for all node types)
    - Sample data (execution data, metrics, feedback)
    - Mock dependencies (database, memgraph, qdrant)
    - Performance fixtures (timing, benchmarks)

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from archon_services.pattern_learning.phase4_traceability.model_contract_feedback_loop import (
    ModelFeedbackLoopInput,
)

# Contract imports
from archon_services.pattern_learning.phase4_traceability.model_contract_pattern_lineage import (
    LineageDepth,
    LineageEventType,
    LineageOperation,
    ModelLineageQueryInput,
    ModelPatternLineageInput,
)
from archon_services.pattern_learning.phase4_traceability.model_contract_usage_analytics import (
    AnalyticsGranularity,
    ModelUsageAnalyticsInput,
    TimeWindowType,
    UsageTrendType,
)
from archon_services.pattern_learning.phase4_traceability.models.model_lineage_edge import (
    EnumEdgeStrength,
    EnumLineageRelationshipType,
    ModelLineageEdge,
)
from archon_services.pattern_learning.phase4_traceability.models.model_lineage_event import (
    EnumEventActor,
    EnumEventSeverity,
    EnumLineageEventType,
    ModelLineageEvent,
)
from archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
    FeedbackSentiment,
    ImprovementStatus,
    ModelPatternFeedback,
    ModelPatternImprovement,
)

# Model imports
from archon_services.pattern_learning.phase4_traceability.models.model_pattern_lineage_node import (
    EnumPatternEvolutionType,
    EnumPatternLineageStatus,
    ModelPatternLineageNode,
)
from archon_services.pattern_learning.phase4_traceability.models.model_pattern_metrics import (
    ModelPatternHealthMetrics,
    ModelPatternPerformanceMetrics,
    ModelPatternTrendAnalysis,
    ModelPatternUsageMetrics,
)
from archon_services.pattern_learning.phase4_traceability.node_feedback_loop_orchestrator import (
    NodeFeedbackLoopOrchestrator,
)

# Phase 4 imports
from archon_services.pattern_learning.phase4_traceability.node_pattern_lineage_tracker_effect import (
    NodePatternLineageTrackerEffect,
)
from archon_services.pattern_learning.phase4_traceability.node_usage_analytics_reducer import (
    NodeUsageAnalyticsReducer,
)

# ============================================================================
# Node Fixtures
# ============================================================================


@pytest.fixture
def lineage_tracker(mock_db_pool):
    """Create lineage tracker node instance with mock database pool."""
    return NodePatternLineageTrackerEffect(db_pool=mock_db_pool)


@pytest.fixture
def usage_analytics_reducer():
    """Create usage analytics reducer node instance."""
    return NodeUsageAnalyticsReducer()


@pytest.fixture
def feedback_loop_orchestrator():
    """Create feedback loop orchestrator node instance."""
    return NodeFeedbackLoopOrchestrator()


# ============================================================================
# Pattern ID Fixtures
# ============================================================================


@pytest.fixture
def sample_pattern_id():
    """Generate sample pattern ID."""
    return uuid4()


@pytest.fixture
def parent_pattern_id():
    """Generate parent pattern ID."""
    return uuid4()


@pytest.fixture
def child_pattern_id():
    """Generate child pattern ID."""
    return uuid4()


# ============================================================================
# Lineage Model Fixtures
# ============================================================================


@pytest.fixture
def sample_lineage_node(sample_pattern_id):
    """Create sample lineage node."""
    return ModelPatternLineageNode(
        pattern_id=sample_pattern_id,
        version=1,
        parent_ids=[],
        child_ids=[],
        status=EnumPatternLineageStatus.ACTIVE,
        evolution_type=EnumPatternEvolutionType.CREATED,
        created_at=datetime.now(timezone.utc),
        created_by="system",
        metadata={
            "source": "test_fixture",
            "test": True,
        },
    )


@pytest.fixture
def parent_lineage_node(parent_pattern_id):
    """Create parent lineage node."""
    return ModelPatternLineageNode(
        pattern_id=parent_pattern_id,
        version=1,
        parent_ids=[],
        child_ids=[],
        status=EnumPatternLineageStatus.ACTIVE,
        evolution_type=EnumPatternEvolutionType.CREATED,
        created_at=datetime.now(timezone.utc) - timedelta(days=7),
        created_by="system",
        metadata={"source": "parent_fixture"},
    )


@pytest.fixture
def child_lineage_node(child_pattern_id, sample_pattern_id):
    """Create child lineage node (derived from sample)."""
    return ModelPatternLineageNode(
        pattern_id=child_pattern_id,
        version=1,
        parent_ids=[sample_pattern_id],
        child_ids=[],
        status=EnumPatternLineageStatus.ACTIVE,
        evolution_type=EnumPatternEvolutionType.REFINED,
        created_at=datetime.now(timezone.utc),
        created_by="ai_system",
        metadata={"source": "child_fixture", "parent": sample_pattern_id},
    )


@pytest.fixture
def sample_lineage_edge(sample_pattern_id, parent_pattern_id):
    """Create sample lineage edge."""
    return ModelLineageEdge(
        source_node_id=uuid4(),
        target_node_id=uuid4(),
        source_pattern_id=parent_pattern_id,
        target_pattern_id=sample_pattern_id,
        relationship_type=EnumLineageRelationshipType.PARENT_OF,
        edge_strength=EnumEdgeStrength.STRONG,
        created_at=datetime.now(timezone.utc),
        created_by="system",
        metadata={"confidence": 0.95},
    )


@pytest.fixture
def sample_lineage_event(sample_pattern_id):
    """Create sample lineage event."""
    return ModelLineageEvent(
        event_id=uuid4(),
        pattern_id=sample_pattern_id,
        event_type=EnumLineageEventType.PATTERN_CREATED,
        event_severity=EnumEventSeverity.INFO,
        actor_type=EnumEventActor.SYSTEM,
        actor_id="system",
        timestamp=datetime.now(timezone.utc),
        description="Pattern created via test fixture",
        metadata={},
    )


# ============================================================================
# Metrics Fixtures
# ============================================================================


@pytest.fixture
def sample_usage_metrics(sample_pattern_id):
    """Create sample usage metrics."""
    return ModelPatternUsageMetrics(
        pattern_id=sample_pattern_id,
        pattern_name="test_pattern",
        metrics_date=datetime.now(timezone.utc).date(),
        execution_count=100,
        success_count=85,
        failure_count=15,
        success_rate=0.85,
        avg_execution_time_ms=250.5,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_performance_metrics(sample_pattern_id):
    """Create sample performance metrics."""
    return ModelPatternPerformanceMetrics(
        pattern_id=sample_pattern_id,
        pattern_name="test_pattern",
        execution_time_ms=250.0,
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_health_metrics(sample_pattern_id):
    """Create sample health metrics."""
    return ModelPatternHealthMetrics(
        pattern_id=sample_pattern_id,
        pattern_name="test_pattern",
        time_window_days=7,
        total_executions=100,
        avg_success_rate=0.85,
        avg_execution_time_ms=250.5,
        p50_execution_time_ms=200.0,
        p95_execution_time_ms=450.0,
        p99_execution_time_ms=800.0,
        error_rate=0.15,
        trend="increasing",
        health_status="healthy",
        calculated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_trend_analysis(sample_pattern_id):
    """Create sample trend analysis."""
    return ModelPatternTrendAnalysis(
        pattern_id=sample_pattern_id,
        pattern_name="test_pattern",
        analysis_period_days=7,
        daily_executions=[10 + i for i in range(7)],
        trend_direction="increasing",
        calculated_at=datetime.now(timezone.utc),
    )


# ============================================================================
# Feedback Fixtures
# ============================================================================


@pytest.fixture
def sample_feedback(sample_pattern_id):
    """Create sample pattern feedback."""
    return ModelPatternFeedback(
        feedback_id=str(uuid4()),
        pattern_id=sample_pattern_id,
        sentiment=FeedbackSentiment.POSITIVE,
        quality_rating=4.5,
        feedback_text="Pattern works well for API debugging",
        execution_id=str(uuid4()),
        created_by="test_user",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_improvement(sample_pattern_id):
    """Create sample pattern improvement."""
    return ModelPatternImprovement(
        improvement_id=str(uuid4()),
        pattern_id=sample_pattern_id,
        improvement_type="performance",
        description="Optimize query performance by adding index",
        status=ImprovementStatus.PROPOSED,
        created_at=datetime.now(timezone.utc),
        created_by="ai_system",
        confidence_score=0.85,
    )


# ============================================================================
# Execution Data Fixtures
# ============================================================================


@pytest.fixture
def sample_execution_data():
    """Create sample execution data for analytics."""
    now = datetime.now(timezone.utc)
    data = []

    # Create 100 execution records over 7 days
    for i in range(100):
        timestamp = now - timedelta(days=6 - (i // 15), hours=i % 24)

        data.append(
            {
                "execution_id": str(uuid4()),
                "timestamp": timestamp,
                "success": i % 5 != 0,  # 80% success rate
                "execution_time_ms": 100 + (i % 50) * 10,  # 100-590ms
                "quality_score": 0.7 + (i % 30) * 0.01,  # 0.7-0.99
                "quality_gates_passed": i % 10 != 0,  # 90% pass rate
                "timeout": i % 20 == 0,  # 5% timeout rate
                "context_type": ["debugging", "api_design", "performance"][i % 3],
                "agent": f"agent-{i % 5}",  # 5 different agents
                "project": f"project-{i % 3}",  # 3 different projects
                "file_path": f"src/file_{i % 10}.py",  # 10 different files
            }
        )

    return data


@pytest.fixture
def empty_execution_data():
    """Create empty execution data for edge case testing."""
    return []


@pytest.fixture
def single_execution_data():
    """Create single execution record for edge case testing."""
    now = datetime.now(timezone.utc)
    return [
        {
            "execution_id": str(uuid4()),
            "timestamp": now,
            "success": True,
            "execution_time_ms": 250,
            "quality_score": 0.85,
            "quality_gates_passed": True,
            "timeout": False,
            "context_type": "debugging",
            "agent": "agent-1",
            "project": "project-1",
            "file_path": "src/test.py",
        }
    ]


# ============================================================================
# Contract Fixtures
# ============================================================================


@pytest.fixture
def sample_lineage_contract(sample_pattern_id):
    """Create sample lineage contract for creation."""
    return ModelPatternLineageInput(
        name="test_lineage_creation",
        operation="track_creation",
        event_type=LineageEventType.PATTERN_CREATED,
        pattern_id=str(sample_pattern_id),
        pattern_name="test_pattern",
        pattern_version="1.0.0",
        parent_pattern_ids=[],
        metadata={"source": "test"},
    )


@pytest.fixture
def sample_query_contract(sample_pattern_id):
    """Create sample lineage query contract."""
    return ModelLineageQueryInput(
        name="test_query_ancestors",
        operation=LineageOperation.QUERY_ANCESTORS,
        pattern_id=sample_pattern_id,
        depth=LineageDepth.FULL,
        include_metadata=True,
    )


@pytest.fixture
def sample_analytics_contract(sample_pattern_id, sample_execution_data):
    """Create sample usage analytics contract with execution data."""
    now = datetime.now(timezone.utc)
    return ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=now - timedelta(days=7),
        time_window_end=now,
        time_window_type=TimeWindowType.LAST_7_DAYS,
        granularity=AnalyticsGranularity.DAILY,
        include_trends=True,
        include_predictions=True,  # Fixed: was include_forecasts
        execution_data=sample_execution_data,  # Add execution data
    )


@pytest.fixture
def sample_feedback_contract(sample_pattern_id):
    """Create sample feedback loop contract."""
    return ModelFeedbackLoopInput(
        pattern_id=str(sample_pattern_id),  # Convert UUID to string
        feedback_type="performance",
        time_window_days=7,
        auto_apply_threshold=0.95,
        min_sample_size=30,
        significance_level=0.05,
        enable_ab_testing=True,
    )


# ============================================================================
# Mock Database Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Create mock database connection pool with query-aware responses."""
    from unittest.mock import MagicMock
    from uuid import uuid4

    pool = AsyncMock()
    connection = AsyncMock()

    # Store state for pattern nodes to ensure consistency across queries
    pattern_node_cache = {}
    inserted_patterns = set()  # Track which patterns have been inserted

    def get_or_create_pattern_node(pattern_id: str) -> dict:
        """Get or create a cached pattern node for consistency."""
        if pattern_id not in pattern_node_cache:
            node_id = uuid4()
            lineage_id = uuid4()
            pattern_node_cache[pattern_id] = {
                "id": node_id,
                "pattern_id": pattern_id,
                "pattern_version": "1.0.0",
                "lineage_id": lineage_id,
                "generation": 1,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "status": "active",
                "parent_ids": [],
                "child_ids": [],
            }
        return pattern_node_cache[pattern_id]

    def mark_pattern_inserted(pattern_id: str):
        """Mark a pattern as inserted."""
        inserted_patterns.add(pattern_id)

    def mock_fetchrow_generator(*args, **kwargs):
        """
        Return pattern rows based on query type.

        Handles:
        - pattern_lineage_nodes table queries (SELECT id, lineage_id, generation...)
        - pattern_ancestry_cache queries (SELECT ancestor_ids, ancestor_pattern_ids...)
        - get_pattern_ancestry function calls
        - INSERT...RETURNING statements
        """
        query = args[0] if args else ""

        # Handle get_pattern_ancestry function calls
        if "get_pattern_ancestry" in query:
            # Return empty list for fetch (no ancestors for root patterns)
            return None

        # Handle get_pattern_descendants function calls
        if "get_pattern_descendants" in query:
            # Return empty list for fetch (no descendants by default)
            return None

        # Handle pattern_ancestry_cache queries
        if "pattern_ancestry_cache" in query:
            # Return ancestry cache data
            node_id = args[1] if len(args) > 1 else uuid4()
            return {
                "pattern_id": str(uuid4()),
                "pattern_node_id": node_id,
                "ancestor_ids": [],  # Empty for root patterns
                "ancestor_pattern_ids": [],  # Empty for root patterns
                "ancestry_depth": 0,
                "total_ancestors": 0,
                "cache_version": 1,
                "last_updated": datetime.now(timezone.utc),
                "is_stale": False,
            }

        # Handle pattern_lineage_nodes SELECT queries
        if "SELECT" in query and "pattern_lineage_nodes" in query:
            # Extract pattern_id from query parameters if provided
            pattern_id = str(args[1]) if len(args) > 1 else str(uuid4())

            # Distinguish between existence checks and lookups
            # Existence checks include "pattern_version" in WHERE clause
            # Lookups typically just query by pattern_id
            is_existence_check = "pattern_version" in query and len(args) > 2

            if is_existence_check:
                # For existence checks during creation, return None if not yet inserted
                # This allows patterns to be created
                if pattern_id not in inserted_patterns:
                    return None

            # For lookups or existing patterns, return the cached node
            # This allows query operations to find patterns
            return get_or_create_pattern_node(pattern_id)

        # Handle INSERT...RETURNING queries for pattern_lineage_nodes
        if (
            "INSERT" in query
            and "pattern_lineage_nodes" in query
            and "RETURNING" in query
        ):
            # Extract pattern_id from INSERT parameters (second parameter after id)
            pattern_id = str(args[2]) if len(args) > 2 else str(uuid4())

            # Mark pattern as inserted
            mark_pattern_inserted(pattern_id)

            # Get or create the node
            node = get_or_create_pattern_node(pattern_id)
            return {
                "id": node["id"],
                "lineage_id": node["lineage_id"],
                "created_at": node["created_at"],
            }

        # Handle INSERT...RETURNING queries for events
        if "INSERT" in query and "RETURNING" in query:
            return {
                "id": uuid4(),
                "timestamp": datetime.now(timezone.utc),
            }

        # Default fallback
        pattern_uuid = uuid4()
        node = get_or_create_pattern_node(str(pattern_uuid))
        return node

    connection.fetchrow = AsyncMock(side_effect=mock_fetchrow_generator)
    connection.fetchval = AsyncMock(return_value=str(uuid4()))

    def mock_fetch_generator(*args, **kwargs):
        """
        Return list of pattern rows based on query type.

        Handles:
        - get_pattern_ancestry function results
        - get_pattern_descendants function results
        - General pattern queries
        """
        query = args[0] if args else ""

        # Handle get_pattern_ancestry function calls
        if "get_pattern_ancestry" in query:
            # Return ancestry records
            node_id = args[1] if len(args) > 1 else uuid4()
            return [
                {
                    "ancestor_id": node_id,
                    "ancestor_pattern_id": str(uuid4()),
                    "generation": 1,
                    "edge_type": "derived_from",
                    "created_at": datetime.now(timezone.utc),
                }
            ]

        # Handle get_pattern_descendants function calls
        if "get_pattern_descendants" in query:
            # Return descendant records
            return [
                {
                    "descendant_id": uuid4(),
                    "descendant_pattern_id": str(uuid4()),
                    "edge_type": "derived_from",
                    "transformation_type": "enhancement",
                    "created_at": datetime.now(timezone.utc),
                }
            ]

        # Default: return list of pattern nodes
        pattern_id = str(uuid4())
        return [get_or_create_pattern_node(pattern_id)]

    connection.fetch = AsyncMock(side_effect=mock_fetch_generator)
    connection.execute = AsyncMock()

    # Mock transaction context manager
    transaction_mock = MagicMock()
    transaction_mock.__aenter__ = AsyncMock(return_value=None)
    transaction_mock.__aexit__ = AsyncMock(return_value=None)
    connection.transaction = MagicMock(return_value=transaction_mock)

    # Mock the acquire context manager properly
    acquire_context = MagicMock()
    acquire_context.__aenter__ = AsyncMock(return_value=connection)
    acquire_context.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_context)

    return pool


@pytest.fixture
def mock_memgraph_driver():
    """Create mock Memgraph driver."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    return driver


@pytest.fixture
def mock_qdrant_client():
    """Create mock Qdrant client."""
    client = AsyncMock()
    return client


# ============================================================================
# Performance Fixtures
# ============================================================================


@pytest.fixture
def performance_timer():
    """Create performance timer for testing."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()

        @property
        def elapsed_ms(self):
            if self.start_time and self.end_time:
                return (self.end_time - self.start_time) * 1000
            return None

    return Timer()


@pytest.fixture
def benchmark_thresholds():
    """Define performance benchmark thresholds."""
    return {
        "lineage_create": 200,  # ms
        "lineage_query": 100,  # ms
        "analytics_aggregation": 500,  # ms
        "feedback_loop": 60000,  # ms (1 min)
        "dashboard_load": 2000,  # ms
    }


# ============================================================================
# Integration Fixtures
# ============================================================================


@pytest.fixture
async def integration_setup():
    """Setup integration test environment."""
    # This would set up test database, etc.
    # For now, return mock setup
    yield {
        "db_ready": True,
        "memgraph_ready": True,
        "qdrant_ready": True,
    }
    # Cleanup
    pass


# ============================================================================
# Fixture Combinations
# ============================================================================


@pytest.fixture
def full_lineage_chain(parent_lineage_node, sample_lineage_node, child_lineage_node):
    """Create full lineage chain: parent -> sample -> child."""
    return {
        "parent": parent_lineage_node,
        "current": sample_lineage_node,
        "child": child_lineage_node,
    }


@pytest.fixture
def complete_metrics_set(
    sample_usage_metrics,
    sample_performance_metrics,
    sample_health_metrics,
    sample_trend_analysis,
):
    """Create complete set of metrics."""
    return {
        "usage": sample_usage_metrics,
        "performance": sample_performance_metrics,
        "health": sample_health_metrics,
        "trend": sample_trend_analysis,
    }


@pytest.fixture
def feedback_data_set(sample_feedback, sample_improvement):
    """Create complete feedback data set."""
    return {"feedback": sample_feedback, "improvement": sample_improvement}
