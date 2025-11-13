"""
Unit tests for ComprehensiveONEXScorer

Tests quality scoring with omnibase_core integration and fallback behavior.
"""

from datetime import datetime, timedelta, timezone

import pytest
from archon_services.quality.comprehensive_onex_scorer import ComprehensiveONEXScorer


class TestComprehensiveONEXScorer:
    """Test suite for Comprehensive ONEX Scorer."""

    @pytest.fixture
    def scorer(self):
        """Create scorer instance."""
        return ComprehensiveONEXScorer()

    def test_fallback_checker_marks_validation_skipped(self, scorer):
        """Test that FallbackChecker properly marks validation as skipped when omnibase_core unavailable."""
        test_code = """
class ModelUser:
    name: str
    email: str
"""
        result = scorer.analyze_content(test_code)

        # Verify validation_skipped flag is set
        assert result.get(
            "validation_skipped", False
        ), "validation_skipped should be True"

        # Verify compliance score is penalized
        assert (
            result["onex_compliance_score"] == 0.3
        ), "Compliance score should be 0.3 when validation skipped"

        # Verify marker in violations
        violations = result["omnibase_violations"]
        assert any(
            "ONEX_VALIDATION_SKIPPED" in v for v in violations
        ), "Should have validation skipped marker in violations"

        # Verify warning in legacy indicators
        indicators = result["legacy_indicators"]
        assert any(
            "ONEX Validator:" in ind and "ONEX_VALIDATION_SKIPPED" in ind
            for ind in indicators
        ), "Should have validation skipped warning in legacy indicators"

    def test_fallback_checker_impacts_quality_score(self, scorer):
        """Test that validation skipped status impacts overall quality score."""
        test_code = """
class ModelUser:
    name: str
    email: str
"""
        result = scorer.analyze_content(test_code)

        # Quality score should be low due to unreliable validation
        # compliance (0.3) * 0.6 + relevance (0.5) * 0.3 + era_modifier
        # = 0.18 + 0.15 + era_modifier
        # With modern_onex era: + 0.1 * 0.1 = 0.01
        # Total: ~0.34
        assert result["quality_score"] < 0.4, (
            f"Quality score should be low (<0.4) when validation skipped, "
            f"got {result['quality_score']}"
        )

    def test_critical_patterns_still_detected(self, scorer):
        """Test that critical patterns are still detected even with fallback checker."""
        critical_code = """
from typing import Any

def process_data(input: Any) -> Any:  # Any types (forbidden)
    return input
"""
        result = scorer.analyze_content(critical_code)

        # Critical patterns should still fail (pattern matching happens regardless)
        assert (
            result["onex_compliance_score"] == 0.0
        ), "Critical patterns should still result in 0.0 score"

        # Should still have validation skipped marker
        assert result.get(
            "validation_skipped", False
        ), "validation_skipped should be True"

    def test_modern_patterns_still_detected(self, scorer):
        """Test that modern ONEX patterns are still detected with fallback checker."""
        modern_code = """
from omnibase.protocols import ProtocolToolBase
from omnibase.logging import emit_log_event

class ModelUserService:
    def __init__(self, registry: BaseOnexRegistry):
        self.container: ModelONEXContainer = registry.get_container()

    @standard_error_handling
    async def process(self):
        emit_log_event("Processing")
"""
        result = scorer.analyze_content(modern_code)

        # Validation skipped, but modern patterns still detected
        assert result.get(
            "validation_skipped", False
        ), "validation_skipped should be True"

        # Should still have modern era detection
        assert result["architectural_era"] == "modern_onex"

        # Compliance score should still be low (0.3) due to validation skipped
        # even though modern patterns are present
        assert (
            result["onex_compliance_score"] == 0.3
        ), "Should have 0.3 score when validation skipped regardless of patterns"

    def test_temporal_relevance_unaffected(self, scorer):
        """Test that temporal relevance calculation is unaffected by validation skip."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=15)

        result = scorer.analyze_content(
            "class ModernService: pass", file_last_modified=recent_date
        )

        # Temporal relevance should still work correctly
        assert result["relevance_score"] == 1.0, "Recent code should have 1.0 relevance"

        # But validation should still be marked as skipped
        assert result.get(
            "validation_skipped", False
        ), "validation_skipped should be True"

    def test_empty_code_with_fallback(self, scorer):
        """Test handling of empty code with fallback checker."""
        result = scorer.analyze_content("")

        # Should still mark validation as skipped
        assert result.get(
            "validation_skipped", False
        ), "validation_skipped should be True"

        # Scores should be in valid range
        assert 0.0 <= result["quality_score"] <= 1.0
        assert (
            result["onex_compliance_score"] == 0.3
        )  # Penalized for skipped validation


@pytest.mark.asyncio
class TestComprehensiveONEXScorerIntegration:
    """Integration tests for comprehensive scorer."""

    @pytest.fixture
    def scorer(self):
        """Create scorer instance."""
        return ComprehensiveONEXScorer()

    async def test_batch_analysis_with_fallback(self, scorer):
        """Test analyzing multiple code samples with fallback checker."""
        code_samples = [
            "class ModelUser: pass",  # Modern
            "class myservice: pass",  # Legacy
            "from typing import Any\ndef f(x: Any): pass",  # Critical
        ]

        results = [scorer.analyze_content(code) for code in code_samples]

        # All should have validation skipped
        assert all(r.get("validation_skipped", False) for r in results)

        # All should have compliance score of 0.3 or 0.0 (critical)
        assert results[0]["onex_compliance_score"] == 0.3  # Modern but skipped
        assert results[1]["onex_compliance_score"] == 0.3  # Legacy but skipped
        assert results[2]["onex_compliance_score"] == 0.0  # Critical pattern

    async def test_validation_skipped_message_clarity(self, scorer):
        """Test that validation skipped messages are clear and informative."""
        result = scorer.analyze_content("class Test: pass")

        # Check message clarity
        violations = result["omnibase_violations"]
        skipped_violations = [v for v in violations if "ONEX_VALIDATION_SKIPPED" in v]

        assert len(skipped_violations) > 0, "Should have skipped validation markers"

        # Each marker should be clear about the issue
        for violation in skipped_violations:
            assert "omnibase_core unavailable" in violation
            assert "quality scores are unreliable" in violation
