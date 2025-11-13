"""
Test module for intelligence data access layer.

This module demonstrates how the extracted data access layer can be
independently tested for data quality verification without UI concerns.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from src.server.data.intelligence_data_access import (
    DiffAnalysisData,
    IntelligenceDataAccess,
    IntelligenceStatsData,
    QueryParameters,
    TemporalCorrelationData,
)


class TestIntelligenceDataAccess:
    """Test cases for IntelligenceDataAccess class."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock database client for testing."""
        client = Mock()
        client.table.return_value = client
        client.select.return_value = client
        client.order.return_value = client
        return client

    @pytest.fixture
    def data_access(self, mock_client):
        """Create IntelligenceDataAccess instance with mock client."""
        return IntelligenceDataAccess(mock_client)

    def test_parse_time_range_valid_ranges(self, data_access):
        """Test parsing of valid time range strings."""
        assert data_access.parse_time_range("1h") == 1
        assert data_access.parse_time_range("6h") == 6
        assert data_access.parse_time_range("24h") == 24
        assert data_access.parse_time_range("72h") == 72
        assert data_access.parse_time_range("7d") == 168

    def test_parse_time_range_invalid_defaults_to_24h(self, data_access):
        """Test parsing of invalid time range defaults to 24h."""
        assert data_access.parse_time_range("invalid") == 24
        assert data_access.parse_time_range("") == 24
        assert data_access.parse_time_range("999x") == 24

    def test_parse_diff_analysis_git_hook_format(self, data_access):
        """Test parsing diff analysis from git hook format."""
        content = {
            "diff_analysis": {
                "total_changes": 5,
                "added_lines": 100,
                "removed_lines": 50,
                "modified_files": ["file1.py", "file2.js"],
            }
        }

        result = data_access.parse_diff_analysis(content)

        assert result is not None
        assert result.total_changes == 5
        assert result.added_lines == 100
        assert result.removed_lines == 50
        assert result.modified_files == ["file1.py", "file2.js"]

    def test_parse_diff_analysis_mcp_format(self, data_access):
        """Test parsing diff analysis from MCP format."""
        content = {
            "code_changes_analysis": {
                "changed_files": ["src/main.py", "tests/test_main.py"]
            }
        }

        result = data_access.parse_diff_analysis(content)

        assert result is not None
        assert result.total_changes == 2
        assert result.added_lines == 0  # Not available in MCP format
        assert result.removed_lines == 0  # Not available in MCP format
        assert result.modified_files == ["src/main.py", "tests/test_main.py"]

    def test_parse_diff_analysis_no_data(self, data_access):
        """Test parsing diff analysis when no data is present."""
        content = {"other_data": "value"}

        result = data_access.parse_diff_analysis(content)

        assert result is None

    def test_parse_correlations_temporal_string_strength(self, data_access):
        """Test parsing temporal correlations with string strength values."""
        content = {
            "correlation_analysis": {
                "temporal_correlations": [
                    {
                        "repository": "repo1",
                        "commit_sha": "abc123",
                        "time_diff_hours": 2.5,
                        "correlation_strength": "high",
                    }
                ]
            }
        }

        temporal, semantic, breaking = data_access.parse_correlations(content)

        assert len(temporal) == 1
        assert temporal[0].repository == "repo1"
        assert temporal[0].commit_sha == "abc123"
        assert temporal[0].time_diff_hours == 2.5
        assert temporal[0].correlation_strength == 0.9  # "high" maps to 0.9

    def test_parse_correlations_v3_format(self, data_access):
        """Test parsing correlations in v3.0 format."""
        content = {
            "cross_repository_correlation": {
                "temporal_correlations": [
                    {
                        "repository": "repo1",
                        "commit": "def456",
                        "time_window": "6h",
                        "correlation_strength": "medium",
                    }
                ],
                "semantic_correlations": [
                    {
                        "repository": "repo2",
                        "commit": "ghi789",
                        "shared_keywords": "auth login user",
                    }
                ],
                "breaking_changes": [
                    {
                        "type": "API_CHANGE",
                        "severity": "HIGH",
                        "description": "Method signature changed",
                        "files_affected": ["api.py"],
                    }
                ],
            }
        }

        temporal, semantic, breaking = data_access.parse_correlations(content)

        # Check temporal correlation
        assert len(temporal) == 1
        assert temporal[0].time_diff_hours == 6.0  # Converted from "6h"
        assert temporal[0].correlation_strength == 0.6  # "medium" maps to 0.6

        # Check semantic correlation
        assert len(semantic) == 1
        assert semantic[0].common_keywords == ["auth", "login", "user"]

        # Check breaking changes
        assert len(breaking) == 1
        assert breaking[0].type == "API_CHANGE"
        assert breaking[0].severity == "HIGH"

    def test_parse_security_analysis_git_hook_format(self, data_access):
        """Test parsing security analysis from git hook format."""
        content = {
            "security_analysis": {
                "patterns_detected": ["SQL injection check", "XSS validation"],
                "risk_level": "MEDIUM",
                "secure_patterns": 3,
            }
        }

        result = data_access.parse_security_analysis(content)

        assert result is not None
        assert result.patterns_detected == ["SQL injection check", "XSS validation"]
        assert result.risk_level == "MEDIUM"
        assert result.secure_patterns == 3

    def test_parse_security_analysis_quality_metrics_format(self, data_access):
        """Test parsing security analysis from quality metrics format."""
        content = {
            "quality_baseline": {
                "code_quality_metrics": {
                    "anti_patterns_found": 0,
                    "architectural_compliance": "High",
                    "type_safety": "Strong",
                }
            }
        }

        result = data_access.parse_security_analysis(content)

        assert result is not None
        assert len(result.patterns_detected) == 3
        assert "No anti-patterns detected" in result.patterns_detected
        assert "High architectural compliance" in result.patterns_detected
        assert "Strong type safety" in result.patterns_detected
        assert result.risk_level == "LOW"
        assert result.secure_patterns == 3

    def test_parse_document_metadata_intelligence_type(self, data_access):
        """Test parsing document metadata for intelligence type documents."""
        doc = {
            "document_type": "intelligence",
            "content": {
                "metadata": {
                    "repository": "test-repo",
                    "commit": "abc123",
                    "author": "john.doe",
                    "change_type": "feature",
                }
            },
            "metadata": {},
        }

        (
            repository,
            commit_sha,
            author,
            change_type,
        ) = data_access.parse_document_metadata(doc)

        assert repository == "test-repo"
        assert commit_sha == "abc123"
        assert author == "john.doe"
        assert change_type == "feature"

    def test_parse_document_metadata_project_type(self, data_access):
        """Test parsing document metadata for project type documents."""
        doc = {
            "document_type": "project",
            "content": {
                "repository_info": {"repository": "project-repo", "commit": "def456"},
                "update_type": "enhancement",
            },
            "author": "jane.smith",
        }

        (
            repository,
            commit_sha,
            author,
            change_type,
        ) = data_access.parse_document_metadata(doc)

        assert repository == "project-repo"
        assert commit_sha == "def456"
        assert author == "jane.smith"
        assert change_type == "enhancement"

    def test_extract_intelligence_documents_filters_by_tags(self, data_access):
        """Test that only documents with intelligence tags are extracted."""
        # Use recent timestamps that will pass the time filter
        recent_time = datetime.now(UTC) - timedelta(hours=1)
        recent_time_str = recent_time.isoformat().replace("+00:00", "Z")

        projects = [
            {
                "id": "proj1",
                "title": "Test Project",
                "created_at": recent_time_str,
                "updated_at": recent_time_str,
                "docs": [
                    {
                        "id": "doc1",
                        "tags": ["intelligence", "pre-push"],
                        "content": {"metadata": {"repository": "repo1"}},
                        "created_at": recent_time_str,
                    },
                    {
                        "id": "doc2",
                        "tags": ["documentation"],  # No intelligence tags
                        "content": {"metadata": {"repository": "repo2"}},
                        "created_at": recent_time_str,
                    },
                    {
                        "id": "doc3",
                        "tags": ["quality-assessment"],
                        "content": {"metadata": {"repository": "repo3"}},
                        "created_at": recent_time_str,
                    },
                ],
            }
        ]

        cutoff_time = datetime.now(UTC) - timedelta(hours=24)

        result = data_access.extract_intelligence_documents_from_projects(
            projects, cutoff_time
        )

        assert len(result) == 2  # Only doc1 and doc3 should be included
        assert result[0]["id"] == "doc1"
        assert result[1]["id"] == "doc3"

    def test_calculate_statistics_empty_data(self, data_access, mock_client):
        """Test statistics calculation with empty data."""
        # Mock empty response
        mock_client.execute.return_value = Mock(data=[])

        params = QueryParameters(time_range="24h")
        result = data_access.calculate_statistics(params)

        assert result.total_changes == 0
        assert result.total_correlations == 0
        assert result.average_correlation_strength == 0.0
        assert result.breaking_changes == 0
        assert result.repositories_active == 0
        assert result.correlation_strengths == []
        assert result.repositories_list == []


class TestQueryParameters:
    """Test cases for QueryParameters data class."""

    def test_query_parameters_defaults(self):
        """Test QueryParameters with default values."""
        params = QueryParameters()

        assert params.repository is None
        assert params.time_range == "24h"
        assert params.limit == 50
        assert params.offset == 0

    def test_query_parameters_custom_values(self):
        """Test QueryParameters with custom values."""
        params = QueryParameters(
            repository="test-repo", time_range="7d", limit=100, offset=25
        )

        assert params.repository == "test-repo"
        assert params.time_range == "7d"
        assert params.limit == 100
        assert params.offset == 25


class TestDataStructures:
    """Test cases for data structure classes."""

    def test_diff_analysis_data_creation(self):
        """Test DiffAnalysisData creation and attributes."""
        diff = DiffAnalysisData(
            total_changes=10,
            added_lines=100,
            removed_lines=50,
            modified_files=["file1.py", "file2.js"],
        )

        assert diff.total_changes == 10
        assert diff.added_lines == 100
        assert diff.removed_lines == 50
        assert diff.modified_files == ["file1.py", "file2.js"]

    def test_temporal_correlation_data_creation(self):
        """Test TemporalCorrelationData creation and attributes."""
        temporal = TemporalCorrelationData(
            repository="repo1",
            commit_sha="abc123",
            time_diff_hours=2.5,
            correlation_strength=0.8,
        )

        assert temporal.repository == "repo1"
        assert temporal.commit_sha == "abc123"
        assert temporal.time_diff_hours == 2.5
        assert temporal.correlation_strength == 0.8

    def test_intelligence_stats_data_creation(self):
        """Test IntelligenceStatsData creation and attributes."""
        stats = IntelligenceStatsData(
            total_changes=50,
            total_correlations=10,
            average_correlation_strength=0.75,
            breaking_changes=2,
            repositories_active=5,
            correlation_strengths=[0.8, 0.7, 0.75],
            repositories_list=["repo1", "repo2", "repo3"],
        )

        assert stats.total_changes == 50
        assert stats.total_correlations == 10
        assert stats.average_correlation_strength == 0.75
        assert stats.breaking_changes == 2
        assert stats.repositories_active == 5
        assert stats.correlation_strengths == [0.8, 0.7, 0.75]
        assert stats.repositories_list == ["repo1", "repo2", "repo3"]


class TestIntegrationScenarios:
    """Integration test scenarios for realistic data quality verification."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock database client for testing."""
        client = Mock()
        client.table.return_value = client
        client.select.return_value = client
        client.order.return_value = client
        return client

    def test_data_consistency_across_formats(self, mock_client):
        """Test that data parsing is consistent across different formats."""
        data_access = IntelligenceDataAccess(mock_client)

        # Test MCP format
        mcp_content = {
            "metadata": {
                "repository": "test-repo",
                "timestamp": "2023-01-01T12:00:00Z",
            },
            "code_changes_analysis": {
                "changed_files": ["src/main.py", "tests/test.py"]
            },
            "cross_repository_correlation": {
                "temporal_correlations": [
                    {
                        "repository": "related-repo",
                        "commit": "def456",
                        "time_window": "24h",
                        "correlation_strength": "high",
                    }
                ]
            },
        }

        # Test legacy format
        legacy_content = {
            "diff_analysis": {
                "total_changes": 2,
                "added_lines": 50,
                "removed_lines": 20,
                "modified_files": ["src/main.py", "tests/test.py"],
            },
            "correlation_analysis": {
                "temporal_correlations": [
                    {
                        "repository": "related-repo",
                        "commit_sha": "def456",
                        "time_diff_hours": 24.0,
                        "correlation_strength": 0.9,
                    }
                ]
            },
        }

        # Parse both formats
        mcp_diff = data_access.parse_diff_analysis(mcp_content)
        legacy_diff = data_access.parse_diff_analysis(legacy_content)

        mcp_temporal, _, _ = data_access.parse_correlations(mcp_content)
        legacy_temporal, _, _ = data_access.parse_correlations(legacy_content)

        # Verify consistent data extraction
        assert mcp_diff.total_changes == legacy_diff.total_changes
        assert mcp_diff.modified_files == legacy_diff.modified_files

        assert len(mcp_temporal) == len(legacy_temporal) == 1
        assert mcp_temporal[0].repository == legacy_temporal[0].repository
        assert mcp_temporal[0].time_diff_hours == legacy_temporal[0].time_diff_hours
        assert (
            mcp_temporal[0].correlation_strength
            == legacy_temporal[0].correlation_strength
        )

    def test_data_quality_validation(self, mock_client):
        """Test data quality validation for edge cases."""
        data_access = IntelligenceDataAccess(mock_client)

        # Test malformed content
        malformed_content = {
            "correlation_analysis": {
                "temporal_correlations": [
                    {
                        # Missing required fields
                        "repository": "repo1"
                        # commit_sha missing, time_diff_hours missing
                    }
                ]
            }
        }

        temporal, semantic, breaking = data_access.parse_correlations(malformed_content)

        # Should handle missing fields gracefully
        assert len(temporal) == 1
        assert temporal[0].repository == "repo1"
        assert temporal[0].commit_sha == ""  # Default value
        assert temporal[0].time_diff_hours == 0.0  # Default value
        assert temporal[0].correlation_strength == 0.0  # Default value


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
