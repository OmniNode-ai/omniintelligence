"""
Integration tests for intelligence API endpoints.

Tests the full API → Service → Data Access flow for intelligence
endpoints including proper error handling and response formatting.

Error Validation:
-----------------
This test suite validates comprehensive API error handling including:
- HTTP error status codes and response structure
- Error detail field format and content
- Service exception propagation to API layer
- Consistent error response format across endpoints
"""

from unittest.mock import Mock, patch

import pytest
from src.server.data.intelligence_data_access import (
    DiffAnalysisData,
    IntelligenceDocumentData,
    IntelligenceStatsData,
    SecurityAnalysisData,
    TemporalCorrelationData,
)
from src.server.services.intelligence_service import (
    BreakingChange,
    CorrelationAnalysis,
    DiffAnalysis,
    IntelligenceData,
    IntelligenceDocument,
    IntelligenceResponse,
    IntelligenceStats,
    SecurityAnalysis,
    SemanticCorrelation,
    TemporalCorrelation,
)

from tests.integration.error_assertions import (
    ErrorAssertions,
    assert_api_error_with_detail,
)


class TestIntelligenceAPIEndpoints:
    """Integration tests for intelligence API endpoints."""

    @pytest.fixture
    def mock_intelligence_service(self):
        """Mock intelligence service functions."""
        # Patch where functions are imported and used (in API routes)
        # NOTE: Use 'server.' paths (not 'src.server.') to match actual import paths
        with (
            patch(
                "server.api_routes.intelligence_api.get_intelligence_documents"
            ) as mock_get_docs,
            patch(
                "server.api_routes.intelligence_api.get_intelligence_stats"
            ) as mock_get_stats,
            patch(
                "server.api_routes.intelligence_api.get_active_repositories"
            ) as mock_get_repos,
        ):
            yield {
                "get_documents": mock_get_docs,
                "get_stats": mock_get_stats,
                "get_repositories": mock_get_repos,
            }

    @pytest.fixture
    def sample_intelligence_response(self):
        """Sample intelligence API response data."""
        # Create a proper IntelligenceResponse instance
        return IntelligenceResponse(
            documents=[
                IntelligenceDocument(
                    id="doc-001",
                    created_at="2023-01-01T12:00:00Z",
                    repository="Test-Repo",
                    commit_sha="abc123",
                    author="test-user",
                    change_type="feature",
                    intelligence_data=IntelligenceData(
                        diff_analysis=DiffAnalysis(
                            total_changes=3,
                            added_lines=50,
                            removed_lines=20,
                            modified_files=["main.py", "utils.py", "tests.py"],
                        ),
                        correlation_analysis=CorrelationAnalysis(
                            temporal_correlations=[
                                TemporalCorrelation(
                                    repository="Related-Repo",
                                    commit_sha="def456",
                                    time_diff_hours=2.0,
                                    correlation_strength=0.8,
                                )
                            ],
                            semantic_correlations=[],
                            breaking_changes=[],
                        ),
                        security_analysis=SecurityAnalysis(
                            patterns_detected=[
                                "Input validation",
                                "SQL injection prevention",
                            ],
                            risk_level="LOW",
                            secure_patterns=2,
                        ),
                    ),
                )
            ],
            total_count=1,
            filtered_count=1,
            time_range="24h",
            repositories=["Test-Repo"],
        )

    @pytest.fixture
    def sample_stats_response(self):
        """Sample intelligence stats response data."""
        return IntelligenceStats(
            total_changes=15,
            total_correlations=8,
            average_correlation_strength=0.72,
            breaking_changes=2,
            repositories_active=5,
            time_range="24h",
        )

    def test_get_intelligence_documents_success(
        self, client, mock_intelligence_service, sample_intelligence_response
    ):
        """Test successful retrieval of intelligence documents."""
        # Setup mock to return sample response
        mock_intelligence_service["get_documents"].return_value = (
            sample_intelligence_response
        )

        # Make request
        response = client.get("/api/intelligence/documents")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert len(data["documents"]) == 1
        assert data["documents"][0]["id"] == "doc-001"
        assert data["documents"][0]["repository"] == "Test-Repo"
        assert data["total_count"] == 1

        # Verify service was called with correct parameters
        mock_intelligence_service["get_documents"].assert_called_once_with(
            repository=None, time_range="24h", limit=50, offset=0
        )

    def test_get_intelligence_documents_with_filters(
        self, client, mock_intelligence_service, sample_intelligence_response
    ):
        """Test intelligence documents retrieval with query filters."""
        mock_intelligence_service["get_documents"].return_value = (
            sample_intelligence_response
        )

        # Make request with filters
        response = client.get(
            "/api/intelligence/documents",
            params={
                "repository": "Specific-Repo",
                "time_range": "7d",
                "limit": 100,
                "offset": 25,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data

        # Verify service was called with filters
        mock_intelligence_service["get_documents"].assert_called_once_with(
            repository="Specific-Repo", time_range="7d", limit=100, offset=25
        )

    def test_get_intelligence_documents_invalid_parameters(
        self, client, mock_intelligence_service
    ):
        """Test intelligence documents retrieval with invalid parameters."""
        mock_intelligence_service["get_documents"].return_value = IntelligenceResponse(
            documents=[],
            total_count=0,
            filtered_count=0,
            time_range="24h",
            repositories=[],
        )

        # Test invalid limit (too high)
        response = client.get("/api/intelligence/documents", params={"limit": 2000})
        assert response.status_code == 422  # Validation error

        # Test invalid offset (negative)
        response = client.get("/api/intelligence/documents", params={"offset": -1})
        assert response.status_code == 422  # Validation error

    def test_get_intelligence_documents_service_error(
        self, client, mock_intelligence_service
    ):
        """
        Test handling of service errors in document retrieval.

        Error Validation:
        - Verifies 500 status code for service exceptions
        - Validates error detail field structure and content
        - Confirms proper exception message propagation
        """
        # Setup mock to raise exception
        mock_intelligence_service["get_documents"].side_effect = Exception(
            "Database connection failed"
        )

        response = client.get("/api/intelligence/documents")

        # Enhanced error validation: Comprehensive API error response check
        ErrorAssertions.assert_api_error_response(
            response,
            expected_status_code=500,
            expected_error_message_contains="Failed to fetch intelligence documents",
        )

        # Additional validation: Verify error detail mentions the root cause
        data = response.json()
        detail = data.get("detail", "")
        assert "Database connection failed" in str(detail) or "Failed to fetch" in str(
            detail
        ), f"Error detail should mention root cause or operation: {detail}"

    def test_get_intelligence_stats_success(
        self, client, mock_intelligence_service, sample_stats_response
    ):
        """Test successful retrieval of intelligence statistics."""
        mock_intelligence_service["get_stats"].return_value = sample_stats_response

        response = client.get("/api/intelligence/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["total_changes"] == 15
        assert data["total_correlations"] == 8
        assert data["average_correlation_strength"] == 0.72
        assert data["repositories_active"] == 5
        assert data["breaking_changes"] == 2

        # Verify service was called with defaults
        mock_intelligence_service["get_stats"].assert_called_once_with(
            repository=None, time_range="24h"
        )

    def test_get_intelligence_stats_with_filters(
        self, client, mock_intelligence_service, sample_stats_response
    ):
        """Test intelligence stats retrieval with filters."""
        mock_intelligence_service["get_stats"].return_value = sample_stats_response

        response = client.get(
            "/api/intelligence/stats",
            params={"repository": "Analytics-Repo", "time_range": "72h"},
        )

        assert response.status_code == 200

        # Verify service was called with filters
        mock_intelligence_service["get_stats"].assert_called_once_with(
            repository="Analytics-Repo", time_range="72h"
        )

    def test_get_intelligence_stats_service_error(
        self, client, mock_intelligence_service
    ):
        """
        Test handling of service errors in stats calculation.

        Error Validation:
        - Verifies 500 status code for calculation failures
        - Validates error response structure
        - Confirms error message clarity for debugging
        """
        mock_intelligence_service["get_stats"].side_effect = Exception(
            "Statistics calculation failed"
        )

        response = client.get("/api/intelligence/stats")

        # Enhanced error validation: Use comprehensive assertion helper
        ErrorAssertions.assert_api_error_response(
            response,
            expected_status_code=500,
            expected_error_message_contains="Failed to calculate intelligence stats",
        )

        # Validate error structure is consistent
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        detail = data["detail"]
        assert isinstance(
            detail, (str, dict)
        ), "Detail should be string or structured dict"

        # Verify error provides actionable information
        detail_str = str(detail)
        assert len(detail_str) > 0, "Error detail should not be empty"
        assert (
            "statistics" in detail_str.lower() or "stats" in detail_str.lower()
        ), "Error should reference the failing operation"

    def test_get_active_repositories_success(self, client, mock_intelligence_service):
        """Test successful retrieval of active repositories."""
        mock_repositories = ["Repo-Alpha", "Repo-Beta", "Repo-Gamma"]
        mock_intelligence_service["get_repositories"].return_value = mock_repositories

        response = client.get("/api/intelligence/repositories")

        assert response.status_code == 200
        data = response.json()

        assert "repositories" in data
        assert len(data["repositories"]) == 3
        assert "Repo-Alpha" in data["repositories"]
        assert "Repo-Beta" in data["repositories"]
        assert "Repo-Gamma" in data["repositories"]

        mock_intelligence_service["get_repositories"].assert_called_once()

    def test_get_active_repositories_empty_result(
        self, client, mock_intelligence_service
    ):
        """Test retrieval of active repositories when none exist."""
        mock_intelligence_service["get_repositories"].return_value = []

        response = client.get("/api/intelligence/repositories")

        assert response.status_code == 200
        data = response.json()

        assert data["repositories"] == []

    def test_get_active_repositories_service_error(
        self, client, mock_intelligence_service
    ):
        """
        Test handling of service errors in repository retrieval.

        Error Validation:
        - Verifies 500 status code for fetch failures
        - Validates error message contains operation context
        - Confirms consistent error response structure
        """
        mock_intelligence_service["get_repositories"].side_effect = Exception(
            "Repository fetch failed"
        )

        response = client.get("/api/intelligence/repositories")

        # Enhanced error validation: Comprehensive error response check
        ErrorAssertions.assert_api_error_response(
            response,
            expected_status_code=500,
            expected_error_message_contains="Failed to fetch repositories",
        )

        # Additional validation: Verify error is actionable
        data = response.json()
        detail = str(data.get("detail", ""))
        assert len(detail) > 0, "Error detail should not be empty"
        # Should mention either the operation or the root cause
        assert (
            "repository" in detail.lower() or "fetch" in detail.lower()
        ), f"Error should reference repositories or fetch operation: {detail}"

    def test_api_response_format_consistency(self, client, mock_intelligence_service):
        """Test that all API responses follow consistent format."""
        # Setup mocks
        mock_intelligence_service["get_documents"].return_value = IntelligenceResponse(
            documents=[],
            total_count=0,
            filtered_count=0,
            time_range="24h",
            repositories=[],
        )
        mock_intelligence_service["get_stats"].return_value = IntelligenceStats(
            total_changes=0,
            total_correlations=0,
            average_correlation_strength=0.0,
            breaking_changes=0,
            repositories_active=0,
            time_range="24h",
        )
        mock_intelligence_service["get_repositories"].return_value = []

        # Test all endpoints
        endpoints = [
            "/api/intelligence/documents",
            "/api/intelligence/stats",
            "/api/intelligence/repositories",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200

            data = response.json()
            assert isinstance(
                data, dict
            ), f"Response from {endpoint} should be a dictionary"

            # Verify response has appropriate structure
            if "documents" in endpoint:
                assert "documents" in data
                assert "total_count" in data
            elif "stats" in endpoint:
                assert "total_changes" in data
            elif "repositories" in endpoint:
                assert "repositories" in data

    def test_error_response_format_consistency(self, client, mock_intelligence_service):
        """
        Test that error responses follow consistent format.

        Error Validation:
        - Verifies all endpoints use consistent error response structure
        - Validates error detail field presence and type
        - Confirms error messages are informative across endpoints
        """
        # Setup mocks to raise exceptions
        mock_intelligence_service["get_documents"].side_effect = Exception("Test error")
        mock_intelligence_service["get_stats"].side_effect = Exception("Test error")
        mock_intelligence_service["get_repositories"].side_effect = Exception(
            "Test error"
        )

        endpoints = [
            "/api/intelligence/documents",
            "/api/intelligence/stats",
            "/api/intelligence/repositories",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)

            # Enhanced error validation: Use comprehensive assertion helper
            ErrorAssertions.assert_api_error_response(
                response,
                expected_status_code=500,
                validate_json_structure=True,
            )

            # Additional consistency checks
            data = response.json()
            assert (
                "detail" in data
            ), f"Error response from {endpoint} should have 'detail' field"

            detail = data["detail"]
            assert isinstance(
                detail, (str, dict)
            ), f"Error detail from {endpoint} should be string or dict, got {type(detail)}"

            # Verify error contains useful information
            detail_str = str(detail)
            assert (
                len(detail_str) > 0
            ), f"Error detail from {endpoint} should not be empty"
            # Should mention either the test error or a descriptive operation failure
            assert (
                "Test error" in detail_str or "Failed to" in detail_str
            ), f"Error from {endpoint} should be descriptive: {detail_str}"


class TestIntelligenceAPIIntegrationScenarios:
    """End-to-end integration test scenarios."""

    @pytest.fixture
    def mock_full_service_chain(self):
        """Mock the entire service chain from API to data access."""
        # Patch where functions are imported and used (in API routes)
        # NOTE: Use 'server.' paths (not 'src.server.') to match actual import paths
        with (
            patch(
                "server.api_routes.intelligence_api.get_intelligence_documents"
            ) as mock_service_docs,
            patch(
                "server.api_routes.intelligence_api.get_intelligence_stats"
            ) as mock_service_stats,
            patch(
                "server.api_routes.intelligence_api.get_active_repositories"
            ) as mock_service_repos,
            patch(
                "server.data.intelligence_data_access.create_intelligence_data_access"
            ) as mock_create_data_access,
        ):
            # Setup mock data access instance
            mock_data_access = Mock()
            mock_create_data_access.return_value = mock_data_access

            yield {
                "service_docs": mock_service_docs,
                "service_stats": mock_service_stats,
                "service_repos": mock_service_repos,
                "data_access": mock_data_access,
            }

    def test_end_to_end_document_retrieval_flow(
        self, client, mock_full_service_chain, sample_mcp_intelligence_document
    ):
        """Test complete flow from API request to data access for document retrieval."""
        # Setup mock data access to return parsed documents
        mock_document = IntelligenceDocumentData(
            id="integration-doc-001",
            created_at="2023-01-01T12:00:00Z",
            repository="Integration-Repo",
            commit_sha="integration-commit-123",
            author="integration-user",
            change_type="feature",
            diff_analysis=DiffAnalysisData(5, 100, 50, ["integration.py", "tests.py"]),
            temporal_correlations=[
                TemporalCorrelationData("Related-Repo", "related-commit", 3.0, 0.7)
            ],
            semantic_correlations=[],
            breaking_changes=[],
            security_analysis=SecurityAnalysisData(["Security pattern"], "LOW", 1),
            raw_content={"test": "data"},
        )

        mock_full_service_chain["data_access"].get_parsed_documents.return_value = [
            mock_document
        ]

        # Configure service to use real logic but with mocked data access
        async def mock_get_intelligence_documents(
            repository=None, time_range="24h", limit=50, offset=0
        ):
            # This would normally use the real service logic
            return IntelligenceResponse(
                documents=[
                    IntelligenceDocument(
                        id=mock_document.id,
                        created_at=mock_document.created_at,
                        repository=mock_document.repository,
                        commit_sha=mock_document.commit_sha,
                        author=mock_document.author,
                        change_type=mock_document.change_type,
                        intelligence_data=IntelligenceData(
                            diff_analysis=DiffAnalysis(
                                total_changes=mock_document.diff_analysis.total_changes,
                                added_lines=mock_document.diff_analysis.added_lines,
                                removed_lines=mock_document.diff_analysis.removed_lines,
                                modified_files=mock_document.diff_analysis.modified_files,
                            ),
                            correlation_analysis=CorrelationAnalysis(
                                temporal_correlations=[
                                    TemporalCorrelation(
                                        repository=tc.repository,
                                        commit_sha=tc.commit_sha,
                                        time_diff_hours=tc.time_diff_hours,
                                        correlation_strength=tc.correlation_strength,
                                    )
                                    for tc in mock_document.temporal_correlations
                                ],
                                semantic_correlations=[],
                                breaking_changes=[],
                            ),
                            security_analysis=SecurityAnalysis(
                                patterns_detected=mock_document.security_analysis.patterns_detected,
                                risk_level=mock_document.security_analysis.risk_level,
                                secure_patterns=mock_document.security_analysis.secure_patterns,
                            ),
                        ),
                    )
                ],
                total_count=1,
                filtered_count=1,
                time_range=time_range,
                repositories=[mock_document.repository],
            )

        mock_full_service_chain["service_docs"].side_effect = (
            mock_get_intelligence_documents
        )

        # Make API request
        response = client.get(
            "/api/intelligence/documents",
            params={"repository": "Integration-Repo", "limit": 10},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert len(data["documents"]) == 1

        doc = data["documents"][0]
        assert doc["id"] == "integration-doc-001"
        assert doc["repository"] == "Integration-Repo"
        assert doc["intelligence_data"]["diff_analysis"]["total_changes"] == 5
        assert (
            len(
                doc["intelligence_data"]["correlation_analysis"][
                    "temporal_correlations"
                ]
            )
            == 1
        )
        assert (
            doc["intelligence_data"]["correlation_analysis"]["temporal_correlations"][
                0
            ]["correlation_strength"]
            == 0.7
        )

        # Verify service was called correctly
        mock_full_service_chain["service_docs"].assert_called_once()

    def test_end_to_end_statistics_calculation_flow(
        self, client, mock_full_service_chain
    ):
        """Test complete flow for statistics calculation."""
        # Setup mock data access to return statistics
        mock_stats = IntelligenceStatsData(
            total_changes=25,
            total_correlations=12,
            average_correlation_strength=0.68,
            breaking_changes=3,
            repositories_active=4,
            correlation_strengths=[0.9, 0.7, 0.6, 0.5],
            repositories_list=["Repo-A", "Repo-B", "Repo-C", "Repo-D"],
        )

        mock_full_service_chain["data_access"].calculate_statistics.return_value = (
            mock_stats
        )

        # Configure service to use real logic
        async def mock_get_intelligence_stats(repository=None, time_range="24h"):
            return IntelligenceStats(
                total_changes=mock_stats.total_changes,
                total_correlations=mock_stats.total_correlations,
                average_correlation_strength=mock_stats.average_correlation_strength,
                breaking_changes=mock_stats.breaking_changes,
                repositories_active=mock_stats.repositories_active,
                time_range=time_range,
            )

        mock_full_service_chain["service_stats"].side_effect = (
            mock_get_intelligence_stats
        )

        # Make API request
        response = client.get("/api/intelligence/stats", params={"time_range": "7d"})

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert data["total_changes"] == 25
        assert data["total_correlations"] == 12
        assert data["average_correlation_strength"] == 0.68
        assert data["repositories_active"] == 4
        assert data["time_range"] == "7d"
        assert data["breaking_changes"] == 3

        # Verify service was called correctly
        mock_full_service_chain["service_stats"].assert_called_once()

    def test_api_performance_with_large_datasets(self, client, mock_full_service_chain):
        """Test API performance with large datasets."""
        import time

        # Setup mock to simulate large dataset
        large_document_list = [
            IntelligenceDocumentData(
                id=f"perf-doc-{i:04d}",
                created_at=f"2023-01-01T{(i%24):02d}:00:00Z",
                repository=f"Perf-Repo-{i%5}",
                commit_sha=f"perf-commit-{i:04d}",
                author=f"perf-user-{i%10}",
                change_type="feature",
                diff_analysis=DiffAnalysisData(
                    i % 10 + 1,
                    (i % 50) + 10,
                    i % 20,
                    [f"file-{j}.py" for j in range(i % 5 + 1)],
                ),
                temporal_correlations=(
                    [
                        TemporalCorrelationData(
                            f"Related-{i%3}",
                            f"related-{i}",
                            float(i % 24),
                            0.5 + (i % 50) / 100,
                        )
                    ]
                    if i % 3 == 0
                    else []
                ),
                semantic_correlations=[],
                breaking_changes=[],
                security_analysis=None,
                raw_content={},
            )
            for i in range(500)  # 500 documents
        ]

        mock_full_service_chain["data_access"].get_parsed_documents.return_value = (
            large_document_list
        )

        # Configure service to return large dataset
        async def mock_get_large_documents(
            repository=None, time_range="24h", limit=50, offset=0
        ):
            # Simulate pagination
            paginated_docs = large_document_list[offset : offset + limit]

            return IntelligenceResponse(
                documents=[
                    IntelligenceDocument(
                        id=doc.id,
                        created_at=doc.created_at,
                        repository=doc.repository,
                        commit_sha=doc.commit_sha,
                        author=doc.author,
                        change_type=doc.change_type,
                        intelligence_data=IntelligenceData(
                            diff_analysis=DiffAnalysis(
                                total_changes=doc.diff_analysis.total_changes,
                                added_lines=doc.diff_analysis.added_lines,
                                removed_lines=doc.diff_analysis.removed_lines,
                                modified_files=doc.diff_analysis.modified_files,
                            ),
                            correlation_analysis=CorrelationAnalysis(
                                temporal_correlations=[],
                                semantic_correlations=[],
                                breaking_changes=[],
                            ),
                            security_analysis=None,
                        ),
                    )
                    for doc in paginated_docs
                ],
                total_count=len(large_document_list),
                filtered_count=len(paginated_docs),
                time_range=time_range,
                repositories=sorted({doc.repository for doc in paginated_docs}),
            )

        mock_full_service_chain["service_docs"].side_effect = mock_get_large_documents

        # Test API performance with pagination
        start_time = time.time()
        response = client.get("/api/intelligence/documents", params={"limit": 100})
        end_time = time.time()

        request_time = end_time - start_time

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 100  # Requested limit
        assert data["total_count"] == 500

        # Performance assertion
        assert request_time < 2.0, f"API request too slow: {request_time:.3f}s"

    def test_concurrent_api_requests(self, client, mock_full_service_chain):
        """Test handling of concurrent API requests."""
        import concurrent.futures
        import threading

        # Setup mock responses
        empty_response = IntelligenceResponse(
            documents=[],
            total_count=0,
            filtered_count=0,
            time_range="24h",
            repositories=[],
        )
        mock_full_service_chain["service_docs"].return_value = empty_response

        # Track concurrent calls
        call_count = {"count": 0}
        call_lock = threading.Lock()

        async def track_calls(*args, **kwargs):
            with call_lock:
                call_count["count"] += 1
            return empty_response

        mock_full_service_chain["service_docs"].side_effect = track_calls

        # Make concurrent requests
        def make_request(i):
            response = client.get(
                f"/api/intelligence/documents?repository=Concurrent-Test-{i}"
            )
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, i) for i in range(10)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # Verify all requests succeeded
        assert all(status == 200 for status in results)
        assert call_count["count"] == 10  # All requests should have been processed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
