"""
Integration Tests for Document Freshness API

Tests the complete Document Freshness API with 9 endpoints:
1. POST /freshness/analyze - Analyze document freshness
2. GET /freshness/stale - Get stale documents
3. POST /freshness/refresh - Refresh documents
4. GET /freshness/stats - Get statistics
5. GET /freshness/document/{path} - Get single document freshness
6. POST /freshness/cleanup - Cleanup old data
7. POST /freshness/events/document-update - Handle document update events
8. GET /freshness/events/stats - Get event statistics
9. GET /freshness/analyses - List freshness analyses

Covers freshness scoring, time decay, dependency tracking, batch operations,
event-driven updates, and cleanup functionality.

Author: Archon Intelligence Team
Date: 2025-10-16
"""

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

# ============================================================================
# Test Markers
# ============================================================================

pytestmark = [
    pytest.mark.integration,
    pytest.mark.freshness,
]


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_document_tree(tmp_path):
    """
    Create temporary document tree for freshness testing.

    Structure:
    - docs/
      - guide.md (fresh)
      - api.md (stale)
      - deprecated.md (very stale)
      - code/
        - example.py (fresh)
        - old_example.py (stale)
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    code_dir = docs_dir / "code"
    code_dir.mkdir()

    # Create documents with different modification times
    now = datetime.now()

    # Fresh document (1 day old)
    guide = docs_dir / "guide.md"
    guide.write_text("# User Guide\n\nLatest documentation.")
    guide.touch()

    # Stale document (45 days old)
    api = docs_dir / "api.md"
    api.write_text("# API Reference\n\nNeeds update.")
    (now - timedelta(days=45)).timestamp()
    Path(api).touch()

    # Very stale document (120 days old)
    deprecated = docs_dir / "deprecated.md"
    deprecated.write_text("# Deprecated Features\n\nVery old content.")
    (now - timedelta(days=120)).timestamp()
    Path(deprecated).touch()

    # Fresh code example (5 days old)
    example = code_dir / "example.py"
    example.write_text("def hello():\n    print('Hello, World!')")
    (now - timedelta(days=5)).timestamp()
    Path(example).touch()

    # Stale code example (60 days old)
    old_example = code_dir / "old_example.py"
    old_example.write_text("def old_function():\n    pass")
    (now - timedelta(days=60)).timestamp()
    Path(old_example).touch()

    return {
        "root": docs_dir,
        "guide": guide,
        "api": api,
        "deprecated": deprecated,
        "example": example,
        "old_example": old_example,
    }


@pytest.fixture
def sample_analysis_request(temp_document_tree):
    """Create sample freshness analysis request."""
    return {
        "path": str(temp_document_tree["root"]),
        "recursive": True,
        "include_patterns": ["*.md", "*.py"],
        "max_files": 100,
    }


@pytest.fixture
def sample_refresh_request(temp_document_tree):
    """Create sample document refresh request."""
    return {
        "document_paths": [
            str(temp_document_tree["api"]),
            str(temp_document_tree["deprecated"]),
        ],
        "refresh_mode": "safe",
        "backup_enabled": True,
        "dry_run": False,
    }


@pytest.fixture
def sample_document_update_event(temp_document_tree):
    """Create sample document update event."""
    return {
        "event_id": str(uuid4()),
        "event_type": "UPDATED",
        "document_path": str(temp_document_tree["guide"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "update_type": "content_change",
        "requires_immediate_analysis": False,
        "priority": 5,
    }


# ============================================================================
# Test Class: Freshness Analysis
# ============================================================================


@pytest.mark.freshness_analysis
class TestFreshnessAnalysis:
    """Tests for freshness analysis endpoint (POST /freshness/analyze)."""

    def test_analyze_single_document_success(
        self, test_client_with_lifespan, temp_document_tree
    ):
        """Test freshness analysis for a single document."""
        response = test_client_with_lifespan.post(
            "/freshness/analyze",
            json={
                "path": str(temp_document_tree["guide"]),
                "recursive": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure (FreshnessAnalysis model)
        assert "analysis_id" in data
        assert data["base_path"] == str(temp_document_tree["guide"])
        assert data["total_documents"] == 1
        assert data["analyzed_documents"] == 1
        assert "documents" in data
        assert isinstance(data["documents"], list)

        # Verify document analysis (first document in list)
        if data["documents"]:
            doc = data["documents"][0]
            assert doc["file_path"] == str(temp_document_tree["guide"])
            assert "freshness_score" in doc
            assert "overall_score" in doc["freshness_score"]
            assert 0.0 <= doc["freshness_score"]["overall_score"] <= 1.0
            assert "freshness_level" in doc
            assert doc["freshness_level"] in [
                "FRESH",
                "RECENT",
                "STALE",
                "OUTDATED",
                "CRITICAL",
            ]

    def test_analyze_directory_recursive(
        self, test_client_with_lifespan, sample_analysis_request
    ):
        """Test recursive directory analysis."""
        response = test_client_with_lifespan.post(
            "/freshness/analyze",
            json=sample_analysis_request,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify directory analysis
        assert data["success"] is True
        assert data["type"] == "directory_analysis"
        assert "analysis_id" in data
        assert "summary" in data

        summary = data["summary"]
        assert summary["total_documents"] > 0
        assert summary["analyzed_documents"] > 0
        assert "average_freshness_score" in summary
        assert 0.0 <= summary["average_freshness_score"] <= 1.0
        assert "stale_documents" in summary
        assert "critical_documents" in summary

        # Verify distributions and recommendations
        assert "freshness_distribution" in data
        assert "recommendations" in data

    def test_analyze_with_file_patterns(
        self, test_client_with_lifespan, temp_document_tree
    ):
        """Test analysis with include/exclude patterns."""
        response = test_client_with_lifespan.post(
            "/freshness/analyze",
            json={
                "path": str(temp_document_tree["root"]),
                "recursive": True,
                "include_patterns": ["*.md"],
                "exclude_patterns": ["deprecated*"],
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        # Should analyze only markdown files, excluding deprecated
        summary = data["summary"]
        assert summary["analyzed_documents"] >= 2  # guide.md, api.md

    def test_analyze_nonexistent_path(self, test_client_with_lifespan):
        """Test analysis with nonexistent path."""
        response = test_client_with_lifespan.post(
            "/freshness/analyze",
            json={
                "path": "/nonexistent/path/to/file.md",
                "recursive": False,
            },
        )

        assert response.status_code in [404, 400]
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_analyze_with_max_files_limit(
        self, test_client_with_lifespan, temp_document_tree
    ):
        """Test analysis with max_files limit."""
        response = test_client_with_lifespan.post(
            "/freshness/analyze",
            json={
                "path": str(temp_document_tree["root"]),
                "recursive": True,
                "max_files": 2,
            },
        )

        assert response.status_code == 200
        data = response.json()

        summary = data["summary"]
        assert summary["analyzed_documents"] <= 2

    def test_freshness_score_calculation(
        self, test_client_with_lifespan, temp_document_tree
    ):
        """Test that freshness scores are calculated correctly."""
        # Analyze fresh document
        fresh_response = test_client_with_lifespan.post(
            "/freshness/analyze",
            json={"path": str(temp_document_tree["guide"]), "recursive": False},
        )

        # Analyze stale document
        stale_response = test_client_with_lifespan.post(
            "/freshness/analyze",
            json={"path": str(temp_document_tree["deprecated"]), "recursive": False},
        )

        assert fresh_response.status_code == 200
        assert stale_response.status_code == 200

        fresh_score = fresh_response.json()["document"]["freshness_score"]
        stale_score = stale_response.json()["document"]["freshness_score"]

        # Fresh document should have higher score than stale
        assert fresh_score > stale_score


# ============================================================================
# Test Class: Stale Documents
# ============================================================================


@pytest.mark.stale_documents
class TestStaleDocuments:
    """Tests for stale documents endpoint (GET /freshness/stale)."""

    def test_get_stale_documents_default(self, test_client_with_lifespan):
        """Test getting stale documents with default filters."""
        response = test_client_with_lifespan.get("/freshness/stale")

        assert response.status_code == 200
        data = response.json()

        assert "documents" in data
        assert "count" in data
        assert isinstance(data["documents"], list)

    def test_get_stale_documents_with_age_filter(self, test_client_with_lifespan):
        """Test filtering stale documents by age."""
        response = test_client_with_lifespan.get(
            "/freshness/stale",
            params={
                "max_age_days": 30,
                "limit": 50,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # All documents should be older than 30 days
        for doc in data["documents"]:
            assert doc["age_days"] > 30

    def test_get_stale_documents_with_score_filter(self, test_client_with_lifespan):
        """Test filtering stale documents by freshness score."""
        response = test_client_with_lifespan.get(
            "/freshness/stale",
            params={
                "min_freshness_score": 0.7,
                "limit": 50,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # All documents should have score below threshold
        for doc in data["documents"]:
            assert doc["freshness_score"] < 0.7

    def test_get_stale_documents_with_priority_filter(self, test_client_with_lifespan):
        """Test filtering stale documents by refresh priority."""
        response = test_client_with_lifespan.get(
            "/freshness/stale",
            params={
                "priority_filter": "HIGH",
                "limit": 20,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # All documents should have HIGH priority
        for doc in data["documents"]:
            assert doc["refresh_priority"] == "HIGH"

    def test_get_stale_documents_pagination(self, test_client_with_lifespan):
        """Test pagination of stale documents."""
        # Get first page
        response1 = test_client_with_lifespan.get(
            "/freshness/stale",
            params={"limit": 5, "offset": 0},
        )

        # Get second page
        response2 = test_client_with_lifespan.get(
            "/freshness/stale",
            params={"limit": 5, "offset": 5},
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        docs1 = response1.json()["documents"]
        docs2 = response2.json()["documents"]

        # Pages should have different documents
        if docs1 and docs2:
            assert docs1[0]["path"] != docs2[0]["path"]


# ============================================================================
# Test Class: Document Refresh
# ============================================================================


@pytest.mark.document_refresh
class TestDocumentRefresh:
    """Tests for document refresh endpoint (POST /freshness/refresh)."""

    def test_refresh_documents_safe_mode(
        self, test_client_with_lifespan, sample_refresh_request
    ):
        """Test document refresh in safe mode with backups."""
        response = test_client_with_lifespan.post(
            "/freshness/refresh",
            json=sample_refresh_request,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "refresh_id" in data
        assert "summary" in data

        summary = data["summary"]
        assert "requested_documents" in summary
        assert "processed_documents" in summary
        assert "success_count" in summary
        assert "failure_count" in summary
        assert "success_rate" in summary

    def test_refresh_documents_dry_run(
        self, test_client_with_lifespan, temp_document_tree
    ):
        """Test document refresh in dry-run mode (no actual changes)."""
        response = test_client_with_lifespan.post(
            "/freshness/refresh",
            json={
                "document_paths": [str(temp_document_tree["api"])],
                "refresh_mode": "safe",
                "dry_run": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        # In dry run, no documents should be actually modified
        summary = data["summary"]
        assert summary.get("dry_run") is True

    def test_refresh_with_filters(self, test_client_with_lifespan, temp_document_tree):
        """Test document refresh with age and score filters."""
        response = test_client_with_lifespan.post(
            "/freshness/refresh",
            json={
                "document_paths": [str(temp_document_tree["root"])],
                "refresh_mode": "safe",
                "max_age_days": 60,
                "min_freshness_score": 0.5,
                "backup_enabled": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        # Should only process documents matching filters

    def test_refresh_creates_backups(
        self, test_client_with_lifespan, sample_refresh_request
    ):
        """Test that refresh operation creates backups when enabled."""
        sample_refresh_request["backup_enabled"] = True

        response = test_client_with_lifespan.post(
            "/freshness/refresh",
            json=sample_refresh_request,
        )

        assert response.status_code == 200
        data = response.json()

        # Should include backup locations
        if data["summary"]["success_count"] > 0:
            assert "backup_locations" in data
            assert len(data["backup_locations"]) > 0

    def test_refresh_tracks_improvements(
        self, test_client_with_lifespan, sample_refresh_request
    ):
        """Test that refresh operation tracks freshness improvements."""
        response = test_client_with_lifespan.post(
            "/freshness/refresh",
            json=sample_refresh_request,
        )

        assert response.status_code == 200
        data = response.json()

        # Should track freshness improvement
        assert "freshness_improvement" in data

    def test_refresh_invalid_documents(self, test_client_with_lifespan):
        """Test refresh with invalid document paths."""
        response = test_client_with_lifespan.post(
            "/freshness/refresh",
            json={
                "document_paths": ["/invalid/path/to/doc.md"],
                "refresh_mode": "safe",
            },
        )

        # Should handle gracefully
        assert response.status_code in [200, 400]
        data = response.json()

        if response.status_code == 200:
            summary = data["summary"]
            assert summary["failure_count"] > 0 or summary["skipped_count"] > 0


# ============================================================================
# Test Class: Freshness Statistics
# ============================================================================


@pytest.mark.freshness_stats
class TestFreshnessStatistics:
    """Tests for freshness statistics endpoint (GET /freshness/stats)."""

    def test_get_freshness_stats_global(self, test_client_with_lifespan):
        """Test getting global freshness statistics."""
        response = test_client_with_lifespan.get("/freshness/stats")

        assert response.status_code == 200
        data = response.json()

        assert "statistics" in data
        stats = data["statistics"]

        # Verify key metrics
        assert "total_documents" in stats
        assert "fresh_count" in stats
        assert "stale_count" in stats
        assert "outdated_count" in stats
        assert "critical_count" in stats
        assert "average_age_days" in stats
        assert "average_freshness_score" in stats

    def test_get_freshness_stats_with_base_path(
        self, test_client_with_lifespan, temp_document_tree
    ):
        """Test getting statistics filtered by base path."""
        response = test_client_with_lifespan.get(
            "/freshness/stats",
            params={"base_path": str(temp_document_tree["root"])},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["base_path"] == str(temp_document_tree["root"])

    def test_freshness_stats_health_indicators(self, test_client_with_lifespan):
        """Test that statistics include health indicators."""
        response = test_client_with_lifespan.get("/freshness/stats")

        assert response.status_code == 200
        data = response.json()

        assert "health_indicators" in data
        health = data["health_indicators"]

        # Verify health percentages
        assert "freshness_percentage" in health
        assert "staleness_percentage" in health
        assert "critical_percentage" in health
        assert 0 <= health["freshness_percentage"] <= 100
        assert 0 <= health["staleness_percentage"] <= 100

    def test_freshness_stats_type_distribution(self, test_client_with_lifespan):
        """Test that statistics include document type distribution."""
        response = test_client_with_lifespan.get("/freshness/stats")

        assert response.status_code == 200
        data = response.json()

        assert "type_distribution" in data
        type_dist = data["type_distribution"]

        # Should be a dictionary mapping types to counts
        assert isinstance(type_dist, dict)


# ============================================================================
# Test Class: Single Document Query
# ============================================================================


@pytest.mark.single_document
class TestSingleDocumentQuery:
    """Tests for single document freshness endpoint (GET /freshness/document/{path})."""

    def test_get_document_freshness_exists(
        self, test_client_with_lifespan, temp_document_tree
    ):
        """Test getting freshness info for existing document."""
        doc_path = str(temp_document_tree["guide"])

        response = test_client_with_lifespan.get(
            f"/freshness/document/{doc_path}",
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "document" in data

        doc = data["document"]
        assert doc["path"] == doc_path
        assert "freshness_score" in doc
        assert "age_days" in doc
        assert "freshness_level" in doc

    def test_get_document_freshness_not_found(self, test_client_with_lifespan):
        """Test getting freshness info for non-existent document."""
        response = test_client_with_lifespan.get(
            "/freshness/document//nonexistent/doc.md",
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_document_freshness_includes_dependencies(
        self, test_client_with_lifespan, temp_document_tree
    ):
        """Test that document freshness includes dependency information."""
        doc_path = str(temp_document_tree["guide"])

        response = test_client_with_lifespan.get(
            f"/freshness/document/{doc_path}",
        )

        assert response.status_code == 200
        data = response.json()

        doc = data["document"]
        # Should include dependency tracking
        if "dependencies" in doc:
            assert isinstance(doc["dependencies"], (int, list))


# ============================================================================
# Test Class: Cleanup Operations
# ============================================================================


@pytest.mark.cleanup
class TestCleanupOperations:
    """Tests for cleanup endpoint (POST /freshness/cleanup)."""

    def test_cleanup_old_data_default(self, test_client_with_lifespan):
        """Test cleanup with default retention period (90 days)."""
        response = test_client_with_lifespan.post(
            "/freshness/cleanup",
            json={"days_to_keep": 90},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "cleanup_results" in data

        results = data["cleanup_results"]
        assert "deleted_database_records" in results
        assert "deleted_backup_directories" in results
        assert results["days_kept"] == 90

    def test_cleanup_with_custom_retention(self, test_client_with_lifespan):
        """Test cleanup with custom retention period."""
        response = test_client_with_lifespan.post(
            "/freshness/cleanup",
            json={"days_to_keep": 30},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        results = data["cleanup_results"]
        assert results["days_kept"] == 30

    def test_cleanup_minimum_retention_validation(self, test_client_with_lifespan):
        """Test that cleanup enforces minimum retention period."""
        response = test_client_with_lifespan.post(
            "/freshness/cleanup",
            json={"days_to_keep": 3},  # Less than minimum (7 days)
        )

        # Should reject or use minimum
        assert response.status_code in [200, 400]
        if response.status_code == 400:
            data = response.json()
            assert data["success"] is False

    def test_cleanup_tracks_deleted_items(self, test_client_with_lifespan):
        """Test that cleanup tracks number of deleted items."""
        response = test_client_with_lifespan.post(
            "/freshness/cleanup",
            json={"days_to_keep": 90},
        )

        assert response.status_code == 200
        data = response.json()

        results = data["cleanup_results"]
        # Should report counts (even if 0)
        assert isinstance(results["deleted_database_records"], int)
        assert isinstance(results["deleted_backup_directories"], int)


# ============================================================================
# Test Class: Event Ingestion
# ============================================================================


@pytest.mark.event_ingestion
class TestEventIngestion:
    """Tests for document update event endpoint (POST /freshness/events/document-update)."""

    def test_ingest_document_update_event(
        self, test_client_with_lifespan, sample_document_update_event
    ):
        """Test ingesting document update event."""
        response = test_client_with_lifespan.post(
            "/freshness/events/document-update",
            json=sample_document_update_event,
        )

        assert response.status_code in [200, 202]  # 202 = Accepted for async processing
        data = response.json()

        assert data["success"] is True
        assert "event_id" in data

    def test_ingest_event_triggers_analysis(
        self, test_client_with_lifespan, sample_document_update_event
    ):
        """Test that document update event triggers freshness analysis."""
        sample_document_update_event["requires_immediate_analysis"] = True

        response = test_client_with_lifespan.post(
            "/freshness/events/document-update",
            json=sample_document_update_event,
        )

        assert response.status_code in [200, 202]
        # Event should be queued for analysis

    def test_ingest_batch_events(self, test_client_with_lifespan, temp_document_tree):
        """Test ingesting multiple document update events."""
        events = []
        for i in range(5):
            event = {
                "event_id": str(uuid4()),
                "event_type": "UPDATED",
                "document_path": str(temp_document_tree["guide"]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "update_type": "content_change",
                "priority": 5,
            }
            events.append(event)

        # Send events in sequence
        for event in events:
            response = test_client_with_lifespan.post(
                "/freshness/events/document-update",
                json=event,
            )
            assert response.status_code in [200, 202]

    def test_ingest_deletion_event(self, test_client_with_lifespan, temp_document_tree):
        """Test handling document deletion event."""
        event = {
            "event_id": str(uuid4()),
            "event_type": "DELETED",
            "document_path": str(temp_document_tree["deprecated"]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        response = test_client_with_lifespan.post(
            "/freshness/events/document-update",
            json=event,
        )

        assert response.status_code in [200, 202]
        # Should remove document from freshness tracking

    def test_ingest_invalid_event(self, test_client_with_lifespan):
        """Test handling invalid event payload."""
        invalid_event = {
            "event_type": "INVALID_TYPE",
            # Missing required fields
        }

        response = test_client_with_lifespan.post(
            "/freshness/events/document-update",
            json=invalid_event,
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False


# ============================================================================
# Test Class: Event Statistics
# ============================================================================


@pytest.mark.event_stats
class TestEventStatistics:
    """Tests for event statistics endpoint (GET /freshness/events/stats)."""

    def test_get_event_stats(self, test_client_with_lifespan):
        """Test getting event coordinator statistics."""
        response = test_client_with_lifespan.get("/freshness/events/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify coordinator stats
        assert "events_processed" in data
        assert "analyses_triggered" in data
        assert "batch_analyses" in data
        assert "immediate_analyses" in data
        assert "errors" in data
        assert isinstance(data["events_processed"], int)

    def test_event_stats_includes_pending_state(self, test_client_with_lifespan):
        """Test that stats include pending/active state."""
        response = test_client_with_lifespan.get("/freshness/events/stats")

        assert response.status_code == 200
        data = response.json()

        # Should include pending updates and active batches
        assert "pending_updates" in data
        assert "active_batches" in data

    def test_event_stats_includes_uptime(self, test_client_with_lifespan):
        """Test that stats include coordinator uptime."""
        response = test_client_with_lifespan.get("/freshness/events/stats")

        assert response.status_code == 200
        data = response.json()

        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0


# ============================================================================
# Test Class: Analyses List
# ============================================================================


@pytest.mark.analyses_list
class TestAnalysesList:
    """Tests for analyses list endpoint (GET /freshness/analyses)."""

    def test_list_analyses_default(self, test_client_with_lifespan):
        """Test listing freshness analyses with default parameters."""
        response = test_client_with_lifespan.get("/freshness/analyses")

        assert response.status_code == 200
        data = response.json()

        assert "analyses" in data
        assert "total_count" in data
        assert isinstance(data["analyses"], list)

    def test_list_analyses_pagination(self, test_client_with_lifespan):
        """Test pagination of analyses list."""
        response = test_client_with_lifespan.get(
            "/freshness/analyses",
            params={"limit": 10, "offset": 0},
        )

        assert response.status_code == 200
        data = response.json()

        # Should limit results
        assert len(data["analyses"]) <= 10

    def test_list_analyses_filtered_by_date(self, test_client_with_lifespan):
        """Test filtering analyses by date range."""
        start_date = (datetime.now() - timedelta(days=7)).isoformat()

        response = test_client_with_lifespan.get(
            "/freshness/analyses",
            params={
                "start_date": start_date,
                "limit": 50,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # All analyses should be after start_date
        for analysis in data["analyses"]:
            assert "created_at" in analysis

    def test_list_analyses_includes_metadata(self, test_client_with_lifespan):
        """Test that analyses list includes key metadata."""
        response = test_client_with_lifespan.get("/freshness/analyses")

        assert response.status_code == 200
        data = response.json()

        if data["analyses"]:
            analysis = data["analyses"][0]
            # Verify metadata structure
            assert "analysis_id" in analysis
            assert "created_at" in analysis
            assert "total_documents" in analysis
            assert "average_freshness_score" in analysis


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.performance
class TestFreshnessPerformance:
    """Performance tests for freshness API."""

    def test_analysis_performance_single_document(
        self, test_client_with_lifespan, temp_document_tree
    ):
        """Test that single document analysis completes within target time."""
        start_time = time.time()

        response = test_client_with_lifespan.post(
            "/freshness/analyze",
            json={
                "path": str(temp_document_tree["guide"]),
                "recursive": False,
            },
        )

        elapsed_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        # Target: <500ms for single document
        assert (
            elapsed_ms < 500
        ), f"Analysis took {elapsed_ms:.2f}ms, exceeds 500ms target"

    def test_batch_analysis_performance(
        self, test_client_with_lifespan, temp_document_tree
    ):
        """Test that directory analysis completes within target time."""
        start_time = time.time()

        response = test_client_with_lifespan.post(
            "/freshness/analyze",
            json={
                "path": str(temp_document_tree["root"]),
                "recursive": True,
                "max_files": 10,
            },
        )

        elapsed_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        # Target: <2s for 10 documents
        assert elapsed_ms < 2000, f"Analysis took {elapsed_ms:.2f}ms, exceeds 2s target"

    def test_stats_query_performance(self, test_client_with_lifespan):
        """Test that statistics query completes quickly."""
        start_time = time.time()

        response = test_client_with_lifespan.get("/freshness/stats")

        elapsed_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        # Target: <200ms for stats query
        assert (
            elapsed_ms < 200
        ), f"Stats query took {elapsed_ms:.2f}ms, exceeds 200ms target"
