"""
Unit Tests for Pattern Storage (PostgreSQL)
AI-Generated with agent-testing methodology
Coverage Target: 95%+

Tests:
- Pattern CRUD operations
- Batch operations
- Query performance
- Data validation
- Error handling
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from asyncpg import Connection, UniqueViolationError


class TestPatternStoragePostgreSQL:
    """Unit tests for PostgreSQL pattern storage operations."""

    # ==========================================
    # CREATE Operations
    # ==========================================

    @pytest.mark.asyncio
    async def test_insert_single_pattern(
        self, db_conn: Connection, sample_pattern: Dict[str, Any], clean_database
    ):
        """Test inserting a single pattern into success_patterns table."""
        # Arrange
        pattern = sample_pattern

        # Act
        result = await db_conn.fetchrow(
            """
            INSERT INTO success_patterns (
                pattern_id, pattern_type, intent_keywords,
                execution_sequence, success_criteria, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING pattern_id, created_at
            """,
            uuid.UUID(pattern["pattern_id"]),
            pattern["pattern_type"],
            pattern["intent_keywords"],
            pattern["execution_sequence"],
            pattern["success_criteria"],
            pattern["metadata"],
        )

        # Assert
        assert result is not None
        assert str(result["pattern_id"]) == pattern["pattern_id"]
        assert result["created_at"] is not None

    @pytest.mark.asyncio
    async def test_insert_duplicate_pattern_fails(
        self, db_conn: Connection, sample_pattern: Dict[str, Any], clean_database
    ):
        """Test that inserting duplicate pattern_id raises error."""
        # Arrange
        pattern = sample_pattern

        # Insert first time
        await db_conn.execute(
            """
            INSERT INTO success_patterns (
                pattern_id, pattern_type, intent_keywords,
                execution_sequence, success_criteria, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.UUID(pattern["pattern_id"]),
            pattern["pattern_type"],
            pattern["intent_keywords"],
            pattern["execution_sequence"],
            pattern["success_criteria"],
            pattern["metadata"],
        )

        # Act & Assert - Second insert should fail
        with pytest.raises(UniqueViolationError):
            await db_conn.execute(
                """
                INSERT INTO success_patterns (
                    pattern_id, pattern_type, intent_keywords,
                    execution_sequence, success_criteria, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.UUID(pattern["pattern_id"]),
                pattern["pattern_type"],
                pattern["intent_keywords"],
                pattern["execution_sequence"],
                pattern["success_criteria"],
                pattern["metadata"],
            )

    @pytest.mark.asyncio
    async def test_batch_insert_patterns(
        self,
        db_conn: Connection,
        sample_patterns_batch: List[Dict[str, Any]],
        clean_database,
        performance_timer,
    ):
        """Test batch inserting 10 patterns."""
        # Arrange
        patterns = sample_patterns_batch

        # Act
        performance_timer.start()

        for pattern in patterns:
            await db_conn.execute(
                """
                INSERT INTO success_patterns (
                    pattern_id, pattern_type, intent_keywords,
                    execution_sequence, success_criteria, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.UUID(pattern["pattern_id"]),
                pattern["pattern_type"],
                pattern["intent_keywords"],
                pattern["execution_sequence"],
                pattern["success_criteria"],
                pattern["metadata"],
            )

        performance_timer.stop()

        # Assert
        count = await db_conn.fetchval("SELECT COUNT(*) FROM success_patterns")
        assert count == len(patterns)

        # Performance: Batch insert should complete in <200ms
        assert performance_timer.elapsed_ms < 200, (
            f"Batch insert took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds 200ms threshold"
        )

    # ==========================================
    # READ Operations
    # ==========================================

    @pytest.mark.asyncio
    async def test_read_pattern_by_id(
        self, db_conn: Connection, sample_pattern: Dict[str, Any], clean_database
    ):
        """Test reading a pattern by pattern_id."""
        # Arrange - Insert pattern first
        pattern = sample_pattern
        await db_conn.execute(
            """
            INSERT INTO success_patterns (
                pattern_id, pattern_type, intent_keywords,
                execution_sequence, success_criteria, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.UUID(pattern["pattern_id"]),
            pattern["pattern_type"],
            pattern["intent_keywords"],
            pattern["execution_sequence"],
            pattern["success_criteria"],
            pattern["metadata"],
        )

        # Act
        result = await db_conn.fetchrow(
            """
            SELECT pattern_id, pattern_type, intent_keywords,
                   execution_sequence, success_criteria, metadata
            FROM success_patterns
            WHERE pattern_id = $1
            """,
            uuid.UUID(pattern["pattern_id"]),
        )

        # Assert
        assert result is not None
        assert str(result["pattern_id"]) == pattern["pattern_id"]
        assert result["pattern_type"] == pattern["pattern_type"]
        assert result["intent_keywords"] == pattern["intent_keywords"]

    @pytest.mark.asyncio
    async def test_read_patterns_by_type(
        self,
        db_conn: Connection,
        sample_patterns_batch: List[Dict[str, Any]],
        clean_database,
    ):
        """Test reading patterns filtered by pattern_type."""
        # Arrange - Insert batch
        for pattern in sample_patterns_batch:
            await db_conn.execute(
                """
                INSERT INTO success_patterns (
                    pattern_id, pattern_type, intent_keywords,
                    execution_sequence, success_criteria, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.UUID(pattern["pattern_id"]),
                pattern["pattern_type"],
                pattern["intent_keywords"],
                pattern["execution_sequence"],
                pattern["success_criteria"],
                pattern["metadata"],
            )

        # Act
        results = await db_conn.fetch(
            """
            SELECT pattern_id, pattern_type
            FROM success_patterns
            WHERE pattern_type = $1
            """,
            "agent_sequence",
        )

        # Assert
        assert len(results) > 0
        for row in results:
            assert row["pattern_type"] == "agent_sequence"

    @pytest.mark.asyncio
    async def test_read_patterns_with_keyword_search(
        self, db_conn: Connection, sample_pattern: Dict[str, Any], clean_database
    ):
        """Test reading patterns using keyword array search."""
        # Arrange
        pattern = sample_pattern
        await db_conn.execute(
            """
            INSERT INTO success_patterns (
                pattern_id, pattern_type, intent_keywords,
                execution_sequence, success_criteria, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.UUID(pattern["pattern_id"]),
            pattern["pattern_type"],
            pattern["intent_keywords"],
            pattern["execution_sequence"],
            pattern["success_criteria"],
            pattern["metadata"],
        )

        # Act - Search for pattern with "authentication" keyword
        results = await db_conn.fetch(
            """
            SELECT pattern_id, intent_keywords
            FROM success_patterns
            WHERE 'authentication' = ANY(intent_keywords)
            """
        )

        # Assert
        assert len(results) > 0
        assert "authentication" in results[0]["intent_keywords"]

    # ==========================================
    # UPDATE Operations
    # ==========================================

    @pytest.mark.asyncio
    async def test_update_pattern_metadata(
        self, db_conn: Connection, sample_pattern: Dict[str, Any], clean_database
    ):
        """Test updating pattern metadata (success_count, confidence_score)."""
        # Arrange - Insert pattern first
        pattern = sample_pattern
        await db_conn.execute(
            """
            INSERT INTO success_patterns (
                pattern_id, pattern_type, intent_keywords,
                execution_sequence, success_criteria, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.UUID(pattern["pattern_id"]),
            pattern["pattern_type"],
            pattern["intent_keywords"],
            pattern["execution_sequence"],
            pattern["success_criteria"],
            pattern["metadata"],
        )

        # Act - Update metadata
        updated_metadata = {
            **pattern["metadata"],
            "success_count": 10,
            "total_attempts": 12,
            "confidence_score": 0.83,
        }

        await db_conn.execute(
            """
            UPDATE success_patterns
            SET metadata = $1, updated_at = NOW()
            WHERE pattern_id = $2
            """,
            updated_metadata,
            uuid.UUID(pattern["pattern_id"]),
        )

        # Assert
        result = await db_conn.fetchrow(
            """
            SELECT metadata, updated_at
            FROM success_patterns
            WHERE pattern_id = $1
            """,
            uuid.UUID(pattern["pattern_id"]),
        )

        assert result["metadata"]["success_count"] == 10
        assert result["metadata"]["confidence_score"] == 0.83
        assert result["updated_at"] is not None

    # ==========================================
    # DELETE Operations
    # ==========================================

    @pytest.mark.asyncio
    async def test_delete_pattern_by_id(
        self, db_conn: Connection, sample_pattern: Dict[str, Any], clean_database
    ):
        """Test deleting a pattern by pattern_id."""
        # Arrange - Insert pattern first
        pattern = sample_pattern
        await db_conn.execute(
            """
            INSERT INTO success_patterns (
                pattern_id, pattern_type, intent_keywords,
                execution_sequence, success_criteria, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.UUID(pattern["pattern_id"]),
            pattern["pattern_type"],
            pattern["intent_keywords"],
            pattern["execution_sequence"],
            pattern["success_criteria"],
            pattern["metadata"],
        )

        # Act
        await db_conn.execute(
            """
            DELETE FROM success_patterns
            WHERE pattern_id = $1
            """,
            uuid.UUID(pattern["pattern_id"]),
        )

        # Assert
        result = await db_conn.fetchrow(
            """
            SELECT pattern_id
            FROM success_patterns
            WHERE pattern_id = $1
            """,
            uuid.UUID(pattern["pattern_id"]),
        )

        assert result is None

    # ==========================================
    # Query Performance Tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_pattern_lookup_performance(
        self,
        db_conn: Connection,
        sample_patterns_batch: List[Dict[str, Any]],
        clean_database,
        performance_timer,
    ):
        """Test that pattern lookup completes in <100ms."""
        # Arrange - Insert batch
        for pattern in sample_patterns_batch:
            await db_conn.execute(
                """
                INSERT INTO success_patterns (
                    pattern_id, pattern_type, intent_keywords,
                    execution_sequence, success_criteria, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.UUID(pattern["pattern_id"]),
                pattern["pattern_type"],
                pattern["intent_keywords"],
                pattern["execution_sequence"],
                pattern["success_criteria"],
                pattern["metadata"],
            )

        pattern_id = sample_patterns_batch[0]["pattern_id"]

        # Act
        performance_timer.start()
        result = await db_conn.fetchrow(
            """
            SELECT *
            FROM success_patterns
            WHERE pattern_id = $1
            """,
            uuid.UUID(pattern_id),
        )
        performance_timer.stop()

        # Assert
        assert result is not None
        assert performance_timer.elapsed_ms < 100, (
            f"Pattern lookup took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds 100ms threshold"
        )

    # ==========================================
    # Error Handling Tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_insert_pattern_with_null_required_field_fails(
        self, db_conn: Connection, clean_database
    ):
        """Test that inserting pattern with NULL required field fails."""
        # Act & Assert
        with pytest.raises(Exception):  # Should raise NOT NULL constraint violation
            await db_conn.execute(
                """
                INSERT INTO success_patterns (
                    pattern_id, pattern_type, intent_keywords,
                    execution_sequence, success_criteria, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.uuid4(),
                None,  # NULL pattern_type should fail
                ["test"],
                [{"agent": "test"}],
                {"status": "ok"},
                {"created_at": datetime.now(timezone.utc).isoformat()},
            )

    @pytest.mark.asyncio
    async def test_read_nonexistent_pattern_returns_none(
        self, db_conn: Connection, clean_database
    ):
        """Test that reading non-existent pattern returns None."""
        # Act
        result = await db_conn.fetchrow(
            """
            SELECT pattern_id
            FROM success_patterns
            WHERE pattern_id = $1
            """,
            uuid.uuid4(),  # Random UUID that doesn't exist
        )

        # Assert
        assert result is None
