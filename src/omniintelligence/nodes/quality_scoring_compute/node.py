"""Quality Scoring Compute - Pure compute node for quality scoring."""

from __future__ import annotations

import time

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.quality_scoring_compute.handlers import (
    create_error_dimensions,
    score_code_quality,
)
from omniintelligence.nodes.quality_scoring_compute.handlers.exceptions import (
    QualityScoringComputeError,
    QualityScoringValidationError,
)
from omniintelligence.nodes.quality_scoring_compute.models import (
    ModelQualityScoringInput,
    ModelQualityScoringMetadata,
    ModelQualityScoringOutput,
)


class NodeQualityScoringCompute(NodeCompute):
    """Pure compute node for scoring code quality.

    This node analyzes source code across multiple quality dimensions:
        - complexity: Cyclomatic complexity approximation (inverted - lower is better)
        - maintainability: Code structure quality (function length, naming conventions)
        - documentation: Docstring and comment coverage
        - temporal_relevance: Code freshness indicators (TODO/FIXME, deprecated markers)
        - patterns: ONEX pattern adherence (frozen models, TypedDict, Protocol, etc.)
        - architectural: Module organization and structure

    The node follows the ONEX pure shell pattern, delegating computation
    to side-effect-free handler functions.
    """

    async def compute(
        self, input_data: ModelQualityScoringInput
    ) -> ModelQualityScoringOutput:
        """Score code quality using pure handler function.

        Follows ONEX pure shell pattern - delegates to handler for computation.

        Args:
            input_data: Typed input model containing source code and scoring configuration.

        Returns:
            Typed ModelQualityScoringOutput with quality score, dimensions,
            ONEX compliance status, and recommendations.
        """
        start_time = time.perf_counter()

        try:
            # Prepare weights - use input weights or defaults
            weights = None
            if input_data.dimension_weights is not None:
                weights = {
                    "complexity": input_data.dimension_weights.complexity,
                    "maintainability": input_data.dimension_weights.maintainability,
                    "documentation": input_data.dimension_weights.documentation,
                    "temporal_relevance": input_data.dimension_weights.temporal_relevance,
                    "patterns": input_data.dimension_weights.patterns,
                    "architectural": input_data.dimension_weights.architectural,
                }

            # Call pure handler function
            result = score_code_quality(
                content=input_data.content,
                language=input_data.language,
                weights=weights,
                onex_threshold=input_data.onex_compliance_threshold,
            )

            processing_time = (time.perf_counter() - start_time) * 1000

            # Check against minimum quality threshold
            meets_threshold = result["quality_score"] >= input_data.min_quality_threshold

            return ModelQualityScoringOutput(
                success=result["success"] and meets_threshold,
                quality_score=result["quality_score"],
                dimensions=result["dimensions"],
                onex_compliant=result["onex_compliant"],
                recommendations=result["recommendations"],
                metadata=ModelQualityScoringMetadata(
                    status="completed" if meets_threshold else "below_threshold",
                    message=(
                        None
                        if meets_threshold
                        else f"Quality score {result['quality_score']:.2f} below threshold {input_data.min_quality_threshold}"
                    ),
                    source_language=result["source_language"],
                    analysis_version=result["analysis_version"],
                    processing_time_ms=processing_time,
                ),
            )

        except QualityScoringValidationError as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            return ModelQualityScoringOutput(
                success=False,
                quality_score=0.0,
                dimensions=create_error_dimensions(),
                onex_compliant=False,
                recommendations=[],
                metadata=ModelQualityScoringMetadata(
                    status="validation_error",
                    message=str(e),
                    processing_time_ms=processing_time,
                ),
            )

        except QualityScoringComputeError as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            return ModelQualityScoringOutput(
                success=False,
                quality_score=0.0,
                dimensions=create_error_dimensions(),
                onex_compliant=False,
                recommendations=[],
                metadata=ModelQualityScoringMetadata(
                    status="compute_error",
                    message=str(e),
                    processing_time_ms=processing_time,
                ),
            )


__all__ = ["NodeQualityScoringCompute"]
