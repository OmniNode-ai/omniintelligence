"""
Unit tests for ONEX Quality Scorer

Tests quality scoring, ONEX compliance, and architectural era detection.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from archon_services.quality.onex_quality_scorer import ONEXQualityScorer

# Add src directory to path for imports


class TestONEXQualityScorer:
    """Test suite for ONEX Quality Scorer."""

    @pytest.fixture
    def scorer(self):
        """Create quality scorer instance."""
        return ONEXQualityScorer()

    def test_modern_onex_code_high_score(self, scorer):
        """Test that modern ONEX code gets high quality score."""
        modern_code = """
from omnibase.protocols import ProtocolToolBase
from omnibase.logging import emit_log_event

class ModelUserService(BaseModel):
    user_id: str
    email: str

class NodeUserEffect(NodeBase):
    def __init__(self, registry: BaseOnexRegistry):
        super().__init__(registry)
        self.container: ModelONEXContainer = registry.get_container()

    @standard_error_handling
    async def process(self):
        try:
            emit_log_event("Processing user effect")
            result = await self.execute()
        except OnexError as e:
            raise CoreErrorCode.EXECUTION_FAILED
        """

        result = scorer.analyze_content(modern_code)

        assert result["quality_score"] > 0.7, "Modern ONEX code should score > 0.7"
        assert result["onex_compliance_score"] > 0.8, "Should have high ONEX compliance"
        assert result["architectural_era"] == "modern_onex"
        assert len(result["legacy_indicators"]) == 0, "Should have no legacy indicators"

    def test_legacy_code_low_score(self, scorer):
        """Test that legacy code gets low quality score."""
        legacy_code = """
from typing import Any

class myService:  # Non-CamelCase
    def __init__(self):
        self.db = Database()  # Direct instantiation

    def get_user(self, user_id: Any):  # Any type
        import os  # Direct OS import
        data = os.getenv("USER_DATA")
        return data
        """

        result = scorer.analyze_content(legacy_code)

        assert result["quality_score"] < 0.5, "Legacy code should score < 0.5"
        assert result["onex_compliance_score"] < 0.3, "Should have low ONEX compliance"
        assert len(result["legacy_indicators"]) > 0, "Should detect legacy indicators"

    def test_critical_pattern_auto_reject(self, scorer):
        """Test that critical patterns result in zero score."""
        critical_code = """
from typing import Any

def process_data(input: Any) -> Any:  # Any types (forbidden)
    return input
        """

        result = scorer.analyze_content(critical_code)

        assert (
            result["onex_compliance_score"] == 0.0
        ), "Critical patterns should result in 0.0"
        assert any(
            "forbidden" in indicator.lower()
            for indicator in result["legacy_indicators"]
        )

    def test_temporal_relevance_recent_code(self, scorer):
        """Test temporal relevance scoring for recent code."""
        # Code modified 15 days ago (recent)
        recent_date = datetime.now(timezone.utc) - timedelta(days=15)

        result = scorer.analyze_content(
            "class ModernService: pass", file_last_modified=recent_date
        )

        assert result["relevance_score"] == 1.0, "Recent code should have 1.0 relevance"

    def test_temporal_relevance_old_code(self, scorer):
        """Test temporal relevance scoring for old code."""
        # Code modified 400 days ago (old)
        old_date = datetime.now(timezone.utc) - timedelta(days=400)

        result = scorer.analyze_content(
            "class OldService: pass", file_last_modified=old_date
        )

        assert result["relevance_score"] == 0.3, "Old code should have 0.3 relevance"

    def test_architectural_era_detection(self, scorer):
        """Test architectural era detection."""
        # Pre-NodeBase era code
        pre_nodebase = """
class UserTool:
    def main():
        parser = argparse.ArgumentParser()
        """

        result = scorer.analyze_content(pre_nodebase)
        assert result["architectural_era"] == "pre_nodebase"

        # Early NodeBase era
        early_nodebase = """
class UserService(NodeBase):
    def __init__(self):
        super().__init__()
        """

        result = scorer.analyze_content(early_nodebase)
        assert result["architectural_era"] == "early_nodebase"

        # Contract-driven era
        contract_driven = """
contract_path = Path("contract.yaml")
config = from_contract(CONTRACT_FILENAME)
        """

        result = scorer.analyze_content(contract_driven)
        assert result["architectural_era"] == "contract_driven"

    def test_legacy_indicator_detection(self, scorer):
        """Test detection of specific legacy indicators."""
        code_with_indicators = """
from services import UserService  # Manual import

class myservice:  # Non-CamelCase
    pass

import os  # Direct OS import
        """

        result = scorer.analyze_content(code_with_indicators)

        indicators = result["legacy_indicators"]
        assert len(indicators) > 0

        # Check for specific indicators
        assert any("CamelCase" in ind for ind in indicators)
        assert any("OS import" in ind for ind in indicators)

    def test_empty_code(self, scorer):
        """Test handling of empty code."""
        result = scorer.analyze_content("")

        assert 0.0 <= result["quality_score"] <= 1.0
        assert 0.0 <= result["onex_compliance_score"] <= 1.0
        assert result["architectural_era"] == "modern_onex"  # Default for empty

    def test_git_commit_date_priority(self, scorer):
        """Test that git_commit_date takes priority over file_last_modified."""
        old_file_date = datetime.now(timezone.utc) - timedelta(days=400)
        recent_commit_date = datetime.now(timezone.utc) - timedelta(days=15)

        result = scorer.analyze_content(
            "class Test: pass",
            file_last_modified=old_file_date,
            git_commit_date=recent_commit_date,
        )

        # Should use recent commit date, not old file date
        assert result["relevance_score"] == 1.0


@pytest.mark.asyncio
class TestONEXQualityScorerIntegration:
    """Integration tests for quality scorer."""

    @pytest.fixture
    def scorer(self):
        """Create quality scorer instance."""
        return ONEXQualityScorer()

    async def test_batch_analysis(self, scorer):
        """Test analyzing multiple code samples."""
        code_samples = [
            "class ModelUser(BaseModel): pass",  # Good
            "class myservice: pass",  # Bad
            "class Service(NodeBase): pass",  # Good
        ]

        results = [scorer.analyze_content(code) for code in code_samples]

        assert len(results) == 3
        assert all("quality_score" in r for r in results)
        assert all("onex_compliance_score" in r for r in results)

    async def test_performance_benchmark(self, scorer):
        """Test performance of quality scoring."""
        import time

        large_code = "class ModernService: pass\n" * 100

        start = time.time()
        result = scorer.analyze_content(large_code)
        elapsed = time.time() - start

        assert elapsed < 0.2, "Analysis should complete in < 200ms"
        assert result is not None
