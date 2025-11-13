"""
Unit tests for Code Intelligence Service

Tests the service logic independently of the FastAPI app.
"""

import pytest
from api.code_intelligence.service import CodeIntelligenceService


class TestCodeIntelligenceService:
    """Tests for CodeIntelligenceService"""

    def test_service_initialization(self):
        """Test service can be initialized"""
        service = CodeIntelligenceService()
        assert service is not None

    def test_get_fallback_metrics(self):
        """Test fallback metrics structure"""
        service = CodeIntelligenceService()
        metrics = service._get_fallback_metrics()

        # Verify structure
        assert "files_analyzed" in metrics
        assert "avg_complexity" in metrics
        assert "code_smells" in metrics
        assert "security_issues" in metrics

        # Verify data types
        assert isinstance(metrics["files_analyzed"], int)
        assert isinstance(metrics["avg_complexity"], (int, float))
        assert isinstance(metrics["code_smells"], int)
        assert isinstance(metrics["security_issues"], int)

        # Verify all values are zero (fallback)
        assert metrics["files_analyzed"] == 0
        assert metrics["avg_complexity"] == 0.0
        assert metrics["code_smells"] == 0
        assert metrics["security_issues"] == 0

    @pytest.mark.asyncio
    async def test_get_code_analysis_returns_dict(self):
        """Test that get_code_analysis returns a dictionary"""
        service = CodeIntelligenceService()
        result = await service.get_code_analysis()

        assert isinstance(result, dict)
        assert "files_analyzed" in result
        assert "avg_complexity" in result
        assert "code_smells" in result
        assert "security_issues" in result

    @pytest.mark.asyncio
    async def test_get_code_analysis_values_are_valid(self):
        """Test that returned values are valid"""
        service = CodeIntelligenceService()
        result = await service.get_code_analysis()

        # All values should be non-negative
        assert result["files_analyzed"] >= 0
        assert result["avg_complexity"] >= 0.0
        assert result["code_smells"] >= 0
        assert result["security_issues"] >= 0

        # Code smells and security issues should not exceed files analyzed
        if result["files_analyzed"] > 0:
            assert result["code_smells"] <= result["files_analyzed"]
            assert result["security_issues"] <= result["files_analyzed"]
