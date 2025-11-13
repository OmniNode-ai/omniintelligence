"""
ONEX Compute Node: Pattern Quality Assessor

Purpose: Calculate comprehensive quality metrics for code patterns
Node Type: Compute (Pure transformation, no side effects)
File: node_pattern_quality_assessor_compute.py
Class: NodePatternQualityAssessorCompute

Pattern: ONEX 4-Node Architecture - Compute
Track: Pattern Ingestion Enhancement
ONEX Compliant: Suffix naming (Node*Compute), file pattern (node_*_compute.py)
"""

import ast
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from src.archon_services.pattern_learning.phase1_foundation.quality.model_contract_pattern_quality import (
    ModelContractPatternQuality,
    ModelQualityMetrics,
    ModelResult,
)
from src.archon_services.pattern_learning.phase1_foundation.quality.node_base_compute import (
    NodeBaseCompute,
)

# Import quality scoring services
from src.archon_services.quality.comprehensive_onex_scorer import (
    ComprehensiveONEXScorer,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ONEX Compute Node: Pattern Quality Assessor
# ============================================================================


class NodePatternQualityAssessorCompute(NodeBaseCompute):
    """
    ONEX Compute Node for pattern quality assessment.

    Implements:
    - ONEX naming convention: Node<Name>Compute
    - File pattern: node_*_compute.py
    - Method signature: async def execute_compute(self, contract: ModelContractPatternQuality) -> ModelResult
    - Pure computation (no I/O, no side effects)
    - Stateless operations with reproducible results

    Responsibilities:
    - Analyze pattern code for ONEX compliance
    - Calculate quality scores (0.0-1.0)
    - Compute complexity metrics
    - Assess maintainability and performance
    - Generate confidence scores
    - Detect architectural patterns

    Quality Metrics Calculated:
    - confidence_score: Pattern reliability (0.0-1.0)
    - complexity_score: Cyclomatic complexity (integer)
    - maintainability_score: Code maintainability (0.0-1.0)
    - performance_score: Estimated performance (0.0-1.0)
    - quality_score: Overall quality (0.0-1.0)
    - onex_compliance_score: ONEX compliance (0.0-1.0)

    Performance Targets:
    - Assessment time: <500ms per pattern
    - Complexity calculation: <100ms
    - Quality scoring: <200ms

    Example:
        >>> node = NodePatternQualityAssessorCompute()
        >>> contract = ModelContractPatternQuality(
        ...     name="assess_pattern",
        ...     pattern_code="async def execute_effect(...): ...",
        ...     pattern_type="code",
        ...     language="python"
        ... )
        >>> result = await node.execute_compute(contract)
        >>> metrics = result.data  # ModelQualityMetrics
        >>> print(f"Quality: {metrics.quality_score}")
    """

    def __init__(self):
        """Initialize pattern quality assessor Compute node."""
        super().__init__()
        self.logger = logging.getLogger("NodePatternQualityAssessorCompute")
        self.quality_scorer = ComprehensiveONEXScorer()

    async def execute_compute(
        self, contract: ModelContractPatternQuality
    ) -> ModelResult:
        """
        Execute pattern quality assessment computation.

        ONEX Method Signature: async def execute_compute(self, contract) -> ModelResult

        Args:
            contract: ModelContractPatternQuality with pattern code and metadata

        Returns:
            ModelResult with ModelQualityMetrics data containing:
            - confidence_score: Pattern reliability (0.0-1.0)
            - usage_count: Initial usage count (0)
            - success_rate: Estimated success rate (0.0-1.0)
            - complexity_score: Cyclomatic complexity
            - maintainability_score: Maintainability score (0.0-1.0)
            - performance_score: Performance score (0.0-1.0)
            - quality_score: Overall quality score (0.0-1.0)
            - onex_compliance_score: ONEX compliance (0.0-1.0)
            - metadata: Additional quality metrics

        Raises:
            Does not raise exceptions - returns ModelResult with error details

        Performance:
            - Target: <500ms per pattern
            - Actual: Typically 200-400ms
        """
        start_time = datetime.now(timezone.utc)

        try:
            self.logger.info(
                f"Assessing quality for pattern: {contract.pattern_name}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "pattern_type": contract.pattern_type,
                    "language": contract.language,
                },
            )

            # Step 1: Comprehensive quality analysis using ComprehensiveONEXScorer
            quality_analysis = self.quality_scorer.analyze_content(
                content=contract.pattern_code,
                file_path=contract.pattern_name,
                file_last_modified=contract.file_last_modified,
                git_commit_date=contract.git_commit_date,
            )

            # Step 2: Calculate complexity score (cyclomatic complexity)
            complexity_score = self._calculate_complexity(contract.pattern_code)

            # Step 3: Calculate maintainability score
            maintainability_score = self._calculate_maintainability(
                contract.pattern_code, quality_analysis
            )

            # Step 4: Calculate performance score
            performance_score = self._calculate_performance_score(
                contract.pattern_code, quality_analysis
            )

            # Step 5: Calculate confidence score (based on quality and completeness)
            confidence_score = self._calculate_confidence(
                quality_analysis, contract.pattern_code, contract.description
            )

            # Step 6: Estimate success rate (based on quality metrics)
            success_rate = self._estimate_success_rate(
                quality_analysis, complexity_score, maintainability_score
            )

            # Step 7: Create quality metrics model
            metrics = ModelQualityMetrics(
                confidence_score=confidence_score,
                usage_count=0,  # Initial value, will be updated on usage
                success_rate=success_rate,
                complexity_score=complexity_score,
                maintainability_score=maintainability_score,
                performance_score=performance_score,
                quality_score=quality_analysis["quality_score"],
                onex_compliance_score=quality_analysis["onex_compliance_score"],
                metadata={
                    "relevance_score": quality_analysis["relevance_score"],
                    "architectural_era": quality_analysis["architectural_era"],
                    "legacy_indicators": quality_analysis["legacy_indicators"],
                    "omnibase_violations": quality_analysis.get(
                        "omnibase_violations", []
                    ),
                    "assessment_timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Calculate operation duration
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            # Record performance metric
            self._record_metric("quality_assessment_duration_ms", duration_ms)

            self.logger.info(
                f"Quality assessment completed: {contract.pattern_name}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "duration_ms": duration_ms,
                    "quality_score": metrics.quality_score,
                    "confidence_score": metrics.confidence_score,
                },
            )

            return ModelResult(
                success=True,
                data=metrics,
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "duration_ms": round(duration_ms, 2),
                    "operation": "quality_assessment",
                    "pattern_name": contract.pattern_name,
                },
            )

        except Exception as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.error(
                f"Quality assessment failed: {e}",
                exc_info=True,
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "pattern_name": contract.pattern_name,
                },
            )
            return ModelResult(
                success=False,
                error=f"Quality assessment failed: {str(e)}",
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(e).__name__,
                },
            )

    # ========================================================================
    # Private Computation Methods
    # ========================================================================

    def _calculate_complexity(self, code: str) -> int:
        """
        Calculate cyclomatic complexity of code.

        Uses AST analysis to count decision points.

        Args:
            code: Source code to analyze

        Returns:
            Integer complexity score (typically 1-20+)
        """
        try:
            tree = ast.parse(code)
            complexity = 1  # Base complexity

            # Count decision points
            for node in ast.walk(tree):
                if isinstance(
                    node,
                    (
                        ast.If,
                        ast.While,
                        ast.For,
                        ast.ExceptHandler,
                        ast.With,
                        ast.Assert,
                        ast.BoolOp,
                    ),
                ):
                    complexity += 1

            return complexity

        except SyntaxError:
            # If code cannot be parsed, return high complexity
            return 50
        except Exception:
            # Default to moderate complexity on error
            return 10

    def _calculate_maintainability(
        self, code: str, quality_analysis: Dict[str, Any]
    ) -> float:
        """
        Calculate maintainability score.

        Factors:
        - ONEX compliance
        - Code length
        - Complexity
        - Documentation presence
        - Legacy indicators

        Args:
            code: Source code
            quality_analysis: Quality analysis results

        Returns:
            Maintainability score 0.0-1.0
        """
        score = 0.5  # Base score

        # Factor 1: ONEX compliance (40% weight)
        onex_score = quality_analysis.get("onex_compliance_score", 0.5)
        score += (onex_score - 0.5) * 0.4

        # Factor 2: Documentation presence (20% weight)
        has_docstring = '"""' in code or "'''" in code
        if has_docstring:
            score += 0.2
        else:
            score -= 0.1

        # Factor 3: Code length (15% weight)
        lines = code.count("\n")
        if 10 <= lines <= 100:  # Ideal range
            score += 0.15
        elif lines > 200:  # Too long
            score -= 0.15

        # Factor 4: Legacy indicators (25% weight)
        legacy_count = len(quality_analysis.get("legacy_indicators", []))
        if legacy_count == 0:
            score += 0.25
        elif legacy_count > 3:
            score -= 0.25

        return max(0.0, min(1.0, score))

    def _calculate_performance_score(
        self, code: str, quality_analysis: Dict[str, Any]
    ) -> float:
        """
        Calculate estimated performance score.

        Factors:
        - Async patterns (good for performance)
        - Database operations (potential bottleneck)
        - Loop complexity
        - ONEX Effect node patterns (optimized I/O)

        Args:
            code: Source code
            quality_analysis: Quality analysis results

        Returns:
            Performance score 0.0-1.0
        """
        score = 0.5  # Base score

        # Factor 1: Async patterns (30% weight)
        if "async def" in code:
            score += 0.3
        else:
            score -= 0.2

        # Factor 2: ONEX Effect patterns (30% weight)
        if "execute_effect" in code:
            score += 0.3

        # Factor 3: Multiple database calls in loops (penalty)
        if "for" in code and ("await" in code or "query" in code):
            score -= 0.2

        # Factor 4: Architectural era (20% weight)
        era = quality_analysis.get("architectural_era", "")
        if era == "modern_onex":
            score += 0.2
        elif era == "pre_nodebase":
            score -= 0.2

        # Factor 5: Complexity (20% weight)
        onex_score = quality_analysis.get("onex_compliance_score", 0.5)
        score += (onex_score - 0.5) * 0.2

        return max(0.0, min(1.0, score))

    def _calculate_confidence(
        self, quality_analysis: Dict[str, Any], code: str, description: Optional[str]
    ) -> float:
        """
        Calculate confidence score for pattern reliability.

        Factors:
        - Quality score
        - ONEX compliance
        - Documentation completeness
        - Code completeness (no TODOs, FIXMEs)

        Args:
            quality_analysis: Quality analysis results
            code: Source code
            description: Pattern description

        Returns:
            Confidence score 0.0-1.0
        """
        score = quality_analysis.get("quality_score", 0.5)

        # Factor 1: Documentation (20% weight)
        if description and len(description) > 50:
            score += 0.2
        elif not description:
            score -= 0.1

        # Factor 2: Code completeness (20% weight)
        if "TODO" in code or "FIXME" in code or "XXX" in code:
            score -= 0.2
        else:
            score += 0.1

        # Factor 3: ONEX compliance (10% weight)
        onex_score = quality_analysis.get("onex_compliance_score", 0.5)
        score += (onex_score - 0.5) * 0.1

        return max(0.0, min(1.0, score))

    def _estimate_success_rate(
        self,
        quality_analysis: Dict[str, Any],
        complexity: int,
        maintainability: float,
    ) -> float:
        """
        Estimate pattern success rate.

        Factors:
        - Quality score
        - Complexity (simpler = higher success)
        - Maintainability

        Args:
            quality_analysis: Quality analysis results
            complexity: Cyclomatic complexity
            maintainability: Maintainability score

        Returns:
            Estimated success rate 0.0-1.0
        """
        # Base on quality score
        score = quality_analysis.get("quality_score", 0.5)

        # Adjust for complexity
        if complexity <= 5:
            score += 0.2
        elif complexity > 15:
            score -= 0.2

        # Adjust for maintainability
        score += (maintainability - 0.5) * 0.3

        return max(0.0, min(1.0, score))


# ============================================================================
# Example Usage
# ============================================================================


async def example_usage():
    """
    Example usage of NodePatternQualityAssessorCompute.

    Demonstrates:
    - Creating quality assessment contract
    - Executing quality assessment
    - Interpreting quality metrics
    """
    from uuid import uuid4

    # Create Compute node
    node = NodePatternQualityAssessorCompute()

    # Example pattern code
    pattern_code = '''
"""
ONEX Effect Node: Database Writer

Purpose: Write data to database
Node Type: Effect (External I/O)
"""
async def execute_effect(self, contract: ModelContractDatabaseWrite) -> ModelResult:
    """Write data to database."""
    async with self.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("INSERT INTO ...", data)
    return ModelResult(success=True)
'''

    # Create contract
    contract = ModelContractPatternQuality(
        name="assess_database_writer",
        pattern_name="DatabaseWriterPattern",
        pattern_type="code",
        language="python",
        pattern_code=pattern_code,
        description="ONEX Effect pattern for database writes",
        correlation_id=uuid4(),
    )

    # Execute assessment
    result = await node.execute_compute(contract)

    if result.success:
        metrics: ModelQualityMetrics = result.data
        print("\n=== Quality Assessment Results ===")
        print(f"Quality Score: {metrics.quality_score:.2f}")
        print(f"ONEX Compliance: {metrics.onex_compliance_score:.2f}")
        print(f"Confidence: {metrics.confidence_score:.2f}")
        print(f"Complexity: {metrics.complexity_score}")
        print(f"Maintainability: {metrics.maintainability_score:.2f}")
        print(f"Performance: {metrics.performance_score:.2f}")
        print(f"Success Rate: {metrics.success_rate:.2f}")
        print(f"Duration: {result.metadata.get('duration_ms')}ms")
    else:
        print(f"Assessment failed: {result.error}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
