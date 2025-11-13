#!/usr/bin/env python3
"""
Index Sample ONEX Patterns to Qdrant

Populates the execution_patterns collection with real ONEX patterns from the
Archon codebase for pattern discovery and code generation.

Configuration:
    Uses centralized config from config/settings.py
    Override with environment variables (QDRANT_URL, EMBEDDING_MODEL_URL, etc.)

Usage:
    python3 scripts/index_sample_patterns.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from uuid import uuid4

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import centralized configuration
from config import settings

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "intelligence"))

from src.services.pattern_learning.phase1_foundation.storage.model_contract_vector_index import (
    ModelContractVectorIndexEffect,
    ModelVectorIndexPoint,
)
from src.services.pattern_learning.phase1_foundation.storage.node_qdrant_vector_index_effect import (
    NodeQdrantVectorIndexEffect,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Sample ONEX patterns from the Archon codebase
SAMPLE_PATTERNS = [
    {
        "pattern_name": "Qdrant Vector Index Effect",
        "node_type": "effect",
        "description": "Vector indexing effect node for embedding generation and Qdrant storage with HNSW optimization",
        "file_path": "src/services/pattern_learning/phase1_foundation/storage/node_qdrant_vector_index_effect.py",
        "complexity": "high",
        "mixins": ["TransactionManager"],
        "contracts": [
            "ModelContractVectorIndexEffect",
            "ModelContractVectorSearchEffect",
        ],
        "code_examples": [
            "async def execute_effect()",
            "await self._ensure_collection_exists()",
        ],
        "use_cases": ["pattern indexing", "vector search", "embedding generation"],
        "confidence": 0.95,
    },
    {
        "pattern_name": "Pattern Similarity Scorer",
        "node_type": "compute",
        "description": "Compute node for calculating similarity scores between patterns using multiple algorithms",
        "file_path": "src/services/pattern_learning/phase2_matching/node_pattern_similarity_compute.py",
        "complexity": "moderate",
        "mixins": [],
        "contracts": ["ModelContractPatternSimilarity"],
        "code_examples": ["async def execute_compute()", "def _calculate_similarity()"],
        "use_cases": ["pattern matching", "similarity scoring", "fuzzy matching"],
        "confidence": 0.90,
    },
    {
        "pattern_name": "Hybrid Scorer",
        "node_type": "compute",
        "description": "Hybrid scoring compute node combining vector similarity, keyword matching, and metadata scoring",
        "file_path": "src/services/pattern_learning/phase2_matching/node_hybrid_scorer_compute.py",
        "complexity": "moderate",
        "mixins": [],
        "contracts": ["ModelContractHybridScore"],
        "code_examples": [
            "async def execute_compute()",
            "def _calculate_weighted_score()",
        ],
        "use_cases": ["pattern ranking", "multi-signal scoring", "relevance scoring"],
        "confidence": 0.88,
    },
    {
        "pattern_name": "Semantic Cache Reducer",
        "node_type": "reducer",
        "description": "Reducer node for semantic caching with Redis and embedding-based key matching",
        "file_path": "src/services/pattern_learning/phase2_matching/reducer_semantic_cache.py",
        "complexity": "high",
        "mixins": ["CachingMixin"],
        "contracts": ["ModelContractSemanticCache"],
        "code_examples": [
            "async def execute_reduction()",
            "await self._find_similar_cached()",
        ],
        "use_cases": [
            "semantic caching",
            "cache invalidation",
            "similarity-based retrieval",
        ],
        "confidence": 0.92,
    },
    {
        "pattern_name": "Intelligence Adapter Handler",
        "node_type": "orchestrator",
        "description": "Orchestrator for handling intelligence adapter requests and coordinating operation handlers",
        "file_path": "src/handlers/intelligence_adapter_handler.py",
        "complexity": "high",
        "mixins": ["EventBusMixin", "ErrorHandlingMixin"],
        "contracts": ["ModelEventEnvelope", "ModelIntelligenceRequest"],
        "code_examples": [
            "async def process_event()",
            "await self._route_to_handler()",
        ],
        "use_cases": ["event routing", "handler coordination", "request processing"],
        "confidence": 0.93,
    },
    {
        "pattern_name": "Pattern Extraction Handler",
        "node_type": "effect",
        "description": "Effect node for extracting code generation patterns from Qdrant vector database",
        "file_path": "src/handlers/operations/pattern_extraction_handler.py",
        "complexity": "moderate",
        "mixins": [],
        "contracts": ["ModelPatternExtractionPayload"],
        "code_examples": ["async def execute()", "await client.scroll()"],
        "use_cases": ["pattern discovery", "code generation", "vector search"],
        "confidence": 0.90,
    },
    {
        "pattern_name": "Schema Discovery Handler",
        "node_type": "effect",
        "description": "Effect node for discovering PostgreSQL database schemas and table structures",
        "file_path": "src/handlers/operations/schema_discovery_handler.py",
        "complexity": "moderate",
        "mixins": [],
        "contracts": ["ModelSchemaDiscoveryPayload"],
        "code_examples": ["async def execute()", "await self._get_tables()"],
        "use_cases": [
            "schema discovery",
            "database introspection",
            "metadata extraction",
        ],
        "confidence": 0.91,
    },
    {
        "pattern_name": "Infrastructure Scan Handler",
        "node_type": "orchestrator",
        "description": "Orchestrator for scanning infrastructure (PostgreSQL, Kafka, Qdrant, Docker) in parallel",
        "file_path": "src/handlers/operations/infrastructure_scan_handler.py",
        "complexity": "high",
        "mixins": ["ErrorHandlingMixin"],
        "contracts": ["ModelInfrastructureScanPayload"],
        "code_examples": ["async def execute()", "await asyncio.gather()"],
        "use_cases": ["infrastructure discovery", "topology mapping", "health checks"],
        "confidence": 0.89,
    },
    {
        "pattern_name": "Event Bus Producer Effect",
        "node_type": "effect",
        "description": "Effect node for publishing events to Kafka/Redpanda event bus",
        "file_path": "services/bridge/src/core/event_publisher.py",
        "complexity": "moderate",
        "mixins": ["RetryMixin", "CircuitBreakerMixin"],
        "contracts": ["ModelEventEnvelope"],
        "code_examples": [
            "async def publish_event()",
            "await producer.send_and_wait()",
        ],
        "use_cases": [
            "event publishing",
            "async messaging",
            "event-driven architecture",
        ],
        "confidence": 0.94,
    },
    {
        "pattern_name": "Tree Discovery Processor",
        "node_type": "orchestrator",
        "description": "Orchestrator for discovering filesystem trees and coordinating stamping operations",
        "file_path": "services/bridge/src/handlers/tree_discovery_handler.py",
        "complexity": "high",
        "mixins": ["WorkflowMixin", "MetricsMixin"],
        "contracts": ["ModelTreeDiscoveryPayload"],
        "code_examples": ["async def process_event()", "await self._discover_tree()"],
        "use_cases": [
            "filesystem discovery",
            "tree traversal",
            "file metadata extraction",
        ],
        "confidence": 0.87,
    },
    # Observability & Monitoring Patterns
    {
        "pattern_name": "Health Monitoring Effect",
        "node_type": "effect",
        "description": "Effect node for health check monitoring, service status tracking, and availability diagnostics with alerting capabilities",
        "file_path": "src/monitoring/node_health_monitor_effect.py",
        "complexity": "moderate",
        "mixins": ["HealthCheckMixin", "AlertingMixin"],
        "contracts": ["ModelContractHealthCheck"],
        "code_examples": [
            "async def check_health()",
            "await self._monitor_dependencies()",
        ],
        "use_cases": [
            "health monitoring",
            "service diagnostics",
            "availability tracking",
            "uptime monitoring",
        ],
        "confidence": 0.92,
    },
    {
        "pattern_name": "Metrics Collection Reducer",
        "node_type": "reducer",
        "description": "Reducer node for aggregating performance metrics, execution statistics, and operational telemetry data",
        "file_path": "src/monitoring/node_metrics_collector_reducer.py",
        "complexity": "moderate",
        "mixins": ["MetricsAggregationMixin"],
        "contracts": ["ModelContractMetrics"],
        "code_examples": [
            "async def aggregate_metrics()",
            "def _calculate_percentiles()",
        ],
        "use_cases": [
            "metrics collection",
            "performance tracking",
            "telemetry aggregation",
            "statistics analysis",
        ],
        "confidence": 0.91,
    },
    {
        "pattern_name": "Error Tracking Effect",
        "node_type": "effect",
        "description": "Effect node for error tracking, exception logging, diagnostics data collection, and failure analysis",
        "file_path": "src/observability/node_error_tracker_effect.py",
        "complexity": "moderate",
        "mixins": ["ErrorCaptureMixin", "StackTraceMixin"],
        "contracts": ["ModelContractErrorTracking"],
        "code_examples": ["async def track_error()", "await self._capture_context()"],
        "use_cases": [
            "error tracking",
            "exception handling",
            "diagnostics",
            "failure analysis",
            "debugging",
        ],
        "confidence": 0.90,
    },
    {
        "pattern_name": "Performance Profiler Compute",
        "node_type": "compute",
        "description": "Compute node for performance profiling, execution time analysis, resource usage tracking, and bottleneck detection",
        "file_path": "src/observability/node_performance_profiler_compute.py",
        "complexity": "high",
        "mixins": ["ProfilingMixin", "TimingMixin"],
        "contracts": ["ModelContractPerformanceProfile"],
        "code_examples": [
            "async def profile_execution()",
            "def _analyze_bottlenecks()",
        ],
        "use_cases": [
            "performance profiling",
            "execution analysis",
            "resource monitoring",
            "optimization",
        ],
        "confidence": 0.89,
    },
    {
        "pattern_name": "Agent Execution Tracker",
        "node_type": "effect",
        "description": "Effect node for tracking agent execution lifecycle, decision history, and workflow state persistence",
        "file_path": "src/agents/node_execution_tracker_effect.py",
        "complexity": "moderate",
        "mixins": ["StatePersistenceMixin", "AuditMixin"],
        "contracts": ["ModelContractAgentExecution"],
        "code_examples": ["async def track_execution()", "await self._persist_state()"],
        "use_cases": [
            "agent monitoring",
            "execution tracking",
            "decision logging",
            "audit trail",
        ],
        "confidence": 0.93,
    },
    # Database & Implementation Patterns
    {
        "pattern_name": "PostgreSQL Query Optimizer",
        "node_type": "compute",
        "description": "Compute node for PostgreSQL query optimization, execution plan analysis, and performance tuning recommendations",
        "file_path": "src/database/node_postgres_optimizer_compute.py",
        "complexity": "high",
        "mixins": ["QueryAnalysisMixin"],
        "contracts": ["ModelContractQueryOptimization"],
        "code_examples": ["async def analyze_query()", "def _suggest_indexes()"],
        "use_cases": [
            "query optimization",
            "database performance",
            "PostgreSQL tuning",
            "index recommendations",
        ],
        "confidence": 0.88,
    },
    {
        "pattern_name": "Database Connection Pool Effect",
        "node_type": "effect",
        "description": "Effect node for managing PostgreSQL connection pooling, transaction management, and resource lifecycle",
        "file_path": "src/database/node_connection_pool_effect.py",
        "complexity": "moderate",
        "mixins": ["ConnectionPoolMixin", "TransactionMixin"],
        "contracts": ["ModelContractDatabaseConnection"],
        "code_examples": ["async def get_connection()", "await self._manage_pool()"],
        "use_cases": [
            "connection pooling",
            "resource management",
            "database connections",
            "transaction handling",
        ],
        "confidence": 0.91,
    },
    {
        "pattern_name": "Metrics Persistence Effect",
        "node_type": "effect",
        "description": "Effect node for persisting metrics data to PostgreSQL with time-series optimization and retention policies",
        "file_path": "src/observability/node_metrics_persistence_effect.py",
        "complexity": "moderate",
        "mixins": ["TimeSeriesMixin", "RetentionPolicyMixin"],
        "contracts": ["ModelContractMetricsPersistence"],
        "code_examples": [
            "async def persist_metrics()",
            "await self._apply_retention()",
        ],
        "use_cases": [
            "metrics storage",
            "time-series data",
            "data retention",
            "PostgreSQL persistence",
        ],
        "confidence": 0.90,
    },
    {
        "pattern_name": "Observability Dashboard Orchestrator",
        "node_type": "orchestrator",
        "description": "Orchestrator for coordinating observability data collection, aggregation, and dashboard visualization",
        "file_path": "src/observability/node_dashboard_orchestrator.py",
        "complexity": "high",
        "mixins": ["DataAggregationMixin", "VisualizationMixin"],
        "contracts": ["ModelContractObservabilityDashboard"],
        "code_examples": [
            "async def orchestrate_dashboard()",
            "await self._aggregate_data()",
        ],
        "use_cases": [
            "dashboard coordination",
            "data aggregation",
            "observability visualization",
            "monitoring",
        ],
        "confidence": 0.87,
    },
]


async def index_patterns():
    """Index sample ONEX patterns to Qdrant."""
    try:
        # Initialize vector index (from centralized config with environment overrides)
        logger.info("Initializing Qdrant vector index...")
        qdrant_url = os.getenv("QDRANT_URL", settings.qdrant_url)
        embedding_model_url = os.getenv(
            "EMBEDDING_MODEL_URL", "http://192.168.86.201:8002"
        )

        vector_index = NodeQdrantVectorIndexEffect(
            qdrant_url=qdrant_url,
            embedding_model_url=embedding_model_url,
        )

        # Prepare points for indexing
        logger.info(f"Preparing {len(SAMPLE_PATTERNS)} sample patterns for indexing...")
        points = []

        for pattern in SAMPLE_PATTERNS:
            # Create search text (what will be embedded)
            search_text = (
                f"{pattern['pattern_name']}: {pattern['description']}. "
                f"Node type: {pattern['node_type']}. "
                f"Use cases: {', '.join(pattern['use_cases'])}. "
                f"Complexity: {pattern['complexity']}."
            )

            # Create point
            point = ModelVectorIndexPoint(
                id=uuid4(),
                payload={
                    "text": search_text,
                    "pattern_name": pattern["pattern_name"],
                    "node_type": pattern["node_type"],
                    "description": pattern["description"],
                    "file_path": pattern["file_path"],
                    "complexity": pattern["complexity"],
                    "mixins": pattern["mixins"],
                    "contracts": pattern["contracts"],
                    "code_examples": pattern["code_examples"],
                    "use_cases": pattern["use_cases"],
                    "confidence": pattern["confidence"],
                    "timestamp": "2025-10-26T00:00:00Z",
                },
            )
            points.append(point)

        # Create index contract
        contract = ModelContractVectorIndexEffect(
            collection_name="execution_patterns",
            points=points,
        )

        # Execute indexing
        logger.info("Indexing patterns to Qdrant (this may take 30-60 seconds)...")
        result = await vector_index.execute_effect(contract)

        logger.info(
            f"✅ Successfully indexed {result.indexed_count} patterns in {result.duration_ms:.2f}ms"
        )
        logger.info(f"   Collection: {result.collection_name}")
        logger.info(
            f"   Points per second: {result.indexed_count / (result.duration_ms / 1000):.2f}"
        )

        # Verify indexing
        logger.info("\nVerifying indexed patterns...")
        from src.services.pattern_learning.phase1_foundation.storage.model_contract_vector_index import (
            ModelContractVectorSearchEffect,
        )

        search_contract = ModelContractVectorSearchEffect(
            collection_name="execution_patterns",
            query_text="effect node for database operations",
            limit=3,
            score_threshold=0.5,
        )

        search_result = await vector_index.search_similar(search_contract)
        logger.info(
            f"✅ Search verification: found {search_result.total_results} results"
        )

        for hit in search_result.hits[:3]:
            logger.info(
                f"   - {hit.payload.get('pattern_name')} (score: {hit.score:.3f})"
            )

        # Cleanup
        await vector_index.close()

        logger.info("\n✅ Pattern indexing complete!")
        return 0

    except Exception as e:
        logger.error(f"❌ Pattern indexing failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(index_patterns())
    sys.exit(exit_code)
