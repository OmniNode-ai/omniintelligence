"""
Integration Tests for Quality History Service

Tests for Phase 5B: Quality Intelligence Upgrades - Historical Quality Trends.
"""

from datetime import datetime, timedelta, timezone

import pytest
from archon_services.quality import QualityHistoryService, QualitySnapshot


@pytest.fixture
def quality_history_service():
    """Fixture for QualityHistoryService"""
    return QualityHistoryService()


@pytest.fixture
def sample_validation_result():
    """Fixture for sample validation result"""
    return {
        "quality_score": 0.85,
        "onex_compliance_score": 0.90,
        "violations": ["Missing type hints"],
        "warnings": ["Consider adding docstrings"],
    }


@pytest.mark.asyncio
async def test_record_snapshot(quality_history_service, sample_validation_result):
    """Test recording a quality snapshot"""
    await quality_history_service.record_snapshot(
        project_id="test_project",
        file_path="/path/to/file.py",
        validation_result=sample_validation_result,
        correlation_id="test_correlation_123",
    )

    assert quality_history_service.get_snapshot_count() == 1


@pytest.mark.asyncio
async def test_snapshot_timezone_awareness(
    quality_history_service, sample_validation_result
):
    """Test that snapshots have timezone-aware timestamps"""
    await quality_history_service.record_snapshot(
        project_id="test_project",
        file_path="/path/to/file.py",
        validation_result=sample_validation_result,
        correlation_id="test_correlation_123",
    )

    snapshot = quality_history_service.snapshots[0]
    assert snapshot.timestamp.tzinfo is not None


@pytest.mark.asyncio
async def test_get_quality_trend_insufficient_data(quality_history_service):
    """Test quality trend with insufficient data"""
    result = await quality_history_service.get_quality_trend(
        project_id="test_project", file_path=None, time_window_days=30
    )

    assert result["trend"] == "insufficient_data"
    assert result["snapshots_count"] == 0


@pytest.mark.asyncio
async def test_get_quality_trend_improving(quality_history_service):
    """Test quality trend detection - improving"""
    # Create snapshots with improving quality scores
    base_time = datetime.now(timezone.utc)
    scores = [0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]

    for i, score in enumerate(scores):
        snapshot = QualitySnapshot(
            timestamp=base_time - timedelta(days=7 - i),  # Spread over week
            project_id="test_project",
            file_path="/path/to/file.py",
            quality_score=score,
            compliance_score=score,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot)

    result = await quality_history_service.get_quality_trend(
        project_id="test_project", file_path=None, time_window_days=30
    )

    assert result["trend"] == "improving"
    assert result["slope"] > 0.01
    assert result["snapshots_count"] == 7
    assert result["current_quality"] == 0.9


@pytest.mark.asyncio
async def test_get_quality_trend_declining(quality_history_service):
    """Test quality trend detection - declining"""
    # Create snapshots with declining quality scores
    base_time = datetime.now(timezone.utc)
    scores = [0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6]

    for i, score in enumerate(scores):
        snapshot = QualitySnapshot(
            timestamp=base_time - timedelta(days=7 - i),
            project_id="test_project",
            file_path="/path/to/file.py",
            quality_score=score,
            compliance_score=score,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot)

    result = await quality_history_service.get_quality_trend(
        project_id="test_project", file_path=None, time_window_days=30
    )

    assert result["trend"] == "declining"
    assert result["slope"] < -0.01
    assert result["snapshots_count"] == 7
    assert result["current_quality"] == 0.6


@pytest.mark.asyncio
async def test_get_quality_trend_stable(quality_history_service):
    """Test quality trend detection - stable"""
    # Create snapshots with stable quality scores
    base_time = datetime.now(timezone.utc)
    scores = [0.8, 0.81, 0.79, 0.80, 0.81, 0.79, 0.8]

    for i, score in enumerate(scores):
        snapshot = QualitySnapshot(
            timestamp=base_time - timedelta(days=7 - i),
            project_id="test_project",
            file_path="/path/to/file.py",
            quality_score=score,
            compliance_score=score,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot)

    result = await quality_history_service.get_quality_trend(
        project_id="test_project", file_path=None, time_window_days=30
    )

    assert result["trend"] == "stable"
    assert -0.01 <= result["slope"] <= 0.01
    assert result["snapshots_count"] == 7


@pytest.mark.asyncio
async def test_get_quality_trend_file_level(quality_history_service):
    """Test quality trend for specific file"""
    base_time = datetime.now(timezone.utc)

    # Add snapshots for two different files
    for i in range(5):
        # File 1 - improving
        snapshot1 = QualitySnapshot(
            timestamp=base_time - timedelta(days=5 - i),
            project_id="test_project",
            file_path="/path/to/file1.py",
            quality_score=0.6 + (i * 0.05),
            compliance_score=0.7,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_file1_{i}",
        )
        quality_history_service.snapshots.append(snapshot1)

        # File 2 - declining
        snapshot2 = QualitySnapshot(
            timestamp=base_time - timedelta(days=5 - i),
            project_id="test_project",
            file_path="/path/to/file2.py",
            quality_score=0.9 - (i * 0.05),
            compliance_score=0.8,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_file2_{i}",
        )
        quality_history_service.snapshots.append(snapshot2)

    # Check file1 trend
    result1 = await quality_history_service.get_quality_trend(
        project_id="test_project", file_path="/path/to/file1.py", time_window_days=30
    )

    assert result1["trend"] == "improving"
    assert result1["snapshots_count"] == 5

    # Check file2 trend
    result2 = await quality_history_service.get_quality_trend(
        project_id="test_project", file_path="/path/to/file2.py", time_window_days=30
    )

    assert result2["trend"] == "declining"
    assert result2["snapshots_count"] == 5


@pytest.mark.asyncio
async def test_detect_quality_regression_no_data(quality_history_service):
    """Test regression detection with no baseline data"""
    result = await quality_history_service.detect_quality_regression(
        project_id="test_project", current_score=0.5, threshold=0.1
    )

    assert result["regression_detected"] is False
    assert result["reason"] == "no_baseline_data"


@pytest.mark.asyncio
async def test_detect_quality_regression_detected(quality_history_service):
    """Test regression detection - regression detected"""
    base_time = datetime.now(timezone.utc)

    # Add recent snapshots with high quality
    for i in range(10):
        snapshot = QualitySnapshot(
            timestamp=base_time - timedelta(days=10 - i),
            project_id="test_project",
            file_path="/path/to/file.py",
            quality_score=0.85,
            compliance_score=0.85,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot)

    # Check current score that's significantly lower
    result = await quality_history_service.detect_quality_regression(
        project_id="test_project",
        current_score=0.65,  # 0.20 below average
        threshold=0.1,
    )

    assert result["regression_detected"] is True
    assert result["current_score"] == 0.65
    assert result["avg_recent_score"] == pytest.approx(0.85, abs=1e-9)
    assert result["difference"] == pytest.approx(0.20, abs=1e-9)
    assert result["snapshots_evaluated"] == 10


@pytest.mark.asyncio
async def test_detect_quality_regression_not_detected(quality_history_service):
    """Test regression detection - no regression"""
    base_time = datetime.now(timezone.utc)

    # Add recent snapshots
    for i in range(10):
        snapshot = QualitySnapshot(
            timestamp=base_time - timedelta(days=10 - i),
            project_id="test_project",
            file_path="/path/to/file.py",
            quality_score=0.8,
            compliance_score=0.8,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot)

    # Check current score that's within threshold
    result = await quality_history_service.detect_quality_regression(
        project_id="test_project",
        current_score=0.75,  # 0.05 below average, within threshold
        threshold=0.1,
    )

    assert result["regression_detected"] is False
    assert result["current_score"] == 0.75
    assert result["avg_recent_score"] == pytest.approx(0.8, abs=1e-9)
    assert result["difference"] == pytest.approx(0.05, abs=1e-9)


@pytest.mark.asyncio
async def test_get_quality_history(quality_history_service):
    """Test retrieving quality history for a file"""
    base_time = datetime.now(timezone.utc)

    # Add snapshots
    for i in range(15):
        snapshot = QualitySnapshot(
            timestamp=base_time - timedelta(days=15 - i),
            project_id="test_project",
            file_path="/path/to/file.py",
            quality_score=0.7 + (i * 0.01),
            compliance_score=0.8,
            violations=["violation"] * i,
            warnings=["warning"] * i,
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot)

    # Get history (default limit: 50)
    history = await quality_history_service.get_quality_history(
        project_id="test_project", file_path="/path/to/file.py"
    )

    assert len(history) == 15
    # Should be sorted by timestamp descending (newest first)
    assert history[0]["quality_score"] > history[-1]["quality_score"]

    # Test with limit
    history_limited = await quality_history_service.get_quality_history(
        project_id="test_project", file_path="/path/to/file.py", limit=5
    )

    assert len(history_limited) == 5


@pytest.mark.asyncio
async def test_clear_snapshots_all(quality_history_service):
    """Test clearing all snapshots"""
    # Add snapshots for multiple projects
    for i in range(5):
        snapshot1 = QualitySnapshot(
            timestamp=datetime.now(timezone.utc),
            project_id="project1",
            file_path="/path/to/file.py",
            quality_score=0.8,
            compliance_score=0.8,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot1)

        snapshot2 = QualitySnapshot(
            timestamp=datetime.now(timezone.utc),
            project_id="project2",
            file_path="/path/to/file.py",
            quality_score=0.8,
            compliance_score=0.8,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot2)

    assert quality_history_service.get_snapshot_count() == 10

    # Clear all
    cleared_count = quality_history_service.clear_snapshots()

    assert cleared_count == 10
    assert quality_history_service.get_snapshot_count() == 0


@pytest.mark.asyncio
async def test_clear_snapshots_by_project(quality_history_service):
    """Test clearing snapshots for specific project"""
    # Add snapshots for multiple projects
    for i in range(5):
        snapshot1 = QualitySnapshot(
            timestamp=datetime.now(timezone.utc),
            project_id="project1",
            file_path="/path/to/file.py",
            quality_score=0.8,
            compliance_score=0.8,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot1)

        snapshot2 = QualitySnapshot(
            timestamp=datetime.now(timezone.utc),
            project_id="project2",
            file_path="/path/to/file.py",
            quality_score=0.8,
            compliance_score=0.8,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot2)

    assert quality_history_service.get_snapshot_count() == 10

    # Clear only project1
    cleared_count = quality_history_service.clear_snapshots(project_id="project1")

    assert cleared_count == 5
    assert quality_history_service.get_snapshot_count() == 5

    # Verify remaining snapshots are from project2
    remaining_project_ids = [s.project_id for s in quality_history_service.snapshots]
    assert all(pid == "project2" for pid in remaining_project_ids)


@pytest.mark.asyncio
async def test_time_window_filtering(quality_history_service):
    """Test time window filtering in trend analysis"""
    base_time = datetime.now(timezone.utc)

    # Add snapshots with varying ages
    for i in range(60):  # 60 days worth of data
        snapshot = QualitySnapshot(
            timestamp=base_time - timedelta(days=60 - i),
            project_id="test_project",
            file_path="/path/to/file.py",
            quality_score=0.5
            + (i * 0.012),  # Steadily improving (slope > 0.01 threshold)
            compliance_score=0.8,
            violations=[],
            warnings=[],
            correlation_id=f"correlation_{i}",
        )
        quality_history_service.snapshots.append(snapshot)

    # Get trend for last 30 days
    result_30 = await quality_history_service.get_quality_trend(
        project_id="test_project", file_path=None, time_window_days=30
    )

    # Get trend for last 7 days
    result_7 = await quality_history_service.get_quality_trend(
        project_id="test_project", file_path=None, time_window_days=7
    )

    # Allow for boundary conditions due to timing (expect 29-30 snapshots for 30-day window)
    assert result_30["snapshots_count"] >= 29
    assert result_30["snapshots_count"] <= 31
    assert result_7["snapshots_count"] >= 6
    assert result_7["snapshots_count"] <= 8
    assert result_30["trend"] == "improving"
    assert result_7["trend"] == "improving"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
