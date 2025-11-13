"""
Unit Tests: Pattern Storage Effect Node

Purpose: Comprehensive test coverage for pattern storage CRUD operations
Target: >90% code coverage with performance validation (<50ms queries)
Track: Track 3-1.2 - PostgreSQL Storage Layer

Test Categories:
- Contract validation
- Insert operations
- Update operations
- Delete operations
- Batch operations
- Error handling
- Performance benchmarks
- Correlation ID tracking
"""

import asyncio
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

from .model_contract_pattern_storage import ModelContractPatternStorage
from .node_pattern_storage_effect import NodePatternStorageEffect

# ============================================================================
# Test Configuration
# ============================================================================

# Test-only credential - use TRACEABILITY_DB_URL_EXTERNAL env var in production
DATABASE_URL = os.getenv(
    "TRACEABILITY_DB_URL_EXTERNAL",
    "postgresql://postgres:test_password_for_local_dev_only@localhost:5436/omninode_bridge",
)

# Performance thresholds
MAX_QUERY_TIME_MS = 50  # Maximum query execution time
MAX_BATCH_TIME_MS = 100  # Maximum batch operation time (10 patterns)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_pool():
    """Create database connection pool for tests."""
    if not ASYNCPG_AVAILABLE:
        pytest.skip("AsyncPG not available")

    pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=2, max_size=10, command_timeout=60
    )

    yield pool

    await pool.close()


@pytest.fixture
async def storage_node(db_pool):
    """Create pattern storage node instance."""
    return NodePatternStorageEffect(db_pool)


@pytest.fixture
async def cleanup_patterns(db_pool):
    """Cleanup test patterns after each test."""
    test_pattern_names = []

    yield test_pattern_names

    # Cleanup after test
    if test_pattern_names:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM pattern_templates
                WHERE pattern_name = ANY($1::text[])
                """,
                test_pattern_names,
            )


# ============================================================================
# Contract Validation Tests
# ============================================================================


class TestContractValidation:
    """Test contract model validation."""

    def test_insert_contract_valid(self):
        """Test valid insert contract creation."""
        contract = ModelContractPatternStorage(
            name="test_insert",
            operation="insert",
            data={
                "pattern_name": "TestPattern",
                "pattern_type": "code",
                "language": "python",
                "template_code": "def test(): pass",
            },
        )

        assert contract.operation == "insert"
        assert contract.name == "test_insert"
        assert isinstance(contract.correlation_id, UUID)

    def test_insert_contract_missing_required_fields(self):
        """Test insert contract validation with missing fields."""
        with pytest.raises(ValueError, match="missing required fields"):
            ModelContractPatternStorage(
                name="test_insert",
                operation="insert",
                data={
                    "pattern_name": "TestPattern"
                    # Missing: pattern_type, language, template_code
                },
            )

    def test_update_contract_valid(self):
        """Test valid update contract creation."""
        contract = ModelContractPatternStorage(
            name="test_update",
            operation="update",
            pattern_id=uuid4(),
            data={"confidence_score": 0.95},
        )

        assert contract.operation == "update"
        assert contract.pattern_id is not None

    def test_update_contract_missing_pattern_id(self):
        """Test update contract validation without pattern_id."""
        with pytest.raises(ValueError, match="requires 'pattern_id'"):
            ModelContractPatternStorage(
                name="test_update", operation="update", data={"confidence_score": 0.95}
            )

    def test_delete_contract_valid(self):
        """Test valid delete contract creation."""
        contract = ModelContractPatternStorage(
            name="test_delete", operation="delete", pattern_id=uuid4()
        )

        assert contract.operation == "delete"
        assert contract.pattern_id is not None

    def test_batch_insert_contract_valid(self):
        """Test valid batch insert contract creation."""
        contract = ModelContractPatternStorage(
            name="test_batch",
            operation="batch_insert",
            patterns=[
                {
                    "pattern_name": "Pattern1",
                    "pattern_type": "code",
                    "language": "python",
                    "template_code": "code1",
                },
                {
                    "pattern_name": "Pattern2",
                    "pattern_type": "code",
                    "language": "python",
                    "template_code": "code2",
                },
            ],
        )

        assert contract.operation == "batch_insert"
        assert len(contract.patterns) == 2


# ============================================================================
# Insert Operation Tests
# ============================================================================


class TestInsertOperations:
    """Test pattern insertion operations."""

    @pytest.mark.asyncio
    async def test_insert_pattern_success(self, storage_node, cleanup_patterns):
        """Test successful pattern insertion."""
        pattern_name = f"TestPattern_{uuid4().hex[:8]}"
        cleanup_patterns.append(pattern_name)

        contract = ModelContractPatternStorage(
            name="test_insert",
            operation="insert",
            data={
                "pattern_name": pattern_name,
                "pattern_type": "code",
                "language": "python",
                "category": "testing",
                "template_code": "async def execute_effect(self, contract): pass",
                "description": "Test pattern for unit tests",
                "confidence_score": 0.92,
                "tags": ["test", "onex"],
                "context": {"test": True},
            },
        )

        start_time = datetime.now(timezone.utc)
        result = await storage_node.execute_effect(contract)
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Validate result
        assert result.success is True
        assert result.data is not None
        assert "pattern_id" in result.data
        assert result.data["pattern_name"] == pattern_name
        assert "created_at" in result.data

        # Validate metadata
        assert result.metadata["operation"] == "insert"
        assert "correlation_id" in result.metadata
        assert "duration_ms" in result.metadata

        # Validate performance
        assert (
            duration_ms < MAX_QUERY_TIME_MS
        ), f"Query took {duration_ms}ms (limit: {MAX_QUERY_TIME_MS}ms)"

    @pytest.mark.asyncio
    async def test_insert_pattern_duplicate(self, storage_node, cleanup_patterns):
        """Test inserting duplicate pattern (unique violation)."""
        pattern_name = f"DuplicatePattern_{uuid4().hex[:8]}"
        cleanup_patterns.append(pattern_name)

        contract = ModelContractPatternStorage(
            name="test_insert",
            operation="insert",
            data={
                "pattern_name": pattern_name,
                "pattern_type": "code",
                "language": "python",
                "template_code": "def test(): pass",
            },
        )

        # First insert should succeed
        result1 = await storage_node.execute_effect(contract)
        assert result1.success is True

        # Second insert should fail with unique violation
        result2 = await storage_node.execute_effect(contract)
        assert result2.success is False
        assert "already exists" in result2.error.lower()
        assert result2.metadata["error_type"] == "unique_violation"

    @pytest.mark.asyncio
    async def test_insert_pattern_minimal_data(self, storage_node, cleanup_patterns):
        """Test inserting pattern with only required fields."""
        pattern_name = f"MinimalPattern_{uuid4().hex[:8]}"
        cleanup_patterns.append(pattern_name)

        contract = ModelContractPatternStorage(
            name="test_insert_minimal",
            operation="insert",
            data={
                "pattern_name": pattern_name,
                "pattern_type": "code",
                "language": "python",
                "template_code": "pass",
            },
        )

        result = await storage_node.execute_effect(contract)

        assert result.success is True
        assert result.data["pattern_name"] == pattern_name


# ============================================================================
# Update Operation Tests
# ============================================================================


class TestUpdateOperations:
    """Test pattern update operations."""

    @pytest.mark.asyncio
    async def test_update_pattern_success(self, storage_node, cleanup_patterns):
        """Test successful pattern update."""
        # First insert a pattern
        pattern_name = f"UpdateTestPattern_{uuid4().hex[:8]}"
        cleanup_patterns.append(pattern_name)

        insert_contract = ModelContractPatternStorage(
            name="test_insert",
            operation="insert",
            data={
                "pattern_name": pattern_name,
                "pattern_type": "code",
                "language": "python",
                "template_code": "original code",
                "confidence_score": 0.5,
            },
        )

        insert_result = await storage_node.execute_effect(insert_contract)
        assert insert_result.success is True
        pattern_id = UUID(insert_result.data["pattern_id"])

        # Now update it
        update_contract = ModelContractPatternStorage(
            name="test_update",
            operation="update",
            pattern_id=pattern_id,
            data={
                "confidence_score": 0.95,
                "usage_count": 42,
                "description": "Updated description",
            },
        )

        start_time = datetime.now(timezone.utc)
        result = await storage_node.execute_effect(update_contract)
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Validate result
        assert result.success is True
        assert result.data["pattern_id"] == str(pattern_id)
        assert result.data["pattern_name"] == pattern_name
        assert "updated_at" in result.data
        assert set(result.data["fields_updated"]) == {
            "confidence_score",
            "usage_count",
            "description",
        }

        # Validate performance
        assert duration_ms < MAX_QUERY_TIME_MS

    @pytest.mark.asyncio
    async def test_update_pattern_not_found(self, storage_node):
        """Test updating non-existent pattern."""
        fake_id = uuid4()

        contract = ModelContractPatternStorage(
            name="test_update",
            operation="update",
            pattern_id=fake_id,
            data={"confidence_score": 0.95},
        )

        result = await storage_node.execute_effect(contract)

        assert result.success is False
        assert "not found" in result.error.lower()
        assert result.metadata["error_type"] == "validation_error"

    @pytest.mark.asyncio
    async def test_update_pattern_with_context(self, storage_node, cleanup_patterns):
        """Test updating pattern with JSONB context field."""
        pattern_name = f"ContextUpdatePattern_{uuid4().hex[:8]}"
        cleanup_patterns.append(pattern_name)

        # Insert pattern
        insert_contract = ModelContractPatternStorage(
            name="test_insert",
            operation="insert",
            data={
                "pattern_name": pattern_name,
                "pattern_type": "code",
                "language": "python",
                "template_code": "code",
                "context": {"version": "1.0"},
            },
        )

        insert_result = await storage_node.execute_effect(insert_contract)
        pattern_id = UUID(insert_result.data["pattern_id"])

        # Update with new context
        update_contract = ModelContractPatternStorage(
            name="test_update",
            operation="update",
            pattern_id=pattern_id,
            data={"context": {"version": "2.0", "new_field": "value"}},
        )

        result = await storage_node.execute_effect(update_contract)

        assert result.success is True


# ============================================================================
# Delete Operation Tests
# ============================================================================


class TestDeleteOperations:
    """Test pattern deletion operations."""

    @pytest.mark.asyncio
    async def test_delete_pattern_success(self, storage_node, cleanup_patterns):
        """Test successful pattern deletion."""
        # Insert pattern
        pattern_name = f"DeleteTestPattern_{uuid4().hex[:8]}"

        insert_contract = ModelContractPatternStorage(
            name="test_insert",
            operation="insert",
            data={
                "pattern_name": pattern_name,
                "pattern_type": "code",
                "language": "python",
                "template_code": "code",
            },
        )

        insert_result = await storage_node.execute_effect(insert_contract)
        pattern_id = UUID(insert_result.data["pattern_id"])

        # Delete pattern
        delete_contract = ModelContractPatternStorage(
            name="test_delete", operation="delete", pattern_id=pattern_id
        )

        start_time = datetime.now(timezone.utc)
        result = await storage_node.execute_effect(delete_contract)
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Validate result
        assert result.success is True
        assert result.data["pattern_id"] == str(pattern_id)
        assert result.data["pattern_name"] == pattern_name
        assert result.data["deleted"] is True

        # Validate performance
        assert duration_ms < MAX_QUERY_TIME_MS

        # Verify pattern is actually deleted
        delete_again = await storage_node.execute_effect(delete_contract)
        assert delete_again.success is False

    @pytest.mark.asyncio
    async def test_delete_pattern_not_found(self, storage_node):
        """Test deleting non-existent pattern."""
        fake_id = uuid4()

        contract = ModelContractPatternStorage(
            name="test_delete", operation="delete", pattern_id=fake_id
        )

        result = await storage_node.execute_effect(contract)

        assert result.success is False
        assert "not found" in result.error.lower()


# ============================================================================
# Batch Operation Tests
# ============================================================================


class TestBatchOperations:
    """Test batch pattern operations."""

    @pytest.mark.asyncio
    async def test_batch_insert_success(self, storage_node, cleanup_patterns):
        """Test successful batch pattern insertion."""
        pattern_names = [f"BatchPattern{i}_{uuid4().hex[:8]}" for i in range(10)]
        cleanup_patterns.extend(pattern_names)

        contract = ModelContractPatternStorage(
            name="test_batch_insert",
            operation="batch_insert",
            patterns=[
                {
                    "pattern_name": name,
                    "pattern_type": "code",
                    "language": "python",
                    "template_code": f"code for {name}",
                    "confidence_score": 0.8 + (i * 0.01),
                }
                for i, name in enumerate(pattern_names)
            ],
        )

        start_time = datetime.now(timezone.utc)
        result = await storage_node.execute_effect(contract)
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Validate result
        assert result.success is True
        assert result.data["count"] == 10
        assert len(result.data["pattern_ids"]) == 10
        assert len(result.data["pattern_names"]) == 10
        assert result.data["batch_success"] is True

        # Validate performance (10 patterns should complete in <100ms)
        assert (
            duration_ms < MAX_BATCH_TIME_MS
        ), f"Batch took {duration_ms}ms (limit: {MAX_BATCH_TIME_MS}ms)"

    @pytest.mark.asyncio
    async def test_batch_insert_partial_failure(self, storage_node, cleanup_patterns):
        """Test batch insert with one invalid pattern (transaction rollback)."""
        pattern_names = [f"FailBatchPattern{i}_{uuid4().hex[:8]}" for i in range(3)]
        cleanup_patterns.extend(pattern_names)

        # Create batch with one duplicate pattern in the middle
        contract = ModelContractPatternStorage(
            name="test_batch_fail",
            operation="batch_insert",
            patterns=[
                {
                    "pattern_name": pattern_names[0],
                    "pattern_type": "code",
                    "language": "python",
                    "template_code": "code1",
                },
                {
                    "pattern_name": pattern_names[0],  # Duplicate!
                    "pattern_type": "code",
                    "language": "python",
                    "template_code": "code2",
                },
                {
                    "pattern_name": pattern_names[2],
                    "pattern_type": "code",
                    "language": "python",
                    "template_code": "code3",
                },
            ],
        )

        result = await storage_node.execute_effect(contract)

        # Should fail due to duplicate
        assert result.success is False
        assert "failed at pattern" in result.error.lower()


# ============================================================================
# Performance Benchmark Tests
# ============================================================================


class TestPerformance:
    """Performance benchmark tests."""

    @pytest.mark.asyncio
    async def test_insert_performance_benchmark(self, storage_node, cleanup_patterns):
        """Benchmark insert performance (<50ms)."""
        pattern_name = f"PerfTestPattern_{uuid4().hex[:8]}"
        cleanup_patterns.append(pattern_name)

        contract = ModelContractPatternStorage(
            name="perf_insert",
            operation="insert",
            data={
                "pattern_name": pattern_name,
                "pattern_type": "code",
                "language": "python",
                "template_code": "def test(): pass",
                "confidence_score": 0.9,
            },
        )

        # Measure multiple runs
        durations = []
        for _ in range(5):
            start = datetime.now(timezone.utc)
            result = await storage_node.execute_effect(contract)
            if result.success:
                duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                durations.append(duration)

                # Cleanup for next iteration
                pattern_id = UUID(result.data["pattern_id"])
                await storage_node.execute_effect(
                    ModelContractPatternStorage(
                        name="cleanup", operation="delete", pattern_id=pattern_id
                    )
                )

        avg_duration = sum(durations) / len(durations) if durations else 0
        assert (
            avg_duration < MAX_QUERY_TIME_MS
        ), f"Average insert: {avg_duration:.2f}ms (limit: {MAX_QUERY_TIME_MS}ms)"

    @pytest.mark.asyncio
    async def test_correlation_id_tracking(self, storage_node, cleanup_patterns):
        """Test correlation ID propagation through operations."""
        pattern_name = f"CorrelationTestPattern_{uuid4().hex[:8]}"
        cleanup_patterns.append(pattern_name)

        correlation_id = uuid4()

        contract = ModelContractPatternStorage(
            name="correlation_test",
            operation="insert",
            data={
                "pattern_name": pattern_name,
                "pattern_type": "code",
                "language": "python",
                "template_code": "code",
            },
            correlation_id=correlation_id,
        )

        result = await storage_node.execute_effect(contract)

        assert result.success is True
        assert result.metadata["correlation_id"] == str(correlation_id)


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_unsupported_operation(self, storage_node):
        """Test handling of unsupported operation."""
        contract = ModelContractPatternStorage(
            name="invalid_op", operation="invalid_operation", data={}
        )

        # Bypass contract validation
        contract.operation = "invalid_operation"

        result = await storage_node.execute_effect(contract)

        assert result.success is False
        assert "unsupported operation" in result.error.lower()

    @pytest.mark.asyncio
    async def test_metrics_collection(self, storage_node, cleanup_patterns):
        """Test that performance metrics are collected."""
        pattern_name = f"MetricsTestPattern_{uuid4().hex[:8]}"
        cleanup_patterns.append(pattern_name)

        contract = ModelContractPatternStorage(
            name="metrics_test",
            operation="insert",
            data={
                "pattern_name": pattern_name,
                "pattern_type": "code",
                "language": "python",
                "template_code": "code",
            },
        )

        # Clear existing metrics
        storage_node.clear_metrics()

        result = await storage_node.execute_effect(contract)

        assert result.success is True

        # Check metrics were recorded
        metrics = storage_node.get_metrics()
        assert "insert_duration_ms" in metrics
        assert metrics["insert_duration_ms"]["value"] > 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_full_crud_workflow(self, storage_node, cleanup_patterns):
        """Test complete CRUD workflow: insert -> update -> delete."""
        pattern_name = f"CRUDWorkflowPattern_{uuid4().hex[:8]}"
        cleanup_patterns.append(pattern_name)

        # 1. INSERT
        insert_contract = ModelContractPatternStorage(
            name="crud_insert",
            operation="insert",
            data={
                "pattern_name": pattern_name,
                "pattern_type": "code",
                "language": "python",
                "template_code": "original",
                "confidence_score": 0.5,
            },
        )

        insert_result = await storage_node.execute_effect(insert_contract)
        assert insert_result.success is True
        pattern_id = UUID(insert_result.data["pattern_id"])

        # 2. UPDATE
        update_contract = ModelContractPatternStorage(
            name="crud_update",
            operation="update",
            pattern_id=pattern_id,
            data={"confidence_score": 0.95, "template_code": "updated"},
        )

        update_result = await storage_node.execute_effect(update_contract)
        assert update_result.success is True

        # 3. DELETE
        delete_contract = ModelContractPatternStorage(
            name="crud_delete", operation="delete", pattern_id=pattern_id
        )

        delete_result = await storage_node.execute_effect(delete_contract)
        assert delete_result.success is True

        # Remove from cleanup since we deleted it
        cleanup_patterns.remove(pattern_name)


# ============================================================================
# Quality Metrics Tests
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_quality_score_high_quality():
    """Test quality calculation for high-quality pattern with all metrics."""
    if not ASYNCPG_AVAILABLE:
        pytest.skip("asyncpg not available")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=1)
    try:
        node = NodePatternStorageEffect(pool)

        # High-quality pattern data
        pattern_data = {
            "pattern_name": "HighQualityPattern",
            "pattern_type": "code",
            "language": "python",
            "template_code": "async def execute_effect(self, contract): ...",  # 50 chars
            "description": "Comprehensive documentation for this pattern",
            "example_usage": "pattern = Pattern(); await pattern.execute()",
            "complexity_score": 2,  # Low complexity (good)
            "maintainability_score": 0.95,  # High maintainability
            "performance_score": 0.90,  # High performance
            "usage_count": 100,  # Well-used
            "success_rate": 0.92,  # High success
            "confidence_score": 0.85,  # High confidence
        }

        result = node._calculate_quality_score(pattern_data)

        # Verify result structure
        assert "quality_score" in result
        assert "confidence" in result
        assert "metadata" in result

        # Verify quality score is high (>0.7 for high-quality pattern)
        assert 0.7 <= result["quality_score"] <= 1.0

        # Verify confidence is high
        assert result["confidence"] >= 0.6

        # Verify metadata contains components
        assert "components" in result["metadata"]
        assert "weights" in result["metadata"]
        assert "raw_metrics" in result["metadata"]

        # Verify all components are present
        components = result["metadata"]["components"]
        assert "complexity" in components
        assert "maintainability" in components
        assert "performance" in components
        assert "documentation" in components
        assert "usage" in components
        assert "success_rate" in components

    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_calculate_quality_score_low_quality():
    """Test quality calculation for low-quality pattern with poor metrics."""
    if not ASYNCPG_AVAILABLE:
        pytest.skip("asyncpg not available")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=1)
    try:
        node = NodePatternStorageEffect(pool)

        # Low-quality pattern data
        pattern_data = {
            "pattern_name": "LowQualityPattern",
            "pattern_type": "code",
            "language": "python",
            "template_code": "def x(): pass",  # Minimal code
            "description": None,  # No description
            "example_usage": None,  # No example
            "complexity_score": 9,  # High complexity (bad)
            "maintainability_score": 0.2,  # Low maintainability
            "performance_score": 0.3,  # Low performance
            "usage_count": 0,  # Unused
            "success_rate": 0.3,  # Low success
            "confidence_score": 0.4,  # Low confidence
        }

        result = node._calculate_quality_score(pattern_data)

        # Verify quality score is low (<0.5)
        assert 0.0 <= result["quality_score"] <= 0.5

        # Verify confidence is lower due to poor metrics
        assert result["confidence"] <= 0.6

    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_calculate_quality_score_defaults():
    """Test quality calculation with default values (minimal pattern data)."""
    if not ASYNCPG_AVAILABLE:
        pytest.skip("asyncpg not available")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=1)
    try:
        node = NodePatternStorageEffect(pool)

        # Minimal pattern data (most fields will use defaults)
        pattern_data = {
            "pattern_name": "MinimalPattern",
            "pattern_type": "code",
            "language": "python",
            "template_code": "def minimal(): return True",
        }

        result = node._calculate_quality_score(pattern_data)

        # Verify result is valid
        assert 0.0 <= result["quality_score"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0

        # With defaults, quality should be moderate (0.4-0.6 range)
        assert 0.3 <= result["quality_score"] <= 0.7

    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_quality_metric_recording():
    """Test recording quality metric to database during pattern insert."""
    if not ASYNCPG_AVAILABLE:
        pytest.skip("asyncpg not available")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2)
    try:
        node = NodePatternStorageEffect(pool)

        # Create pattern with quality metrics
        pattern_data = {
            "pattern_name": f"QualityTestPattern_{uuid4().hex[:8]}",
            "pattern_type": "code",
            "language": "python",
            "category": "test",
            "template_code": "async def test_pattern(): return True",
            "description": "Test pattern for quality metric recording",
            "example_usage": "result = await test_pattern()",
            "complexity_score": 3,
            "maintainability_score": 0.8,
            "performance_score": 0.85,
            "usage_count": 50,
            "success_rate": 0.88,
            "confidence_score": 0.75,
            "context": {"version": "1.0.0"},
        }

        # Insert pattern (should automatically record quality metric)
        contract = ModelContractPatternStorage(
            name="test_quality_metric_insert",
            operation="insert",
            data=pattern_data,
        )

        result = await node.execute_effect(contract)

        assert result.success is True
        pattern_id = UUID(result.data["pattern_id"])

        # Verify quality metric was recorded
        async with pool.acquire() as conn:
            # Check if quality metric exists for this pattern
            query = """
                SELECT quality_score, confidence, metadata
                FROM pattern_quality_metrics
                WHERE pattern_id = $1
            """
            metric_row = await conn.fetchrow(query, pattern_id)

            # Verify metric was recorded
            assert (
                metric_row is not None
            ), "Quality metric should be recorded for new pattern"

            # Verify values are within valid ranges
            assert 0.0 <= metric_row["quality_score"] <= 1.0
            assert 0.0 <= metric_row["confidence"] <= 1.0

            # Verify metadata is present
            assert metric_row["metadata"] is not None

            # Clean up test data
            await conn.execute(
                "DELETE FROM pattern_quality_metrics WHERE pattern_id = $1", pattern_id
            )
            await conn.execute(
                "DELETE FROM pattern_templates WHERE id = $1", pattern_id
            )

    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_quality_components_calculation():
    """Test individual component calculations in quality score."""
    if not ASYNCPG_AVAILABLE:
        pytest.skip("asyncpg not available")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=1)
    try:
        node = NodePatternStorageEffect(pool)

        # Test pattern with known metrics
        pattern_data = {
            "pattern_name": "ComponentTestPattern",
            "pattern_type": "code",
            "language": "python",
            "template_code": "def test(): pass" * 20,  # ~260 chars
            "description": "Test description",
            "example_usage": "test()",
            "complexity_score": 5,  # Medium
            "maintainability_score": 0.75,
            "performance_score": 0.70,
            "usage_count": 20,
            "success_rate": 0.80,
            "confidence_score": 0.70,
        }

        result = node._calculate_quality_score(pattern_data)

        components = result["metadata"]["components"]

        # Verify complexity component (inverted - lower is better)
        # Score 5 should give (10-5)/10 = 0.5
        assert abs(components["complexity"] - 0.5) < 0.1

        # Verify maintainability component (direct mapping)
        assert abs(components["maintainability"] - 0.75) < 0.01

        # Verify performance component (direct mapping)
        assert abs(components["performance"] - 0.70) < 0.01

        # Verify documentation component
        # Has description (0.4) + has example (0.3) + >100 chars (0.3) = 1.0
        assert components["documentation"] == 1.0

        # Verify success rate component (direct mapping)
        assert abs(components["success_rate"] - 0.80) < 0.01

        # Verify usage component (logarithmic scale)
        # 20 usage should be: log10(21)/3 ≈ 0.44
        assert 0.3 <= components["usage"] <= 0.6

    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_quality_metric_error_handling():
    """Test that quality metric recording errors don't fail pattern insert."""
    if not ASYNCPG_AVAILABLE:
        pytest.skip("asyncpg not available")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2)
    try:
        node = NodePatternStorageEffect(pool)

        # Create pattern with minimal data (quality calculation should still work)
        pattern_data = {
            "pattern_name": f"ErrorTestPattern_{uuid4().hex[:8]}",
            "pattern_type": "code",
            "language": "python",
            "category": "test",
            "template_code": "pass",
        }

        contract = ModelContractPatternStorage(
            name="test_quality_error_handling",
            operation="insert",
            data=pattern_data,
        )

        result = await node.execute_effect(contract)

        # Pattern insert should succeed even if quality metric has issues
        assert result.success is True
        pattern_id = UUID(result.data["pattern_id"])

        # Clean up
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM pattern_quality_metrics WHERE pattern_id = $1", pattern_id
            )
            await conn.execute(
                "DELETE FROM pattern_templates WHERE id = $1", pattern_id
            )

    finally:
        await pool.close()


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--cov=.", "--cov-report=term-missing"])
