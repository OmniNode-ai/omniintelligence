"""
Integration Tests for Intelligence Metrics API

Tests operations-per-minute endpoint for dashboard graphing.

Created: 2025-10-28
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
from app import app
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db_pool():
    """Create a mock database pool with test data"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    # Mock the acquire context manager
    mock_acquire_cm = MagicMock()
    mock_acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_acquire_cm

    return mock_pool, mock_conn


@pytest.fixture
def sample_operations_data():
    """Generate sample operations-per-minute data"""
    base_time = datetime.now(timezone.utc)
    data = []

    # Generate 60 minutes of data (1 hour)
    for i in range(60):
        timestamp = base_time - timedelta(minutes=60 - i)
        # Truncate to minute for consistency
        timestamp = timestamp.replace(second=0, microsecond=0)
        operations = 100 + (i % 10) * 5  # Varying operations count
        data.append({"timestamp": timestamp, "operations": operations})

    return data


class TestOperationsPerMinuteEndpoint:
    """Test suite for operations-per-minute endpoint"""

    @pytest.mark.asyncio
    async def test_operations_per_minute_success(
        self, mock_db_pool, sample_operations_data
    ):
        """Test successful operations-per-minute query"""
        mock_pool, mock_conn = mock_db_pool
        mock_conn.fetch = AsyncMock(return_value=sample_operations_data)

        # Patch the database pool
        with patch("src.api.intelligence_metrics.routes._db_pool", new=mock_pool):
            client = TestClient(app)
            response = client.get(
                "/api/intelligence/metrics/operations-per-minute?time_window=1h"
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "timestamps" in data
            assert "operations" in data
            assert "time_window" in data
            assert "total_operations" in data
            assert "avg_operations_per_minute" in data

            # Verify data consistency
            assert len(data["timestamps"]) == 60
            assert len(data["operations"]) == 60
            assert data["time_window"] == "1h"
            assert data["total_operations"] > 0
            assert data["avg_operations_per_minute"] > 0

    @pytest.mark.asyncio
    async def test_operations_per_minute_24h(self, mock_db_pool):
        """Test operations-per-minute query with 24h window"""
        mock_pool, mock_conn = mock_db_pool

        # Generate 24 hours of data (1440 minutes)
        base_time = datetime.now(timezone.utc)
        data = []
        for i in range(1440):
            timestamp = base_time - timedelta(minutes=1440 - i)
            timestamp = timestamp.replace(second=0, microsecond=0)
            operations = 50 + (i % 20) * 3
            data.append({"timestamp": timestamp, "operations": operations})

        mock_conn.fetch = AsyncMock(return_value=data)

        with patch("src.api.intelligence_metrics.routes._db_pool", new=mock_pool):
            client = TestClient(app)
            response = client.get(
                "/api/intelligence/metrics/operations-per-minute?time_window=24h"
            )

            assert response.status_code == 200
            data_response = response.json()

            assert data_response["time_window"] == "24h"
            assert len(data_response["timestamps"]) == 1440
            assert data_response["total_operations"] > 0

    @pytest.mark.asyncio
    async def test_operations_per_minute_empty_data(self, mock_db_pool):
        """Test operations-per-minute query with no data"""
        mock_pool, mock_conn = mock_db_pool
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("src.api.intelligence_metrics.routes._db_pool", new=mock_pool):
            client = TestClient(app)
            response = client.get(
                "/api/intelligence/metrics/operations-per-minute?time_window=1h"
            )

            assert response.status_code == 200
            data = response.json()

            # Should handle empty data gracefully
            assert data["timestamps"] == []
            assert data["operations"] == []
            assert data["total_operations"] == 0
            assert data["avg_operations_per_minute"] == 0.0

    @pytest.mark.asyncio
    async def test_operations_per_minute_database_error(self, mock_db_pool):
        """Test operations-per-minute endpoint with database error"""
        mock_pool, mock_conn = mock_db_pool
        mock_conn.fetch = AsyncMock(
            side_effect=asyncpg.PostgresError("Connection failed")
        )

        with patch("src.api.intelligence_metrics.routes._db_pool", new=mock_pool):
            client = TestClient(app)
            response = client.get(
                "/api/intelligence/metrics/operations-per-minute?time_window=1h"
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Database error" in data["detail"]

    def test_operations_per_minute_invalid_time_window(self):
        """Test operations-per-minute with invalid time window"""
        client = TestClient(app)

        # Invalid time window pattern
        response = client.get(
            "/api/intelligence/metrics/operations-per-minute?time_window=invalid"
        )

        # Should return validation error
        assert response.status_code == 422

    def test_operations_per_minute_no_db_pool(self):
        """Test operations-per-minute when database pool is not initialized"""
        with patch("src.api.intelligence_metrics.routes._db_pool", new=None):
            client = TestClient(app)
            response = client.get(
                "/api/intelligence/metrics/operations-per-minute?time_window=1h"
            )

            assert response.status_code == 503
            data = response.json()
            assert "detail" in data
            assert "Database pool not initialized" in data["detail"]

    @pytest.mark.asyncio
    async def test_operations_per_minute_all_time_windows(
        self, mock_db_pool, sample_operations_data
    ):
        """Test all supported time windows (1h, 24h, 7d, 30d)"""
        mock_pool, mock_conn = mock_db_pool
        time_windows = ["1h", "24h", "7d", "30d"]

        for window in time_windows:
            mock_conn.fetch = AsyncMock(return_value=sample_operations_data)

            with patch("src.api.intelligence_metrics.routes._db_pool", new=mock_pool):
                client = TestClient(app)
                response = client.get(
                    f"/api/intelligence/metrics/operations-per-minute?time_window={window}"
                )

                assert response.status_code == 200
                data = response.json()
                assert data["time_window"] == window

    @pytest.mark.asyncio
    async def test_operations_per_minute_response_format(
        self, mock_db_pool, sample_operations_data
    ):
        """Test response format matches dashboard requirements"""
        mock_pool, mock_conn = mock_db_pool
        mock_conn.fetch = AsyncMock(return_value=sample_operations_data)

        with patch("src.api.intelligence_metrics.routes._db_pool", new=mock_pool):
            client = TestClient(app)
            response = client.get(
                "/api/intelligence/metrics/operations-per-minute?time_window=1h"
            )

            assert response.status_code == 200
            data = response.json()

            # Verify timestamps are ISO format strings
            for ts in data["timestamps"]:
                # Should be parseable as datetime
                datetime.fromisoformat(ts.replace("Z", "+00:00"))

            # Verify operations are integers
            for op in data["operations"]:
                assert isinstance(op, int)

            # Verify avg_operations_per_minute is a float
            assert isinstance(data["avg_operations_per_minute"], (int, float))


class TestIntelligenceMetricsIntegration:
    """Integration tests for full intelligence metrics workflow"""

    @pytest.mark.asyncio
    async def test_complete_metrics_workflow(
        self, mock_db_pool, sample_operations_data
    ):
        """Test complete workflow: query operations → process → return formatted data"""
        mock_pool, mock_conn = mock_db_pool
        mock_conn.fetch = AsyncMock(return_value=sample_operations_data)

        with patch("src.api.intelligence_metrics.routes._db_pool", new=mock_pool):
            client = TestClient(app)

            # Step 1: Query operations-per-minute
            response = client.get(
                "/api/intelligence/metrics/operations-per-minute?time_window=1h"
            )
            assert response.status_code == 200
            data = response.json()

            # Step 2: Verify data consistency
            total = sum(data["operations"])
            assert data["total_operations"] == total

            avg = total / len(data["operations"]) if data["operations"] else 0
            assert abs(data["avg_operations_per_minute"] - avg) < 0.01

            # Step 3: Verify timestamps are in ascending order
            timestamps = [
                datetime.fromisoformat(ts.replace("Z", "+00:00"))
                for ts in data["timestamps"]
            ]
            assert timestamps == sorted(timestamps)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
