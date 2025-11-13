"""
Comprehensive Unit Tests for ManifestIntelligenceHandler

Tests for manifest intelligence handler covering:
- Event routing (can_handle)
- Event handling (handle_event)
- Parallel query execution
- Individual query methods (patterns, infrastructure, models, schemas, debug)
- Response publishing (completed/failed)
- Metrics tracking
- Error handling and graceful degradation
- HTTP client lifecycle management
- Shutdown procedures

Created: 2025-11-04
Purpose: Improve coverage from 0% to 70%+ for manifest_intelligence_handler.py
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from asyncpg.exceptions import UndefinedTableError
from handlers.manifest_intelligence_handler import ManifestIntelligenceHandler

# ==============================================================================
# Test Fixtures
# ==============================================================================


class MockEventEnvelope:
    """Mock event envelope for testing."""

    def __init__(
        self,
        event_type: str = "manifest_intelligence_requested",
        correlation_id: str = None,
        payload: Dict[str, Any] = None,
    ):
        self.event_type = event_type
        self.correlation_id = correlation_id or str(uuid4())
        self.payload = payload or {}


class MockQdrantCollection:
    """Mock Qdrant collection."""

    def __init__(self, name: str, points_count: int = 100):
        self.name = name
        self.points_count = points_count


class MockQdrantPoint:
    """Mock Qdrant point."""

    def __init__(self, point_id: str, payload: Dict[str, Any]):
        self.id = point_id
        self.payload = payload


@pytest.fixture
def mock_qdrant_client():
    """Mock AsyncQdrantClient."""
    client = AsyncMock()

    # Mock collections
    client.get_collections = AsyncMock(
        return_value=Mock(
            collections=[
                MockQdrantCollection("code_patterns", 100),
                MockQdrantCollection("pattern_embeddings", 50),
            ]
        )
    )

    # Mock collection info
    client.get_collection = AsyncMock(
        return_value=MockQdrantCollection("code_patterns", 100)
    )

    # Mock scroll results
    mock_points = [
        MockQdrantPoint(
            "pattern-1",
            {
                "name": "ONEX Effect Pattern",
                "file_path": "/path/to/pattern.py",
                "description": "Effect node pattern",
                "node_types": ["effect"],
                "confidence": 0.95,
                "use_cases": ["API calls", "Database queries"],
                "metadata": {"language": "python"},
            },
        ),
        MockQdrantPoint(
            "pattern-2",
            {
                "name": "ONEX Compute Pattern",
                "file_path": "/path/to/compute.py",
                "description": "Compute node pattern",
                "node_types": ["compute"],
                "confidence": 0.88,
                "use_cases": ["Data transformation"],
                "metadata": {"language": "python"},
            },
        ),
    ]
    client.scroll = AsyncMock(return_value=(mock_points, None))
    client.close = AsyncMock()

    return client


@pytest.fixture
def mock_infrastructure_result():
    """Mock infrastructure scan result."""
    result = Mock()
    result.postgresql = {"host": "localhost", "port": 5432, "status": "available"}
    result.kafka = {"brokers": ["localhost:9092"], "status": "available"}
    result.qdrant = {"url": "http://localhost:6333", "status": "available"}
    result.docker_services = [{"name": "archon-intelligence", "status": "running"}]
    result.query_time_ms = 250.0
    return result


@pytest.fixture
def mock_schema_result():
    """Mock schema discovery result."""
    result = Mock()
    result.tables = [
        {"name": "agent_routing_decisions", "columns": 15},
        {"name": "pattern_executions", "columns": 10},
    ]
    result.total_tables = 2
    result.query_time_ms = 150.0
    return result


@pytest.fixture
def handler():
    """Create ManifestIntelligenceHandler with mocked dependencies."""
    handler = ManifestIntelligenceHandler(
        postgres_url="postgresql://test:test@localhost:5432/testdb",
        qdrant_url="http://localhost:6333",
        embedding_model_url="http://localhost:8002",
        openai_api_key="sk-test-key",
    )

    # Mock router
    handler._router = AsyncMock()
    handler._router.publish = AsyncMock()
    handler._router_initialized = True

    return handler


# ==============================================================================
# Initialization Tests
# ==============================================================================


class TestInitialization:
    """Test handler initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default environment variables."""
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://localhost/testdb",
                "QDRANT_URL": "http://localhost:6333",
                "EMBEDDING_MODEL_URL": "http://localhost:8002",
                "OPENAI_API_KEY": "sk-test",
            },
        ):
            handler = ManifestIntelligenceHandler()

            assert handler.postgres_url == "postgresql://localhost/testdb"
            assert handler.qdrant_url == "http://localhost:6333"
            assert handler.embedding_model_url == "http://localhost:8002"
            assert handler.openai_api_key == "sk-test"
            assert handler.http_client is None
            assert handler.metrics["events_handled"] == 0
            assert handler.metrics["events_failed"] == 0

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        handler = ManifestIntelligenceHandler(
            postgres_url="postgresql://custom:5432/db",
            qdrant_url="http://custom:6333",
            embedding_model_url="http://custom:8002",
            openai_api_key="sk-custom",
        )

        assert handler.postgres_url == "postgresql://custom:5432/db"
        assert handler.qdrant_url == "http://custom:6333"
        assert handler.embedding_model_url == "http://custom:8002"
        assert handler.openai_api_key == "sk-custom"

    def test_init_metrics(self, handler):
        """Test metrics are initialized correctly."""
        assert "events_handled" in handler.metrics
        assert "events_failed" in handler.metrics
        assert "total_processing_time_ms" in handler.metrics
        assert "partial_results_count" in handler.metrics
        assert "full_results_count" in handler.metrics


# ==============================================================================
# HTTP Client Management Tests
# ==============================================================================


class TestHttpClientManagement:
    """Test HTTP client lifecycle management."""

    @pytest.mark.asyncio
    async def test_ensure_http_client_creates_client(self, handler):
        """Test HTTP client is created when needed."""
        assert handler.http_client is None
        await handler._ensure_http_client()
        assert handler.http_client is not None
        assert isinstance(handler.http_client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_ensure_http_client_reuses_existing(self, handler):
        """Test HTTP client is reused if already created."""
        await handler._ensure_http_client()
        first_client = handler.http_client
        await handler._ensure_http_client()
        assert handler.http_client is first_client

    @pytest.mark.asyncio
    async def test_close_http_client(self, handler):
        """Test HTTP client is closed properly."""
        await handler._ensure_http_client()
        assert handler.http_client is not None

        await handler._close_http_client()
        assert handler.http_client is None

    @pytest.mark.asyncio
    async def test_close_http_client_when_none(self, handler):
        """Test closing HTTP client when it doesn't exist."""
        assert handler.http_client is None
        await handler._close_http_client()
        assert handler.http_client is None


# ==============================================================================
# Event Routing Tests
# ==============================================================================


class TestEventRouting:
    """Test event type routing."""

    def test_can_handle_manifest_intelligence_requested(self, handler):
        """Test handler recognizes manifest_intelligence_requested event."""
        assert handler.can_handle("manifest_intelligence_requested") is True

    def test_can_handle_manifest_dot_intelligence_dot_requested(self, handler):
        """Test handler recognizes manifest.intelligence.requested event."""
        assert handler.can_handle("manifest.intelligence.requested") is True

    def test_can_handle_intelligence_dot_manifest_dot_requested(self, handler):
        """Test handler recognizes intelligence.manifest.requested event."""
        assert handler.can_handle("intelligence.manifest.requested") is True

    def test_can_handle_case_insensitive(self, handler):
        """Test handler is case-insensitive."""
        assert handler.can_handle("MANIFEST_INTELLIGENCE_REQUESTED") is True
        assert handler.can_handle("Manifest.Intelligence.Requested") is True

    def test_cannot_handle_unknown_event(self, handler):
        """Test handler rejects unknown events."""
        assert handler.can_handle("unknown.event.type") is False
        assert handler.can_handle("tree.index-project-requested") is False


# ==============================================================================
# Event Handling Tests
# ==============================================================================


class TestEventHandling:
    """Test event handling logic."""

    @pytest.mark.asyncio
    async def test_handle_event_success(self, handler):
        """Test successful event handling."""
        event = MockEventEnvelope(
            event_type="manifest_intelligence_requested",
            correlation_id=str(uuid4()),
            payload={"options": {}},
        )

        # Mock execute method
        handler.execute = AsyncMock(
            return_value={
                "patterns": {},
                "infrastructure": {},
                "models": {},
                "database_schemas": {},
                "debug_intelligence": {},
                "summary": {
                    "sections_succeeded": 5,
                    "sections_failed": 0,
                    "partial_results": False,
                    "query_time_ms": 500.0,
                },
                "warnings": [],
            }
        )

        success = await handler.handle_event(event)

        assert success is True
        assert handler.metrics["events_handled"] == 1
        assert handler.metrics["events_failed"] == 0
        assert handler.metrics["full_results_count"] == 1
        assert handler.metrics["partial_results_count"] == 0

    @pytest.mark.asyncio
    async def test_handle_event_partial_results(self, handler):
        """Test event handling with partial results."""
        event = MockEventEnvelope(
            event_type="manifest_intelligence_requested",
            payload={"options": {}},
        )

        # Mock execute with partial results
        handler.execute = AsyncMock(
            return_value={
                "patterns": {},
                "infrastructure": {},
                "models": {},
                "database_schemas": {},
                "debug_intelligence": {},
                "summary": {
                    "sections_succeeded": 3,
                    "sections_failed": 2,
                    "partial_results": True,
                    "query_time_ms": 500.0,
                },
                "warnings": [
                    "patterns section unavailable",
                    "models section unavailable",
                ],
            }
        )

        success = await handler.handle_event(event)

        assert success is True
        assert handler.metrics["partial_results_count"] == 1
        assert handler.metrics["full_results_count"] == 0

    @pytest.mark.asyncio
    async def test_handle_event_failure(self, handler):
        """Test event handling failure."""
        event = MockEventEnvelope(
            event_type="manifest_intelligence_requested",
            correlation_id=str(uuid4()),
            payload={"options": {}},
        )

        # Mock execute to raise exception
        handler.execute = AsyncMock(side_effect=Exception("Query failed"))

        success = await handler.handle_event(event)

        assert success is False
        assert handler.metrics["events_failed"] == 1

        # Verify failed event was published
        handler._router.publish.assert_called_once()
        call_args = handler._router.publish.call_args
        assert "manifest.failed" in call_args.kwargs["topic"]

    @pytest.mark.asyncio
    async def test_handle_event_extracts_options(self, handler):
        """Test event handling extracts options from payload."""
        event = MockEventEnvelope(
            event_type="manifest_intelligence_requested",
            payload={
                "options": {
                    "include_patterns": False,
                    "max_patterns": 50,
                }
            },
        )

        handler.execute = AsyncMock(
            return_value={
                "summary": {
                    "sections_succeeded": 5,
                    "sections_failed": 0,
                    "partial_results": False,
                },
                "warnings": [],
            }
        )

        await handler.handle_event(event)

        # Verify execute was called with correct options
        handler.execute.assert_called_once()
        call_args = handler.execute.call_args
        assert call_args.kwargs["options"]["include_patterns"] is False
        assert call_args.kwargs["options"]["max_patterns"] == 50


# ==============================================================================
# Execute Method Tests
# ==============================================================================


class TestExecuteMethod:
    """Test parallel query execution."""

    @pytest.mark.asyncio
    async def test_execute_all_sections_succeed(self, handler):
        """Test execute with all sections succeeding."""
        # Mock all query methods
        handler._query_patterns = AsyncMock(
            return_value={"patterns": [], "total_count": 0, "query_time_ms": 100.0}
        )
        handler._query_infrastructure = AsyncMock(
            return_value={"postgresql": {}, "kafka": {}, "query_time_ms": 150.0}
        )
        handler._query_models = AsyncMock(
            return_value={"ai_models": {"providers": []}, "query_time_ms": 120.0}
        )
        handler._query_database_schemas = AsyncMock(
            return_value={"tables": [], "total_tables": 0, "query_time_ms": 130.0}
        )
        handler._query_debug_intelligence = AsyncMock(
            return_value={"pattern_executions": [], "query_time_ms": 110.0}
        )

        result = await handler.execute(correlation_id="test-exec-123", options={})

        assert result["summary"]["sections_succeeded"] == 5
        assert result["summary"]["sections_failed"] == 0
        assert result["summary"]["partial_results"] is False
        assert len(result["warnings"]) == 0
        assert "query_time_ms" in result["summary"]

    @pytest.mark.asyncio
    async def test_execute_partial_results(self, handler):
        """Test execute with partial results (some queries fail)."""
        # Mock some queries to fail
        handler._query_patterns = AsyncMock(side_effect=Exception("Qdrant unavailable"))
        handler._query_infrastructure = AsyncMock(
            return_value={"postgresql": {}, "query_time_ms": 150.0}
        )
        handler._query_models = AsyncMock(side_effect=Exception("vLLM unavailable"))
        handler._query_database_schemas = AsyncMock(
            return_value={"tables": [], "query_time_ms": 130.0}
        )
        handler._query_debug_intelligence = AsyncMock(
            return_value={"pattern_executions": [], "query_time_ms": 110.0}
        )

        result = await handler.execute(correlation_id="test-partial", options={})

        assert result["summary"]["sections_succeeded"] == 3
        assert result["summary"]["sections_failed"] == 2
        assert result["summary"]["partial_results"] is True
        assert len(result["warnings"]) == 2
        assert any("patterns section unavailable" in w for w in result["warnings"])
        assert any("models section unavailable" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_execute_graceful_degradation(self, handler):
        """Test execute continues even if some queries fail."""
        # Simulate multiple failures
        handler._query_patterns = AsyncMock(side_effect=Exception("Error 1"))
        handler._query_infrastructure = AsyncMock(side_effect=Exception("Error 2"))
        handler._query_models = AsyncMock(side_effect=Exception("Error 3"))
        handler._query_database_schemas = AsyncMock(
            return_value={"tables": [], "query_time_ms": 100.0}
        )
        handler._query_debug_intelligence = AsyncMock(
            return_value={"pattern_executions": [], "query_time_ms": 100.0}
        )

        result = await handler.execute(correlation_id="test-degraded", options={})

        # Should still return result with available data
        assert result["summary"]["sections_succeeded"] == 2
        assert result["summary"]["sections_failed"] == 3
        assert result["summary"]["partial_results"] is True
        assert len(result["warnings"]) == 3


# ==============================================================================
# Query Patterns Tests
# ==============================================================================


class TestQueryPatterns:
    """Test _query_patterns method."""

    @pytest.mark.asyncio
    async def test_query_patterns_success(self, handler, mock_qdrant_client):
        """Test successful patterns query."""
        with patch(
            "handlers.manifest_intelligence_handler.AsyncQdrantClient",
            return_value=mock_qdrant_client,
        ):
            result = await handler._query_patterns(options={})

            assert "patterns" in result
            assert "total_count" in result
            assert "query_time_ms" in result
            # 2 collections x 2 patterns each = 4 total patterns
            assert len(result["patterns"]) == 4
            assert result["patterns"][0]["name"] == "ONEX Effect Pattern"

    @pytest.mark.asyncio
    async def test_query_patterns_disabled(self, handler):
        """Test patterns query when disabled."""
        result = await handler._query_patterns(options={"include_patterns": False})

        assert result["patterns"] == []
        assert result["total_count"] == 0
        assert result["query_time_ms"] == 0.0

    @pytest.mark.asyncio
    async def test_query_patterns_max_limit(self, handler, mock_qdrant_client):
        """Test patterns query respects max_patterns option."""
        with patch(
            "handlers.manifest_intelligence_handler.AsyncQdrantClient",
            return_value=mock_qdrant_client,
        ):
            await handler._query_patterns(options={"max_patterns": 50})

            # Verify scroll was called with correct limit
            mock_qdrant_client.scroll.assert_called()
            call_args = mock_qdrant_client.scroll.call_args
            assert call_args.kwargs["limit"] == 50

    @pytest.mark.asyncio
    async def test_query_patterns_failure(self, handler, mock_qdrant_client):
        """Test patterns query handles failures."""
        mock_qdrant_client.get_collections.side_effect = Exception("Qdrant error")

        with patch(
            "handlers.manifest_intelligence_handler.AsyncQdrantClient",
            return_value=mock_qdrant_client,
        ):
            with pytest.raises(Exception, match="Qdrant error"):
                await handler._query_patterns(options={})


# ==============================================================================
# Query Infrastructure Tests
# ==============================================================================


class TestQueryInfrastructure:
    """Test _query_infrastructure method."""

    @pytest.mark.asyncio
    async def test_query_infrastructure_success(
        self, handler, mock_infrastructure_result
    ):
        """Test successful infrastructure query."""
        handler.infrastructure_handler.execute = AsyncMock(
            return_value=mock_infrastructure_result
        )

        result = await handler._query_infrastructure(options={})

        assert "postgresql" in result
        assert "kafka" in result
        assert "docker_services" in result
        assert result["query_time_ms"] == 250.0

    @pytest.mark.asyncio
    async def test_query_infrastructure_disabled(self, handler):
        """Test infrastructure query when disabled."""
        result = await handler._query_infrastructure(
            options={"include_infrastructure": False}
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_query_infrastructure_failure(self, handler):
        """Test infrastructure query handles failures."""
        handler.infrastructure_handler.execute = AsyncMock(
            side_effect=Exception("Infrastructure error")
        )

        with pytest.raises(Exception, match="Infrastructure error"):
            await handler._query_infrastructure(options={})


# ==============================================================================
# Query Models Tests
# ==============================================================================


class TestQueryModels:
    """Test _query_models method."""

    @pytest.mark.asyncio
    async def test_query_models_vllm_available(self, handler):
        """Test models query with vLLM available."""
        # Mock HTTP client
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "Alibaba-NLP/gte-Qwen2-1.5B-instruct"},
                {"name": "BAAI/bge-large-en-v1.5"},
            ]
        }

        handler.http_client = AsyncMock()
        handler.http_client.get = AsyncMock(return_value=mock_response)

        result = await handler._query_models(options={})

        assert "ai_models" in result
        assert len(result["ai_models"]["providers"]) == 2

        # Check vLLM provider
        vllm_provider = next(
            p for p in result["ai_models"]["providers"] if p["name"] == "vLLM"
        )
        assert vllm_provider["status"] == "available"
        assert len(vllm_provider["models"]) == 2

    @pytest.mark.asyncio
    async def test_query_models_vllm_unavailable(self, handler):
        """Test models query when vLLM is unavailable."""
        handler.http_client = AsyncMock()
        handler.http_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        result = await handler._query_models(options={})

        vllm_provider = next(
            p for p in result["ai_models"]["providers"] if p["name"] == "vLLM"
        )
        assert vllm_provider["status"] == "unavailable"
        assert "error" in vllm_provider

    @pytest.mark.asyncio
    async def test_query_models_openai_configured(self, handler):
        """Test models query with OpenAI API key configured."""
        handler.openai_api_key = "sk-test-key"
        handler.http_client = AsyncMock()
        handler.http_client.get = AsyncMock(side_effect=Exception("vLLM error"))

        result = await handler._query_models(options={})

        openai_provider = next(
            p for p in result["ai_models"]["providers"] if p["name"] == "OpenAI"
        )
        assert openai_provider["status"] == "available"
        assert len(openai_provider["models"]) > 0

    @pytest.mark.asyncio
    async def test_query_models_openai_not_configured(self, handler):
        """Test models query when OpenAI API key not configured."""
        handler.openai_api_key = None
        handler.http_client = AsyncMock()
        handler.http_client.get = AsyncMock(side_effect=Exception("vLLM error"))

        result = await handler._query_models(options={})

        openai_provider = next(
            p for p in result["ai_models"]["providers"] if p["name"] == "OpenAI"
        )
        assert openai_provider["status"] == "not_configured"

    @pytest.mark.asyncio
    async def test_query_models_disabled(self, handler):
        """Test models query when disabled."""
        result = await handler._query_models(options={"include_models": False})

        assert result["ai_models"] == {}
        assert result["query_time_ms"] == 0.0


# ==============================================================================
# Query Database Schemas Tests
# ==============================================================================


class TestQueryDatabaseSchemas:
    """Test _query_database_schemas method."""

    @pytest.mark.asyncio
    async def test_query_database_schemas_success(self, handler, mock_schema_result):
        """Test successful database schemas query."""
        handler.schema_handler.execute = AsyncMock(return_value=mock_schema_result)

        result = await handler._query_database_schemas(options={})

        assert "tables" in result
        assert "total_tables" in result
        assert result["total_tables"] == 2
        assert len(result["tables"]) == 2

    @pytest.mark.asyncio
    async def test_query_database_schemas_disabled(self, handler):
        """Test database schemas query when disabled."""
        result = await handler._query_database_schemas(
            options={"include_database_schemas": False}
        )

        assert result["tables"] == []
        assert result["total_tables"] == 0

    @pytest.mark.asyncio
    async def test_query_database_schemas_failure(self, handler):
        """Test database schemas query handles failures."""
        handler.schema_handler.execute = AsyncMock(side_effect=Exception("DB error"))

        with pytest.raises(Exception, match="DB error"):
            await handler._query_database_schemas(options={})


# ==============================================================================
# Query Debug Intelligence Tests
# ==============================================================================


class TestQueryDebugIntelligence:
    """Test _query_debug_intelligence method."""

    @pytest.mark.asyncio
    async def test_query_debug_intelligence_success(self, handler):
        """Test successful debug intelligence query."""
        # Mock asyncpg connection
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "pattern_id": "pattern-1",
                    "execution_time_ms": 150.5,
                    "success": True,
                    "error_message": None,
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "pattern_id": "pattern-2",
                    "execution_time_ms": 250.0,
                    "success": False,
                    "error_message": "Timeout",
                    "created_at": datetime.now(timezone.utc),
                },
            ]
        )
        mock_conn.close = AsyncMock()

        with patch("asyncpg.connect", return_value=mock_conn):
            result = await handler._query_debug_intelligence(options={})

            assert "pattern_executions" in result
            assert "query_time_ms" in result
            assert len(result["pattern_executions"]) == 2
            assert result["pattern_executions"][0]["pattern_id"] == "pattern-1"
            assert result["pattern_executions"][1]["success"] is False

    @pytest.mark.asyncio
    async def test_query_debug_intelligence_table_not_exists(self, handler):
        """Test debug intelligence query when table doesn't exist."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=UndefinedTableError("Table not found"))
        mock_conn.close = AsyncMock()

        with patch("asyncpg.connect", return_value=mock_conn):
            result = await handler._query_debug_intelligence(options={})

            assert result["pattern_executions"] == []

    @pytest.mark.asyncio
    async def test_query_debug_intelligence_disabled(self, handler):
        """Test debug intelligence query when disabled."""
        result = await handler._query_debug_intelligence(
            options={"include_debug_intelligence": False}
        )

        assert result["pattern_executions"] == []
        assert result["query_time_ms"] == 0.0

    @pytest.mark.asyncio
    async def test_query_debug_intelligence_connection_failure(self, handler):
        """Test debug intelligence query handles connection failures."""
        with patch("asyncpg.connect", side_effect=Exception("Connection failed")):
            with pytest.raises(Exception, match="Connection failed"):
                await handler._query_debug_intelligence(options={})


# ==============================================================================
# Response Publishing Tests
# ==============================================================================


class TestResponsePublishing:
    """Test response publishing methods."""

    @pytest.mark.asyncio
    async def test_publish_manifest_intelligence_completed(self, handler):
        """Test publishing completed event."""
        correlation_id = str(uuid4())
        result = {
            "patterns": {},
            "summary": {"sections_succeeded": 5, "sections_failed": 0},
        }

        await handler._publish_manifest_intelligence_completed(
            correlation_id=correlation_id,
            result=result,
            processing_time_ms=500.0,
        )

        handler._router.publish.assert_called_once()
        call_args = handler._router.publish.call_args

        assert "manifest.completed" in call_args.kwargs["topic"]
        assert call_args.kwargs["key"] == correlation_id

    @pytest.mark.asyncio
    async def test_publish_manifest_intelligence_failed(self, handler):
        """Test publishing failed event."""
        correlation_id = str(uuid4())

        await handler._publish_manifest_intelligence_failed(
            correlation_id=correlation_id,
            error_message="Query timeout",
            processing_time_ms=1500.0,
        )

        handler._router.publish.assert_called_once()
        call_args = handler._router.publish.call_args

        assert "manifest.failed" in call_args.kwargs["topic"]
        assert call_args.kwargs["key"] == correlation_id

        # Verify error payload
        event = call_args.kwargs["event"]
        assert event.payload["error_message"] == "Query timeout"
        assert event.payload["retry_allowed"] is True

    @pytest.mark.asyncio
    async def test_publish_completed_with_uuid_correlation_id(self, handler):
        """Test publishing with UUID correlation ID."""
        correlation_id = uuid4()

        await handler._publish_manifest_intelligence_completed(
            correlation_id=str(correlation_id),
            result={},
            processing_time_ms=100.0,
        )

        handler._router.publish.assert_called_once()


# ==============================================================================
# Utility Methods Tests
# ==============================================================================


class TestUtilityMethods:
    """Test utility methods."""

    def test_get_handler_name(self, handler):
        """Test get_handler_name returns correct name."""
        assert handler.get_handler_name() == "ManifestIntelligenceHandler"

    def test_get_metrics_no_events(self, handler):
        """Test get_metrics with no events processed."""
        metrics = handler.get_metrics()

        assert metrics["events_handled"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_processing_time_ms"] == 0.0
        assert metrics["partial_results_rate"] == 0.0
        assert metrics["handler_name"] == "ManifestIntelligenceHandler"

    def test_get_metrics_with_events(self, handler):
        """Test get_metrics with processed events."""
        handler.metrics["events_handled"] = 10
        handler.metrics["events_failed"] = 2
        handler.metrics["total_processing_time_ms"] = 5000.0
        handler.metrics["partial_results_count"] = 3
        handler.metrics["full_results_count"] = 7

        metrics = handler.get_metrics()

        assert metrics["events_handled"] == 10
        assert metrics["events_failed"] == 2
        assert metrics["success_rate"] == 10 / 12  # 10 handled out of 12 total
        assert metrics["avg_processing_time_ms"] == 500.0  # 5000 / 10
        assert metrics["partial_results_rate"] == 0.3  # 3 / 10

    @pytest.mark.asyncio
    async def test_shutdown(self, handler):
        """Test shutdown closes resources."""
        # Create HTTP client
        await handler._ensure_http_client()
        assert handler.http_client is not None

        # Shutdown
        await handler.shutdown()

        # Verify HTTP client closed
        assert handler.http_client is None


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_full_event_lifecycle_success(self, handler):
        """Test complete event lifecycle from receipt to response."""
        # Mock all query methods
        handler._query_patterns = AsyncMock(
            return_value={"patterns": [], "total_count": 0, "query_time_ms": 100.0}
        )
        handler._query_infrastructure = AsyncMock(
            return_value={"postgresql": {}, "query_time_ms": 150.0}
        )
        handler._query_models = AsyncMock(
            return_value={"ai_models": {"providers": []}, "query_time_ms": 120.0}
        )
        handler._query_database_schemas = AsyncMock(
            return_value={"tables": [], "query_time_ms": 130.0}
        )
        handler._query_debug_intelligence = AsyncMock(
            return_value={"pattern_executions": [], "query_time_ms": 110.0}
        )

        event = MockEventEnvelope(
            event_type="manifest_intelligence_requested",
            correlation_id=str(uuid4()),
            payload={"options": {}},
        )

        success = await handler.handle_event(event)

        assert success is True
        assert handler.metrics["events_handled"] == 1
        assert handler._router.publish.called

    @pytest.mark.asyncio
    async def test_performance_tracking(self, handler):
        """Test performance metrics are tracked correctly."""
        handler.execute = AsyncMock(
            return_value={
                "summary": {
                    "sections_succeeded": 5,
                    "sections_failed": 0,
                    "partial_results": False,
                },
                "warnings": [],
            }
        )

        event = MockEventEnvelope(payload={"options": {}})

        await handler.handle_event(event)

        assert handler.metrics["total_processing_time_ms"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
