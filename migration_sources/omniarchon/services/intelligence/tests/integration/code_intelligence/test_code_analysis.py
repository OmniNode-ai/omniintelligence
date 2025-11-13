"""
Integration tests for Code Intelligence API

Tests the /api/intelligence/code/analysis endpoint with realistic database scenarios.
"""

import pytest
from app import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create FastAPI test client"""
    return TestClient(app)


class TestCodeAnalysisEndpoint:
    """Tests for GET /api/intelligence/code/analysis endpoint"""

    def test_get_code_analysis_success(self, client):
        """Test successful code analysis retrieval"""
        response = client.get("/api/intelligence/code/analysis")

        # Verify response status
        assert response.status_code == 200

        # Verify response structure
        data = response.json()
        assert "files_analyzed" in data
        assert "avg_complexity" in data
        assert "code_smells" in data
        assert "security_issues" in data

        # Verify data types
        assert isinstance(data["files_analyzed"], int)
        assert isinstance(data["avg_complexity"], (int, float))
        assert isinstance(data["code_smells"], int)
        assert isinstance(data["security_issues"], int)

        # Verify data ranges (non-negative values)
        assert data["files_analyzed"] >= 0
        assert data["avg_complexity"] >= 0.0
        assert data["code_smells"] >= 0
        assert data["security_issues"] >= 0

    def test_get_code_analysis_response_model(self, client):
        """Test that response matches Pydantic model"""
        response = client.get("/api/intelligence/code/analysis")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        required_fields = [
            "files_analyzed",
            "avg_complexity",
            "code_smells",
            "security_issues",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_get_code_analysis_idempotency(self, client):
        """Test that multiple requests return consistent results"""
        # Make multiple requests
        response1 = client.get("/api/intelligence/code/analysis")
        response2 = client.get("/api/intelligence/code/analysis")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Results should be consistent (assuming database is static during test)
        data1 = response1.json()
        data2 = response2.json()

        assert data1["files_analyzed"] == data2["files_analyzed"]
        assert data1["avg_complexity"] == data2["avg_complexity"]
        assert data1["code_smells"] == data2["code_smells"]
        assert data1["security_issues"] == data2["security_issues"]

    def test_get_code_analysis_performance(self, client):
        """Test that endpoint responds within acceptable time"""
        import time

        start = time.time()
        response = client.get("/api/intelligence/code/analysis")
        duration = time.time() - start

        assert response.status_code == 200
        # Should respond within 5 seconds (allowing for database query)
        assert duration < 5.0, f"Request took {duration:.2f}s, expected < 5.0s"

    def test_get_code_analysis_content_type(self, client):
        """Test that response has correct content type"""
        response = client.get("/api/intelligence/code/analysis")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]


class TestCodeAnalysisMetrics:
    """Tests for specific code analysis metrics"""

    def test_files_analyzed_metric(self, client):
        """Test files_analyzed metric is computed correctly"""
        response = client.get("/api/intelligence/code/analysis")
        data = response.json()

        files_analyzed = data["files_analyzed"]

        # Should be non-negative integer
        assert isinstance(files_analyzed, int)
        assert files_analyzed >= 0

    def test_avg_complexity_metric(self, client):
        """Test avg_complexity metric is computed correctly"""
        response = client.get("/api/intelligence/code/analysis")
        data = response.json()

        avg_complexity = data["avg_complexity"]

        # Should be non-negative number
        assert isinstance(avg_complexity, (int, float))
        assert avg_complexity >= 0.0

        # Complexity typically ranges 1-50 for real code
        # Allow wider range for test data
        assert avg_complexity < 1000

    def test_code_smells_metric(self, client):
        """Test code_smells metric is computed correctly"""
        response = client.get("/api/intelligence/code/analysis")
        data = response.json()

        code_smells = data["code_smells"]

        # Should be non-negative integer
        assert isinstance(code_smells, int)
        assert code_smells >= 0

        # Code smells should not exceed total files
        files_analyzed = data["files_analyzed"]
        if files_analyzed > 0:
            assert code_smells <= files_analyzed

    def test_security_issues_metric(self, client):
        """Test security_issues metric is computed correctly"""
        response = client.get("/api/intelligence/code/analysis")
        data = response.json()

        security_issues = data["security_issues"]

        # Should be non-negative integer
        assert isinstance(security_issues, int)
        assert security_issues >= 0

        # Security issues should not exceed total files
        files_analyzed = data["files_analyzed"]
        if files_analyzed > 0:
            assert security_issues <= files_analyzed
