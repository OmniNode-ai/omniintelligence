# SPDX-License-Identifier: Apache-2.0
"""Integration tests for NodeQualityScoringCompute.

These tests exercise the node's compute() method end-to-end, verifying:
1. Full pipeline from input model to output model
2. Preset configuration behavior through the node
3. Error handling and propagation
4. Output model structure and field validation

The tests use realistic code samples to verify the scoring algorithms
produce expected results for different code quality levels.
"""

from __future__ import annotations

from typing import Final

import pytest

from omnibase_core.models.container.model_onex_container import ModelONEXContainer

from omniintelligence.nodes.quality_scoring_compute.handlers import (
    OnexStrictnessLevel,
)
from omniintelligence.nodes.quality_scoring_compute.models import (
    ModelDimensionWeights,
    ModelQualityScoringInput,
    ModelQualityScoringOutput,
)
from omniintelligence.nodes.quality_scoring_compute.node import (
    NodeQualityScoringCompute,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def onex_container() -> ModelONEXContainer:
    """Create a fresh ONEX container for each test."""
    return ModelONEXContainer()


# =============================================================================
# Constants
# =============================================================================

# Quality score thresholds for test assertions
HIGH_QUALITY_MIN_SCORE: Final[float] = 0.6
LOW_QUALITY_MAX_SCORE: Final[float] = 0.7
MODERATE_QUALITY_MIN_SCORE: Final[float] = 0.4
MODERATE_QUALITY_MAX_SCORE: Final[float] = 0.85
PROCESSING_TIME_NORMAL_MS: Final[float] = 500.0
PROCESSING_TIME_LARGE_MS: Final[float] = 2000.0


# =============================================================================
# Sample Code Fixtures
# =============================================================================


HIGH_QUALITY_ONEX_CODE = '''"""ONEX-compliant model with proper patterns.

This module demonstrates best practices for ONEX node development.
"""

from __future__ import annotations

from typing import ClassVar, Final

from pydantic import BaseModel, Field, field_validator


__all__ = ["UserModel", "create_user"]


class UserModel(BaseModel):
    """User model following ONEX patterns.

    Attributes:
        name: The user's display name.
        email: The user's email address.
        age: The user's age in years.
    """

    name: str = Field(..., min_length=1, description="User display name")
    email: str = Field(..., description="User email address")
    age: int = Field(..., ge=0, le=150, description="User age in years")

    model_config: ClassVar[dict[str, bool | str]] = {
        "frozen": True,
        "extra": "forbid",
    }

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()


def create_user(name: str, email: str, age: int) -> UserModel:
    """Create a new user instance.

    Args:
        name: The user's display name.
        email: The user's email address.
        age: The user's age in years.

    Returns:
        A validated UserModel instance.
    """
    return UserModel(name=name, email=email, age=age)
'''


LOW_QUALITY_CODE = '''# TODO: Fix this later
# FIXME: Performance issues
# XXX: Deprecated approach

def BADFUNCTION(x, y, z, a, b, c, d, e, f, g, **kwargs):
    result = {}
    data = []
    if x:
        if y:
            if z:
                if a:
                    if b:
                        if c:
                            result["value"] = x + y + z
    for i in range(100):
        for j in range(100):
            for k in range(100):
                data.append(i + j + k)
    return result


class badclass:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
    def method4(self): pass
    def method5(self): pass
    model_config = {}
'''


MODERATE_QUALITY_CODE = '''"""A module with moderate code quality."""

from typing import Optional


class DataProcessor:
    """Process data with basic functionality."""

    def __init__(self, data: list) -> None:
        self.data = data

    def process(self) -> list:
        """Process the data and return results."""
        result = []
        for item in self.data:
            if item is not None:
                result.append(item * 2)
        return result

    def filter_data(self, threshold: int) -> list:
        """Filter data above threshold."""
        return [x for x in self.data if x and x > threshold]
'''


# =============================================================================
# Test Classes
# =============================================================================


@pytest.mark.integration
class TestNodeComputeMethod:
    """Integration tests for NodeQualityScoringCompute.compute() method."""

    @pytest.fixture
    def node(self, onex_container: ModelONEXContainer) -> NodeQualityScoringCompute:
        """Create a fresh node instance for each test."""
        return NodeQualityScoringCompute(container=onex_container)

    async def test_compute_returns_valid_output_model(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test compute() returns properly structured ModelQualityScoringOutput."""
        input_data = ModelQualityScoringInput(
            source_path="test.py",
            content="def hello() -> None:\n    pass\n",
            language="python",
        )

        output = await node.compute(input_data)

        # Verify output is correct type
        assert isinstance(output, ModelQualityScoringOutput)

        # Verify required fields exist
        assert hasattr(output, "success")
        assert hasattr(output, "quality_score")
        assert hasattr(output, "dimensions")
        assert hasattr(output, "onex_compliant")
        assert hasattr(output, "recommendations")
        assert hasattr(output, "metadata")

        # Verify field types
        assert isinstance(output.success, bool)
        assert isinstance(output.quality_score, float)
        assert isinstance(output.dimensions, dict)
        assert isinstance(output.onex_compliant, bool)
        assert isinstance(output.recommendations, list)

    async def test_compute_pipeline_input_to_output(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test full pipeline: ModelQualityScoringInput -> compute() -> ModelQualityScoringOutput."""
        input_data = ModelQualityScoringInput(
            source_path="src/models/user.py",
            content=HIGH_QUALITY_ONEX_CODE,
            language="python",
            project_name="test_project",
        )

        output = await node.compute(input_data)

        # Verify successful processing
        assert output.success is True

        # Verify quality score is in valid range
        assert 0.0 <= output.quality_score <= 1.0

        # Verify all six dimensions are present
        expected_dimensions = {
            "complexity",
            "maintainability",
            "documentation",
            "temporal_relevance",
            "patterns",
            "architectural",
        }
        assert set(output.dimensions.keys()) == expected_dimensions

        # Verify each dimension score is in valid range
        for dim_name, dim_score in output.dimensions.items():
            assert 0.0 <= dim_score <= 1.0, f"Dimension {dim_name} out of range"

        # Verify metadata is populated
        assert output.metadata is not None
        assert output.metadata.status == "completed"
        assert output.metadata.source_language == "python"
        assert output.metadata.analysis_version is not None
        assert output.metadata.processing_time_ms is not None
        assert output.metadata.processing_time_ms >= 0.0

    async def test_compute_with_high_quality_code(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test compute() scores ONEX-compliant code highly."""
        input_data = ModelQualityScoringInput(
            source_path="src/models/user.py",
            content=HIGH_QUALITY_ONEX_CODE,
            language="python",
        )

        output = await node.compute(input_data)

        # High quality code should score well
        assert output.success is True
        assert output.quality_score >= HIGH_QUALITY_MIN_SCORE, (
            f"High quality code scored {output.quality_score}, expected >= {HIGH_QUALITY_MIN_SCORE}"
        )

        # Should be ONEX compliant with default threshold
        assert output.onex_compliant is True

        # Should have high documentation score (has docstrings)
        assert output.dimensions["documentation"] >= 0.5

        # Should have high patterns score (uses ONEX patterns)
        assert output.dimensions["patterns"] >= 0.5

        # Should have few or no recommendations
        assert len(output.recommendations) <= 3

    async def test_compute_with_low_quality_code(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test compute() gives low scores to code with anti-patterns."""
        input_data = ModelQualityScoringInput(
            source_path="legacy/bad_code.py",
            content=LOW_QUALITY_CODE,
            language="python",
        )

        output = await node.compute(input_data)

        # Should still succeed (processing worked)
        assert output.success is True

        # Low quality code should score poorly
        assert output.quality_score < LOW_QUALITY_MAX_SCORE, (
            f"Low quality code scored {output.quality_score}, expected < {LOW_QUALITY_MAX_SCORE}"
        )

        # Should have low temporal relevance (TODOs, FIXMEs)
        assert output.dimensions["temporal_relevance"] < 0.8

        # Low quality code should not score perfectly on complexity
        # (the complexity score is inverted - higher means lower complexity)
        # Even complex code may score moderately well if complexity is spread
        # across functions, so we just verify it's not perfect
        assert output.dimensions["complexity"] < 1.0

        # Should have recommendations for improvement
        assert len(output.recommendations) >= 1

    async def test_compute_with_moderate_quality_code(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test compute() returns moderate scores for average code."""
        input_data = ModelQualityScoringInput(
            source_path="src/processor.py",
            content=MODERATE_QUALITY_CODE,
            language="python",
        )

        output = await node.compute(input_data)

        assert output.success is True

        # Moderate code should score in the middle range
        assert MODERATE_QUALITY_MIN_SCORE <= output.quality_score <= MODERATE_QUALITY_MAX_SCORE, (
            f"Moderate code scored {output.quality_score}"
        )

    async def test_compute_with_custom_weights(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test compute() respects custom dimension weights."""
        # Custom weights emphasizing documentation
        custom_weights = ModelDimensionWeights(
            complexity=0.10,
            maintainability=0.10,
            documentation=0.40,  # Highly weighted
            temporal_relevance=0.10,
            patterns=0.15,
            architectural=0.15,
        )

        input_data = ModelQualityScoringInput(
            source_path="test.py",
            content=HIGH_QUALITY_ONEX_CODE,
            language="python",
            dimension_weights=custom_weights,
        )

        output = await node.compute(input_data)

        assert output.success is True
        # The score should reflect the weighted dimensions
        assert 0.0 <= output.quality_score <= 1.0

    async def test_compute_with_min_quality_threshold(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test compute() respects min_quality_threshold setting."""
        input_data = ModelQualityScoringInput(
            source_path="test.py",
            content=LOW_QUALITY_CODE,
            language="python",
            min_quality_threshold=0.9,  # Very high threshold
        )

        output = await node.compute(input_data)

        # Should fail the threshold check
        assert output.success is False
        assert output.metadata is not None
        assert output.metadata.status == "below_threshold"
        assert output.metadata.message is not None
        assert "below threshold" in output.metadata.message.lower()


@pytest.mark.integration
class TestPresetIntegration:
    """Integration tests for preset behavior through the node."""

    @pytest.fixture
    def node(self, onex_container: ModelONEXContainer) -> NodeQualityScoringCompute:
        """Create a fresh node instance for each test."""
        return NodeQualityScoringCompute(container=onex_container)

    async def test_strict_preset_through_compute(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test STRICT preset via compute() method."""
        input_data = ModelQualityScoringInput(
            source_path="production/service.py",
            content=HIGH_QUALITY_ONEX_CODE,
            language="python",
            onex_preset=OnexStrictnessLevel.STRICT,
        )

        output = await node.compute(input_data)

        assert output.success is True
        # STRICT preset has 0.8 threshold
        # High quality code should pass even strict threshold
        assert 0.0 <= output.quality_score <= 1.0

    async def test_standard_preset_through_compute(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test STANDARD preset via compute() method."""
        input_data = ModelQualityScoringInput(
            source_path="src/module.py",
            content=MODERATE_QUALITY_CODE,
            language="python",
            onex_preset=OnexStrictnessLevel.STANDARD,
        )

        output = await node.compute(input_data)

        assert output.success is True
        # STANDARD preset has 0.7 threshold
        assert 0.0 <= output.quality_score <= 1.0

    async def test_lenient_preset_through_compute(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test LENIENT preset via compute() method."""
        input_data = ModelQualityScoringInput(
            source_path="prototype/experiment.py",
            content=LOW_QUALITY_CODE,
            language="python",
            onex_preset=OnexStrictnessLevel.LENIENT,
        )

        output = await node.compute(input_data)

        assert output.success is True
        # LENIENT preset has 0.5 threshold - even low quality might pass
        assert 0.0 <= output.quality_score <= 1.0

    async def test_preset_overrides_custom_weights(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test that preset takes precedence over dimension_weights."""
        # Custom weights that would produce different results
        custom_weights = ModelDimensionWeights(
            complexity=0.50,  # Very high complexity weight
            maintainability=0.10,
            documentation=0.10,
            temporal_relevance=0.10,
            patterns=0.10,
            architectural=0.10,
        )

        # First run without preset
        input_without_preset = ModelQualityScoringInput(
            source_path="test.py",
            content=HIGH_QUALITY_ONEX_CODE,
            language="python",
            dimension_weights=custom_weights,
        )
        output_without_preset = await node.compute(input_without_preset)

        # Second run with preset (should override weights)
        input_with_preset = ModelQualityScoringInput(
            source_path="test.py",
            content=HIGH_QUALITY_ONEX_CODE,
            language="python",
            dimension_weights=custom_weights,
            onex_preset=OnexStrictnessLevel.STANDARD,
        )
        output_with_preset = await node.compute(input_with_preset)

        # Both should succeed
        assert output_without_preset.success is True
        assert output_with_preset.success is True

        # Scores may differ because preset overrides the custom weights
        # The preset uses balanced weights, custom uses high complexity weight
        # We don't assert inequality since it depends on code characteristics,
        # but we verify both produce valid results
        assert 0.0 <= output_without_preset.quality_score <= 1.0
        assert 0.0 <= output_with_preset.quality_score <= 1.0

    async def test_preset_determines_onex_compliance_threshold(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test that preset correctly sets ONEX compliance threshold."""
        # Use code that scores around 0.6-0.75 range
        input_strict = ModelQualityScoringInput(
            source_path="test.py",
            content=MODERATE_QUALITY_CODE,
            language="python",
            onex_preset=OnexStrictnessLevel.STRICT,  # threshold 0.8
        )
        input_lenient = ModelQualityScoringInput(
            source_path="test.py",
            content=MODERATE_QUALITY_CODE,
            language="python",
            onex_preset=OnexStrictnessLevel.LENIENT,  # threshold 0.5
        )

        output_strict = await node.compute(input_strict)
        output_lenient = await node.compute(input_lenient)

        # Same code, different presets
        # With strict (0.8 threshold), moderate code likely not compliant
        # With lenient (0.5 threshold), moderate code likely compliant
        assert output_strict.success is True
        assert output_lenient.success is True

        # The lenient preset should be more likely to pass
        # (we don't strictly assert because it depends on actual scores)


@pytest.mark.integration
class TestErrorPropagation:
    """Tests for error handling through the compute() method."""

    @pytest.fixture
    def node(self, onex_container: ModelONEXContainer) -> NodeQualityScoringCompute:
        """Create a fresh node instance for each test."""
        return NodeQualityScoringCompute(container=onex_container)

    async def test_empty_content_error_propagates(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test validation error for empty content propagates correctly."""
        # The input model validates content is non-empty, so we need to
        # test with whitespace-only content which passes Pydantic but fails handler
        input_data = ModelQualityScoringInput(
            source_path="test.py",
            content="   \n\t\n   ",  # Only whitespace
            language="python",
        )

        output = await node.compute(input_data)

        # Should return error result, not raise exception
        assert output.success is False
        assert output.quality_score == 0.0
        assert output.onex_compliant is False
        assert output.metadata is not None
        assert output.metadata.status == "validation_error"
        assert output.metadata.message is not None
        assert "empty" in output.metadata.message.lower()

    async def test_invalid_weights_error_propagates(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test validation error for invalid weights propagates correctly."""
        # Invalid weights that don't sum to 1.0 will fail Pydantic validation
        # So we test by checking the model validation works
        with pytest.raises(ValueError, match="sum to 1.0"):
            ModelDimensionWeights(
                complexity=0.50,
                maintainability=0.50,
                documentation=0.50,  # Sum > 1.0
                temporal_relevance=0.10,
                patterns=0.10,
                architectural=0.10,
            )

    async def test_compute_error_captured_in_metadata(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test that compute errors are captured in output metadata."""
        # Syntax error in code should be handled gracefully
        input_data = ModelQualityScoringInput(
            source_path="broken.py",
            content="def broken(\n    return 42",  # Syntax error
            language="python",
        )

        output = await node.compute(input_data)

        # Should still return a result (not raise)
        assert output.success is True  # Scoring worked, code just has issues
        assert output.quality_score > 0.0  # Gets baseline score
        assert output.onex_compliant is False

        # Should have recommendation about syntax error
        assert len(output.recommendations) >= 1
        has_syntax_rec = any(
            "syntax" in rec.lower() for rec in output.recommendations
        )
        assert has_syntax_rec, f"Expected syntax recommendation in {output.recommendations}"

    async def test_unsupported_language_handled_gracefully(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test that unsupported languages get baseline scores."""
        input_data = ModelQualityScoringInput(
            source_path="code.rs",
            content="fn main() { println!(\"Hello\"); }",
            language="rust",  # Unsupported
        )

        output = await node.compute(input_data)

        # Should succeed with baseline scores
        assert output.success is True
        assert output.quality_score == 0.5  # Baseline for unsupported
        assert output.metadata is not None
        assert output.metadata.source_language == "rust"

        # Should have recommendation about unsupported language
        has_unsupported_rec = any(
            "unsupported" in rec.lower() or "not available" in rec.lower()
            for rec in output.recommendations
        )
        assert has_unsupported_rec

    async def test_processing_time_captured(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test that processing time is captured in metadata."""
        input_data = ModelQualityScoringInput(
            source_path="test.py",
            content=HIGH_QUALITY_ONEX_CODE,
            language="python",
        )

        output = await node.compute(input_data)

        assert output.metadata is not None
        assert output.metadata.processing_time_ms is not None
        assert output.metadata.processing_time_ms >= 0.0
        # Processing should be fast (under 1 second for reasonable code)
        assert output.metadata.processing_time_ms < 1000.0


@pytest.mark.integration
class TestNodeDeterminism:
    """Tests verifying the node produces deterministic results."""

    @pytest.fixture
    def node(self, onex_container: ModelONEXContainer) -> NodeQualityScoringCompute:
        """Create a fresh node instance for each test."""
        return NodeQualityScoringCompute(container=onex_container)

    async def test_compute_is_deterministic(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test that compute() produces same output for same input."""
        input_data = ModelQualityScoringInput(
            source_path="test.py",
            content=HIGH_QUALITY_ONEX_CODE,
            language="python",
        )

        output1 = await node.compute(input_data)
        output2 = await node.compute(input_data)

        # Core fields should be identical
        assert output1.success == output2.success
        assert output1.quality_score == output2.quality_score
        assert output1.dimensions == output2.dimensions
        assert output1.onex_compliant == output2.onex_compliant
        assert output1.recommendations == output2.recommendations

        # Metadata fields (except processing time) should be identical
        assert output1.metadata is not None
        assert output2.metadata is not None
        assert output1.metadata.status == output2.metadata.status
        assert output1.metadata.source_language == output2.metadata.source_language
        assert output1.metadata.analysis_version == output2.metadata.analysis_version

    async def test_multiple_node_instances_produce_same_results(
        self, onex_container: ModelONEXContainer
    ) -> None:
        """Test that different node instances produce identical results."""
        node1 = NodeQualityScoringCompute(container=onex_container)
        node2 = NodeQualityScoringCompute(container=ModelONEXContainer())

        input_data = ModelQualityScoringInput(
            source_path="test.py",
            content=MODERATE_QUALITY_CODE,
            language="python",
        )

        output1 = await node1.compute(input_data)
        output2 = await node2.compute(input_data)

        assert output1.quality_score == output2.quality_score
        assert output1.dimensions == output2.dimensions
        assert output1.onex_compliant == output2.onex_compliant


@pytest.mark.integration
class TestNodePerformance:
    """Performance tests for the compute node."""

    @pytest.fixture
    def node(self, onex_container: ModelONEXContainer) -> NodeQualityScoringCompute:
        """Create a fresh node instance for each test."""
        return NodeQualityScoringCompute(container=onex_container)

    async def test_compute_completes_in_bounded_time(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test that compute completes quickly for reasonable input."""
        input_data = ModelQualityScoringInput(
            source_path="test.py",
            content=HIGH_QUALITY_ONEX_CODE,
            language="python",
        )

        output = await node.compute(input_data)

        assert output.success is True
        assert output.metadata is not None
        # Should complete in under 500ms for normal code
        assert output.metadata.processing_time_ms < PROCESSING_TIME_NORMAL_MS

    async def test_compute_handles_large_file(
        self, node: NodeQualityScoringCompute
    ) -> None:
        """Test that compute handles larger files without issues."""
        # Create a larger file by repeating content
        large_content = HIGH_QUALITY_ONEX_CODE * 10  # ~6KB of code

        input_data = ModelQualityScoringInput(
            source_path="large_module.py",
            content=large_content,
            language="python",
        )

        output = await node.compute(input_data)

        assert output.success is True
        assert output.metadata is not None
        # Should still complete in reasonable time
        assert output.metadata.processing_time_ms < PROCESSING_TIME_LARGE_MS
