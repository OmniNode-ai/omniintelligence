"""
Comprehensive unit tests for intelligence data access layer.

Converted from the original validation script with proper pytest structure,
comprehensive fixtures, and detailed assertions.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from src.server.data.intelligence_data_access import (
    BreakingChangeData,
    DiffAnalysisData,
    IntelligenceDataAccess,
    IntelligenceDocumentData,
    IntelligenceStatsData,
    QueryParameters,
    TemporalCorrelationData,
    TimeRange,
    create_intelligence_data_access,
)


class TestIntelligenceDataAccessValidation:
    """
    Test cases converted from the original validation script.

    These tests validate the core functionality that was previously
    tested via the shell script approach.
    """

    @pytest.fixture
    def mock_database_client(self):
        """Create comprehensive mock database client."""
        client = Mock()

        # Setup method chaining
        mock_table = Mock()
        mock_select = Mock()

        # Configure execute to return controllable data
        mock_execute = Mock()
        mock_execute.data = []

        mock_select.execute.return_value = mock_execute
        mock_select.order.return_value = mock_select
        mock_table.select.return_value = mock_select
        client.table.return_value = mock_table

        return client

    @pytest.fixture
    def data_access_instance(self, mock_database_client):
        """Create data access instance with mock client."""
        return IntelligenceDataAccess(mock_database_client)

    def test_time_range_parsing_validation(self, data_access_instance):
        """
        Test time range parsing functionality.

        Converted from validate_time_range_parsing() in the original script.
        """
        test_cases = [
            ("1h", 1),
            ("6h", 6),
            ("24h", 24),
            ("72h", 72),
            ("7d", 168),
            ("invalid", 24),  # Should default to 24h
            ("", 24),  # Empty string defaults to 24h
            ("999x", 24),  # Invalid format defaults to 24h
        ]

        for time_range, expected in test_cases:
            result = data_access_instance.parse_time_range(time_range)
            assert (
                result == expected
            ), f"Time range parsing failed: {time_range} -> {result} (expected {expected})"

    def test_document_parsing_mcp_format(
        self, data_access_instance, sample_mcp_intelligence_document
    ):
        """Test document parsing for MCP format."""
        content = sample_mcp_intelligence_document["content"]

        # Test diff analysis parsing
        diff_analysis = data_access_instance.parse_diff_analysis(content)
        assert diff_analysis is not None
        assert diff_analysis.total_changes == 3  # Number of changed files
        assert diff_analysis.modified_files == [
            "src/server/api_routes/intelligence_api.py",
            "src/server/data/intelligence_data_access.py",
            "tests/test_intelligence_integration.py",
        ]

        # Test correlation parsing
        temporal, semantic, breaking = data_access_instance.parse_correlations(content)

        assert len(temporal) == 2
        assert temporal[0].repository == "Related-Service"
        assert temporal[0].time_diff_hours == 6.0  # Converted from "6h"
        assert temporal[0].correlation_strength == 0.9  # "high" -> 0.9

        assert len(semantic) == 1
        assert semantic[0].repository == "Auth-Service"
        assert semantic[0].semantic_similarity == 0.85

        assert len(breaking) == 1
        assert breaking[0].type == "API_CHANGE"
        assert breaking[0].severity == "HIGH"

        # Test security analysis parsing
        security = data_access_instance.parse_security_analysis(content)
        assert security is not None
        assert security.patterns_detected == [
            "JWT token validation",
            "Input sanitization",
        ]
        assert security.risk_level == "LOW"
        assert security.secure_patterns == 2

    def test_document_parsing_legacy_format(
        self, data_access_instance, sample_legacy_intelligence_document
    ):
        """Test document parsing for legacy git hook format."""
        content = sample_legacy_intelligence_document["content"]

        # Test diff analysis parsing
        diff_analysis = data_access_instance.parse_diff_analysis(content)
        assert diff_analysis is not None
        assert diff_analysis.total_changes == 5
        assert diff_analysis.added_lines == 142
        assert diff_analysis.removed_lines == 38
        assert len(diff_analysis.modified_files) == 3

        # Test correlation parsing
        temporal, semantic, breaking = data_access_instance.parse_correlations(content)

        assert len(temporal) == 1
        assert temporal[0].repository == "Data-Pipeline"
        assert temporal[0].time_diff_hours == 4.5
        assert temporal[0].correlation_strength == 0.9

        assert len(semantic) == 1
        assert semantic[0].semantic_similarity == 0.72
        assert semantic[0].common_keywords == [
            "data",
            "analysis",
            "intelligence",
            "correlation",
        ]

        assert len(breaking) == 0  # No breaking changes in this sample

    def test_document_parsing_project_format(
        self, data_access_instance, sample_project_intelligence_document
    ):
        """Test document parsing for project quality assessment format."""
        content = sample_project_intelligence_document["content"]

        # Test diff analysis parsing
        diff_analysis = data_access_instance.parse_diff_analysis(content)
        assert diff_analysis is not None
        assert diff_analysis.total_changes == 2  # files_changed from repository_info
        assert diff_analysis.modified_files == [
            "src/core/validators.py",
            "tests/test_validators.py",
        ]

        # Test security analysis parsing (derived from quality metrics)
        security = data_access_instance.parse_security_analysis(content)
        assert security is not None
        assert "No anti-patterns detected" in security.patterns_detected
        assert "High architectural compliance" in security.patterns_detected
        assert "Strong type safety" in security.patterns_detected
        assert security.risk_level == "LOW"
        assert security.secure_patterns == 3

    def test_document_parsing_malformed_data(
        self, data_access_instance, sample_malformed_document
    ):
        """Test graceful handling of malformed document data."""
        content = sample_malformed_document["content"]

        # Should handle missing fields gracefully
        temporal, semantic, breaking = data_access_instance.parse_correlations(content)

        # Should still parse what's available, with defaults for missing fields
        assert len(temporal) == 1
        assert temporal[0].repository == ""  # Missing repository
        assert temporal[0].commit_sha == ""  # Missing commit_sha
        assert temporal[0].time_diff_hours == 2.0  # Present in data
        assert temporal[0].correlation_strength == 0.0  # Missing, defaults to 0.0

        # Diff analysis should handle missing required fields
        diff_analysis = data_access_instance.parse_diff_analysis(content)
        assert diff_analysis is not None
        assert diff_analysis.total_changes == 0  # Missing total_changes
        assert diff_analysis.modified_files == []

    def test_document_parsing_empty_data(
        self, data_access_instance, sample_empty_document
    ):
        """Test parsing of empty document content."""
        content = sample_empty_document["content"]

        # Should return None/empty for all parsing operations
        diff_analysis = data_access_instance.parse_diff_analysis(content)
        assert diff_analysis is None

        temporal, semantic, breaking = data_access_instance.parse_correlations(content)
        assert len(temporal) == 0
        assert len(semantic) == 0
        assert len(breaking) == 0

        security = data_access_instance.parse_security_analysis(content)
        assert security is None

    def test_document_metadata_parsing_intelligence_type(self, data_access_instance):
        """Test parsing metadata from intelligence-type documents."""
        doc = {
            "document_type": "intelligence",
            "metadata": {"fallback": "value"},
            "content": {
                "metadata": {
                    "repository": "Primary-Repo",
                    "commit": "primary-commit-123",
                    "author": "primary-author",
                    "change_type": "feature",
                }
            },
        }

        (
            repository,
            commit_sha,
            author,
            change_type,
        ) = data_access_instance.parse_document_metadata(doc)

        # Should prioritize content.metadata over doc.metadata
        assert repository == "Primary-Repo"
        assert commit_sha == "primary-commit-123"
        assert author == "primary-author"
        assert change_type == "feature"

    def test_document_metadata_parsing_project_type(self, data_access_instance):
        """Test parsing metadata from project-type documents."""
        doc = {
            "document_type": "spec",
            "author": "project-author",
            "content": {
                "repository_info": {
                    "repository": "Project-Repo",
                    "commit": "project-commit-456",
                },
                "update_type": "enhancement",
            },
        }

        (
            repository,
            commit_sha,
            author,
            change_type,
        ) = data_access_instance.parse_document_metadata(doc)

        assert repository == "Project-Repo"
        assert commit_sha == "project-commit-456"
        assert author == "project-author"
        assert change_type == "enhancement"

    def test_extract_intelligence_documents_filtering(
        self, data_access_instance, sample_project_with_intelligence_docs
    ):
        """Test extraction and filtering of intelligence documents from projects."""
        projects = [sample_project_with_intelligence_docs]
        cutoff_time = datetime.now(UTC) - timedelta(hours=24)

        # Test without repository filter
        result = data_access_instance.extract_intelligence_documents_from_projects(
            projects, cutoff_time
        )

        # Should extract 2 documents (doc-001 and doc-003), filtering out doc-002 (no intelligence tags)
        assert len(result) == 2
        assert result[0]["id"] == "doc-001"
        assert result[1]["id"] == "doc-003"

        # Test with repository filter
        result_filtered = (
            data_access_instance.extract_intelligence_documents_from_projects(
                projects, cutoff_time, repository_filter="Quality-Repo"
            )
        )

        # Should only return doc-003 which has Quality-Repo
        assert len(result_filtered) == 1
        assert result_filtered[0]["id"] == "doc-003"

    def test_get_raw_documents_empty_response(
        self, data_access_instance, mock_database_client
    ):
        """Test handling of empty database response."""
        # Configure mock to return empty data
        mock_database_client.table().select().order().execute.return_value.data = []

        params = QueryParameters(time_range="24h", limit=50)
        result = data_access_instance.get_raw_documents(params)

        assert result["success"] is True
        assert result["documents"] == []
        assert result["total_count"] == 0
        assert result["error"] is None

    def test_get_raw_documents_database_error(
        self, data_access_instance, mock_database_client
    ):
        """Test handling of database errors."""
        # Configure mock to raise exception
        mock_database_client.table().select().order().execute.side_effect = Exception(
            "Database connection failed"
        )

        params = QueryParameters(time_range="24h", limit=50)
        result = data_access_instance.get_raw_documents(params)

        assert result["success"] is False
        assert result["documents"] == []
        assert result["total_count"] == 0
        assert "Database connection failed" in result["error"]

    def test_statistics_calculation_empty_data(
        self, data_access_instance, mock_database_client
    ):
        """Test statistics calculation with empty dataset."""
        # Configure mock to return empty data
        mock_database_client.table().select().order().execute.return_value.data = []

        params = QueryParameters(time_range="24h")
        stats = data_access_instance.calculate_statistics(params)

        assert stats.total_changes == 0
        assert stats.total_correlations == 0
        assert stats.average_correlation_strength == 0.0
        assert stats.breaking_changes == 0
        assert stats.repositories_active == 0
        assert stats.correlation_strengths == []
        assert stats.repositories_list == []

    def test_statistics_calculation_with_data(
        self,
        data_access_instance,
        mock_database_client,
        sample_project_with_intelligence_docs,
    ):
        """Test statistics calculation with actual data."""
        # Configure mock to return project data
        mock_database_client.table().select().order().execute.return_value.data = [
            sample_project_with_intelligence_docs
        ]

        params = QueryParameters(time_range="24h")

        with patch.object(
            data_access_instance, "get_parsed_documents"
        ) as mock_get_parsed:
            # Mock parsed documents with correlation data
            mock_documents = [
                IntelligenceDocumentData(
                    id="doc-1",
                    created_at="2023-01-01T12:00:00Z",
                    repository="Repo-A",
                    commit_sha="commit-1",
                    author="author-1",
                    change_type="feature",
                    diff_analysis=DiffAnalysisData(1, 10, 5, ["file.py"]),
                    temporal_correlations=[
                        TemporalCorrelationData("Repo-B", "commit-2", 2.0, 0.8),
                        TemporalCorrelationData("Repo-C", "commit-3", 4.0, 0.6),
                    ],
                    semantic_correlations=[],
                    breaking_changes=[
                        BreakingChangeData(
                            "API_CHANGE", "HIGH", "Changed API", ["api.py"]
                        )
                    ],
                    security_analysis=None,
                    raw_content={},
                ),
                IntelligenceDocumentData(
                    id="doc-2",
                    created_at="2023-01-01T11:00:00Z",
                    repository="Repo-B",
                    commit_sha="commit-4",
                    author="author-2",
                    change_type="bugfix",
                    diff_analysis=DiffAnalysisData(2, 20, 10, ["bug.py"]),
                    temporal_correlations=[
                        TemporalCorrelationData("Repo-A", "commit-1", 1.0, 0.9)
                    ],
                    semantic_correlations=[],
                    breaking_changes=[],
                    security_analysis=None,
                    raw_content={},
                ),
            ]
            mock_get_parsed.return_value = mock_documents

            stats = data_access_instance.calculate_statistics(params)

            assert stats.total_changes == 2
            assert stats.total_correlations == 3  # 2 + 1
            assert (
                stats.average_correlation_strength == (0.8 + 0.6 + 0.9) / 3
            )  # Average of all correlations
            assert stats.breaking_changes == 1
            assert stats.repositories_active == 2  # Repo-A and Repo-B
            assert len(stats.correlation_strengths) == 3
            assert set(stats.repositories_list) == {"Repo-A", "Repo-B"}

    def test_get_active_repositories(self, data_access_instance, mock_database_client):
        """Test retrieval of active repositories."""
        # Configure mock to return project data with intelligence documents
        mock_project_data = [
            {
                "id": "proj-1",
                "title": "Project 1",
                "docs": [
                    {
                        "tags": ["intelligence", "pre-push"],
                        "content": {"metadata": {"repository": "Repo-Alpha"}},
                    },
                    {
                        "tags": ["documentation"],  # Should be ignored
                        "content": {"description": "Docs"},
                    },
                ],
            },
            {
                "id": "proj-2",
                "title": "Project 2",
                "docs": [
                    {
                        "tags": ["quality-assessment"],
                        "content": {
                            "repository_info": {
                                "repository": "Repo-Beta"
                            }  # Legacy format
                        },
                    }
                ],
            },
        ]

        mock_database_client.table().select().execute.return_value.data = (
            mock_project_data
        )

        repositories = data_access_instance.get_active_repositories()

        assert len(repositories) == 2
        assert "Repo-Alpha" in repositories
        assert "Repo-Beta" in repositories
        assert repositories == sorted(repositories)  # Should be sorted

    def test_get_active_repositories_error_handling(
        self, data_access_instance, mock_database_client
    ):
        """Test error handling in get_active_repositories."""
        # Configure mock to raise exception
        mock_database_client.table().select().execute.side_effect = Exception(
            "Database error"
        )

        repositories = data_access_instance.get_active_repositories()

        assert repositories == []  # Should return empty list on error


class TestIntelligenceDataAccessIntegration:
    """Integration tests for the data access layer."""

    @pytest.fixture
    def data_access_instance(self, mock_database_client):
        """Create data access instance."""
        return IntelligenceDataAccess(mock_database_client)

    def test_end_to_end_document_processing(
        self,
        data_access_instance,
        mock_database_client,
        sample_mcp_intelligence_document,
        sample_legacy_intelligence_document,
    ):
        """Test complete document processing pipeline."""
        project_data = [
            {
                "id": "integration-proj",
                "title": "Integration Test Project",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "docs": [
                    sample_mcp_intelligence_document,
                    sample_legacy_intelligence_document,
                ],
            }
        ]

        mock_database_client.table().select().order().execute.return_value.data = (
            project_data
        )

        params = QueryParameters(time_range="24h", limit=100)

        # Test raw document retrieval
        raw_result = data_access_instance.get_raw_documents(params)
        assert raw_result["success"] is True
        assert len(raw_result["documents"]) == 2

        # Test parsed document retrieval
        parsed_docs = data_access_instance.get_parsed_documents(params)
        assert len(parsed_docs) == 2

        # Verify MCP document was parsed correctly
        mcp_doc = next(doc for doc in parsed_docs if doc.id == "doc-mcp-001")
        assert mcp_doc.repository == "Archon"
        assert mcp_doc.commit_sha == "abc123def456"
        assert len(mcp_doc.temporal_correlations) == 2
        assert len(mcp_doc.breaking_changes) == 1

        # Verify legacy document was parsed correctly
        legacy_doc = next(doc for doc in parsed_docs if doc.id == "doc-legacy-001")
        assert legacy_doc.repository == "Archon-Legacy"
        assert legacy_doc.diff_analysis.total_changes == 5
        assert legacy_doc.diff_analysis.added_lines == 142

        # Test statistics calculation
        stats = data_access_instance.calculate_statistics(params)
        assert stats.total_changes == 2
        assert stats.repositories_active == 2  # Archon and Archon-Legacy
        assert "Archon" in stats.repositories_list
        assert "Archon-Legacy" in stats.repositories_list

    def test_performance_with_large_dataset(
        self, data_access_instance, mock_database_client, performance_test_dataset
    ):
        """Test performance with large datasets."""
        import time

        # Create large project dataset
        project_data = [
            {
                "id": "perf-proj",
                "title": "Performance Test Project",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "docs": performance_test_dataset["documents"],
            }
        ]

        mock_database_client.table().select().order().execute.return_value.data = (
            project_data
        )

        params = QueryParameters(time_range="7d", limit=1000)

        # Measure parsing performance
        start_time = time.time()
        parsed_docs = data_access_instance.get_parsed_documents(params)
        parsing_time = time.time() - start_time

        # Measure statistics calculation performance
        start_time = time.time()
        stats = data_access_instance.calculate_statistics(params)
        stats_time = time.time() - start_time

        # Verify results
        assert len(parsed_docs) == performance_test_dataset["expected_total_changes"]
        assert (
            stats.repositories_active
            == performance_test_dataset["expected_repositories"]
        )
        assert (
            stats.total_correlations
            == performance_test_dataset["expected_correlations"]
        )

        # Performance assertions (should complete within reasonable time)
        assert (
            parsing_time < 5.0
        ), f"Document parsing took {parsing_time:.2f}s, expected < 5.0s"
        assert (
            stats_time < 2.0
        ), f"Statistics calculation took {stats_time:.2f}s, expected < 2.0s"

    def test_factory_function(self, mock_database_client):
        """Test the factory function for creating data access instances."""
        instance = create_intelligence_data_access(mock_database_client)

        assert isinstance(instance, IntelligenceDataAccess)
        assert instance.client is mock_database_client


class TestQueryParametersAndDataStructures:
    """Test query parameters and data structure classes."""

    def test_query_parameters_defaults(self):
        """Test QueryParameters default values."""
        params = QueryParameters()

        assert params.repository is None
        assert params.time_range == "24h"
        assert params.limit == 50
        assert params.offset == 0

    def test_query_parameters_custom_values(self):
        """Test QueryParameters with custom values."""
        params = QueryParameters(
            repository="custom-repo", time_range="7d", limit=200, offset=100
        )

        assert params.repository == "custom-repo"
        assert params.time_range == "7d"
        assert params.limit == 200
        assert params.offset == 100

    def test_data_structure_creation_and_equality(self):
        """Test data structure creation and equality."""
        # Test DiffAnalysisData
        diff1 = DiffAnalysisData(10, 100, 50, ["file1.py", "file2.js"])
        diff2 = DiffAnalysisData(10, 100, 50, ["file1.py", "file2.js"])

        assert diff1.total_changes == diff2.total_changes
        assert diff1.modified_files == diff2.modified_files

        # Test TemporalCorrelationData
        temporal1 = TemporalCorrelationData("repo1", "commit1", 2.5, 0.8)
        temporal2 = TemporalCorrelationData("repo1", "commit1", 2.5, 0.8)

        assert temporal1.repository == temporal2.repository
        assert temporal1.time_diff_hours == temporal2.time_diff_hours
        assert temporal1.correlation_strength == temporal2.correlation_strength

        # Test IntelligenceStatsData
        stats1 = IntelligenceStatsData(
            100, 25, 0.75, 5, 10, [0.8, 0.7, 0.75], ["repo1", "repo2"]
        )
        stats2 = IntelligenceStatsData(
            100, 25, 0.75, 5, 10, [0.8, 0.7, 0.75], ["repo1", "repo2"]
        )

        assert stats1.total_changes == stats2.total_changes
        assert (
            stats1.average_correlation_strength == stats2.average_correlation_strength
        )
        assert stats1.repositories_list == stats2.repositories_list

    def test_time_range_enum(self):
        """Test TimeRange enum values."""
        assert TimeRange.ONE_HOUR.value == "1h"
        assert TimeRange.SIX_HOURS.value == "6h"
        assert TimeRange.TWENTY_FOUR_HOURS.value == "24h"
        assert TimeRange.SEVENTY_TWO_HOURS.value == "72h"
        assert TimeRange.SEVEN_DAYS.value == "7d"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
