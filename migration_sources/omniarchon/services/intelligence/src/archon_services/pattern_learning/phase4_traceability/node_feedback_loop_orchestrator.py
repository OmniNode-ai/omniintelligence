"""
ONEX Orchestrator Node: Feedback Loop for Pattern Improvement

Purpose: Orchestrate pattern improvement workflow based on usage feedback
Node Type: Orchestrator (Coordinates feedback collection, analysis, validation, and application)
File: node_feedback_loop_orchestrator.py
Class: NodeFeedbackLoopOrchestrator

Pattern: ONEX 4-Node Architecture - Orchestrator
Track: Track 3-4.3 - Phase 4 Feedback Loop
ONEX Compliant: Suffix naming (Node*Orchestrator), file pattern (node_*_orchestrator.py)

Workflow:
1. Collect feedback from Track 2 intelligence hooks
2. Analyze performance and identify improvement opportunities
3. Generate improvement proposals
4. Validate improvements with A/B testing (statistical significance)
5. Apply successful improvements
6. Track lineage and update pattern storage

Author: Archon Intelligence Team
Date: 2025-10-02
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from statistics import mean, median, stdev
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from scipy import stats  # For statistical testing
from src.archon_services.pattern_learning.phase4_traceability.model_contract_feedback_loop import (
    ModelContractFeedbackLoop,
    ModelFeedbackLoopInput,
    ModelFeedbackLoopOutput,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_graph import (
    LineageRelationType,
    ModelLineageEdge,
    ModelLineageGraph,
    ModelLineageNode,
    NodeStatus,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
    FeedbackSentiment,
    ImprovementStatus,
    ModelPatternFeedback,
    ModelPatternImprovement,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Result Model
# ============================================================================


class ModelResult:
    """Result model for Orchestrator operations."""

    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.data = data or {}
        self.error = error
        self.metadata = metadata or {}


# ============================================================================
# ONEX Orchestrator Node: Feedback Loop
# ============================================================================


class NodeFeedbackLoopOrchestrator:
    """
    ONEX Orchestrator Node for pattern improvement feedback loop.

    Implements:
    - ONEX naming convention: Node<Name>Orchestrator
    - File pattern: node_*_orchestrator.py
    - Method signature: async def execute_orchestration(contract) -> ModelResult
    - 5-step workflow: Collect → Analyze → Generate → Validate → Apply
    - Statistical validation with p-value <0.05
    - A/B testing framework
    - Integration with Track 2 intelligence hooks

    Responsibilities:
    - Coordinate feedback collection from Track 2 hooks
    - Analyze pattern performance and identify improvement opportunities
    - Generate improvement proposals
    - Validate improvements with A/B testing
    - Apply successful improvements and track lineage
    - Update pattern storage (Phase 1)

    Performance Targets:
    - Feedback collection: <5s for 1000 executions
    - Analysis: <10s for statistical analysis
    - Validation: <60s for A/B test
    - Total workflow: <1 minute (excluding A/B test duration)

    Statistical Requirements:
    - Minimum sample size: 30 executions
    - Significance level: p-value <0.05
    - Confidence threshold: 95% for auto-apply

    Example:
        >>> orchestrator = NodeFeedbackLoopOrchestrator()
        >>> contract = ModelFeedbackLoopInput(
        ...     pattern_id="pattern_api_debug_v1",
        ...     feedback_type="performance",
        ...     time_window_days=7
        ... )
        >>> result = await orchestrator.execute_orchestration(contract)
        >>> print(f"Improvements: {result.data['improvements_applied']}")
    """

    def __init__(self):
        """Initialize feedback loop orchestrator."""
        self.logger = logging.getLogger("NodeFeedbackLoopOrchestrator")

        # In production, these would be injected dependencies
        # For now, we'll implement inline for demonstration
        self.feedback_store: List[ModelPatternFeedback] = []
        self.improvement_store: List[ModelPatternImprovement] = []
        self.lineage_graph = ModelLineageGraph()

    # ========================================================================
    # ONEX Execute Orchestration Method (Primary Interface)
    # ========================================================================

    async def execute_orchestration(
        self, contract: ModelFeedbackLoopInput
    ) -> ModelResult:
        """
        Execute pattern improvement feedback loop.

        ONEX Method Signature: async def execute_orchestration(contract) -> ModelResult

        Args:
            contract: ModelFeedbackLoopInput with feedback loop parameters

        Returns:
            ModelResult with improvement results and statistics

        Workflow:
            1. Collect feedback from Track 2 hooks (execution traces)
            2. Analyze performance and identify improvement opportunities
            3. Generate improvement proposals
            4. Validate improvements with A/B testing
            5. Apply successful improvements and update lineage

        Performance:
            - Collection: <5s for 1000 executions
            - Analysis: <10s
            - Total: <60s (excluding A/B test wait time)
        """
        start_time = datetime.now(timezone.utc)
        operation_name = contract.operation
        pattern_id = contract.pattern_id

        try:
            self.logger.info(
                f"Starting feedback loop orchestration: {operation_name}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "pattern_id": pattern_id,
                    "feedback_type": contract.feedback_type,
                    "time_window_days": contract.time_window_days,
                },
            )

            # Initialize output
            output = ModelFeedbackLoopOutput(
                success=True,
                pattern_id=pattern_id,
                correlation_id=contract.correlation_id,
                workflow_stages={},
            )

            # ================================================================
            # Step 1: Collect Feedback from Track 2 Hooks
            # ================================================================
            self.logger.info("Step 1: Collecting feedback from Track 2 hooks")
            feedback_items, executions = await self._collect_feedback(
                pattern_id=pattern_id,
                time_window_days=contract.time_window_days,
                feedback_type=contract.feedback_type,
            )

            output.feedback_collected = len(feedback_items)
            output.executions_analyzed = len(executions)
            output.workflow_stages["collect"] = "completed"

            if len(feedback_items) < contract.min_sample_size:
                output.warnings.append(
                    f"Insufficient feedback items: {len(feedback_items)} < {contract.min_sample_size}"
                )
                output.workflow_stages["analyze"] = "skipped"
                output.workflow_stages["validate"] = "skipped"
                output.workflow_stages["apply"] = "skipped"

                return self._build_result(output, start_time)

            # ================================================================
            # Step 2: Analyze Performance and Identify Improvements
            # ================================================================
            self.logger.info(
                "Step 2: Analyzing performance and identifying improvements"
            )
            improvement_opportunities = await self._analyze_and_generate_improvements(
                pattern_id=pattern_id,
                feedback_items=feedback_items,
                executions=executions,
            )

            output.improvements_identified = len(improvement_opportunities)
            output.improvement_opportunities = [
                {
                    "type": imp.improvement_type,
                    "description": imp.description,
                    "expected_delta": imp.performance_delta,
                }
                for imp in improvement_opportunities
            ]
            output.workflow_stages["analyze"] = "completed"

            if not improvement_opportunities:
                self.logger.info("No improvement opportunities identified")
                output.workflow_stages["validate"] = "skipped"
                output.workflow_stages["apply"] = "skipped"
                return self._build_result(output, start_time)

            # ================================================================
            # Step 3: Validate Improvements with A/B Testing
            # ================================================================
            if contract.enable_ab_testing:
                self.logger.info("Step 3: Validating improvements with A/B testing")
                validated_improvements = await self._validate_improvements(
                    pattern_id=pattern_id,
                    improvements=improvement_opportunities,
                    significance_level=contract.significance_level,
                    min_sample_size=contract.min_sample_size,
                )

                output.improvements_validated = len(validated_improvements)
                output.validation_results = [
                    {
                        "improvement_id": str(imp.improvement_id),
                        "p_value": imp.p_value,
                        "confidence": imp.confidence_score,
                        "significant": (
                            imp.p_value < contract.significance_level
                            if imp.p_value
                            else False
                        ),
                    }
                    for imp in validated_improvements
                ]
                output.workflow_stages["validate"] = "completed"
            else:
                # Skip validation, use all improvements
                validated_improvements = improvement_opportunities
                output.improvements_validated = len(validated_improvements)
                output.workflow_stages["validate"] = "skipped"

            # ================================================================
            # Step 4: Apply Successful Improvements
            # ================================================================
            self.logger.info("Step 4: Applying successful improvements")
            applied, rejected = await self._apply_improvements(
                pattern_id=pattern_id,
                improvements=validated_improvements,
                auto_apply_threshold=contract.auto_apply_threshold,
            )

            output.improvements_applied = len(applied)
            output.improvements_rejected = len(rejected)
            output.workflow_stages["apply"] = "completed"

            # ================================================================
            # Step 5: Calculate Performance Delta and Statistics
            # ================================================================
            if applied:
                # Calculate baseline and improved metrics
                baseline = self._calculate_baseline_metrics(feedback_items)
                improved = self._calculate_improved_metrics(applied, baseline)

                output.baseline_metrics = baseline
                output.improved_metrics = improved

                # Calculate performance delta
                if baseline.get("avg_execution_time_ms", 0) > 0:
                    time_delta = (
                        baseline["avg_execution_time_ms"]
                        - improved["avg_execution_time_ms"]
                    ) / baseline["avg_execution_time_ms"]
                    output.performance_delta = time_delta

                # Get best p-value from applied improvements
                p_values = [imp.p_value for imp in applied if imp.p_value is not None]
                if p_values:
                    output.p_value = min(p_values)
                    output.statistically_significant = (
                        output.p_value < contract.significance_level
                    )

                # Get highest confidence
                confidences = [imp.confidence_score for imp in applied]
                if confidences:
                    output.confidence_score = max(confidences)

            # ================================================================
            # Step 6: Schedule Next Review
            # ================================================================
            output.next_review_date = datetime.now(timezone.utc) + timedelta(
                days=contract.time_window_days
            )

            # Build final result
            return self._build_result(output, start_time)

        except ValueError as e:
            return self._build_error_result(
                str(e), "validation_error", contract.correlation_id, start_time
            )
        except Exception as e:
            self.logger.error(
                f"Feedback loop orchestration failed: {e}",
                exc_info=True,
                extra={"correlation_id": str(contract.correlation_id)},
            )
            return self._build_error_result(
                str(e),
                type(e).__name__,
                contract.correlation_id,
                start_time,
            )

    # ========================================================================
    # Step 1: Feedback Collection
    # ========================================================================

    async def _collect_feedback(
        self, pattern_id: str, time_window_days: int, feedback_type: str
    ) -> tuple[List[ModelPatternFeedback], List[Dict[str, Any]]]:
        """
        Collect feedback from Track 2 intelligence hooks.

        Integrates with:
        - hook_executions table (Track 2)
        - execution_traces table (Track 2)
        - quality_results from hooks
        - performance_results from hooks

        Args:
            pattern_id: Pattern to collect feedback for
            time_window_days: Time window in days
            feedback_type: Type of feedback to collect

        Returns:
            Tuple of (feedback_items, execution_data)
        """
        # In production, this would query the database
        # For now, we'll simulate with mock data

        # Simulate database query for executions
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_window_days)

        # Mock execution data (in production, this comes from hook_executions)
        executions = await self._query_hook_executions(pattern_id, cutoff_date)

        # Convert executions to feedback items
        feedback_items = []
        for exec_data in executions:
            # Get execution_id and convert to string if it's a UUID
            exec_id = exec_data.get("execution_id", uuid4())
            exec_id_str = str(exec_id) if isinstance(exec_id, UUID) else exec_id

            feedback = ModelPatternFeedback(
                pattern_id=UUID(pattern_id) if "-" in pattern_id else uuid4(),
                execution_id=exec_id_str,
                sentiment=self._determine_sentiment(exec_data),
                explicit_rating=exec_data.get("quality_score"),
                implicit_signals={
                    "execution_time_ms": exec_data.get("duration_ms", 0),
                    "success": exec_data.get("status") == "success",
                    "retry_count": exec_data.get("retry_count", 0),
                },
                context=exec_data.get("context", {}),
                success=exec_data.get("status") == "success",
                quality_score=exec_data.get("quality_score"),
                performance_score=exec_data.get("performance_score"),
            )
            feedback_items.append(feedback)

        self.logger.info(
            f"Collected {len(feedback_items)} feedback items from {len(executions)} executions"
        )

        return feedback_items, executions

    async def _query_hook_executions(
        self, pattern_id: str, cutoff_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Query hook_executions table from Track 2.

        In production, this would be a database query like:
        SELECT * FROM hook_executions
        WHERE pattern_id = %s AND started_at >= %s
        ORDER BY started_at DESC

        For now, we simulate with mock data.
        """
        # Simulate 100 executions with varying performance
        executions = []
        for i in range(100):
            executions.append(
                {
                    "execution_id": uuid4(),
                    "pattern_id": pattern_id,
                    "started_at": cutoff_date + timedelta(hours=i),
                    "duration_ms": 400 + (i % 50) * 10,  # Varying execution time
                    "status": "success" if i % 10 != 0 else "failed",
                    "quality_score": 0.85 + (i % 15) * 0.01,
                    "performance_score": 0.80 + (i % 20) * 0.01,
                    "retry_count": 1 if i % 20 == 0 else 0,
                    "context": {"complexity": "medium", "domain": "api_development"},
                }
            )
        return executions

    def _determine_sentiment(self, execution: Dict[str, Any]) -> FeedbackSentiment:
        """Determine sentiment from execution data."""
        quality_score = execution.get("quality_score", 0.5)
        performance_score = execution.get("performance_score", 0.5)
        success = execution.get("status") == "success"

        if not success:
            return FeedbackSentiment.NEGATIVE

        avg_score = (quality_score + performance_score) / 2
        if avg_score >= 0.9:
            return FeedbackSentiment.POSITIVE
        elif avg_score >= 0.7:
            return FeedbackSentiment.NEUTRAL
        else:
            return FeedbackSentiment.NEGATIVE

    # ========================================================================
    # Step 2: Analysis and Improvement Generation
    # ========================================================================

    async def _analyze_and_generate_improvements(
        self,
        pattern_id: str,
        feedback_items: List[ModelPatternFeedback],
        executions: List[Dict[str, Any]],
    ) -> List[ModelPatternImprovement]:
        """
        Analyze feedback and generate improvement proposals.

        Identifies:
        - Performance bottlenecks (slow execution times)
        - Quality issues (low quality scores)
        - High error rates
        - Patterns in failures

        Args:
            pattern_id: Pattern being analyzed
            feedback_items: Collected feedback
            executions: Raw execution data

        Returns:
            List of improvement proposals
        """
        improvements = []

        # Analyze execution times
        execution_times = [
            fb.implicit_signals.get("execution_time_ms", 0) for fb in feedback_items
        ]

        if execution_times:
            avg_time = mean(execution_times)
            median_time = median(execution_times)
            std_time = stdev(execution_times) if len(execution_times) > 1 else 0

            # If execution time is slow or highly variable, suggest caching
            if avg_time > 400 or std_time > 100:
                improvement = ModelPatternImprovement(
                    pattern_id=UUID(pattern_id) if "-" in pattern_id else uuid4(),
                    improvement_type="performance",
                    status=ImprovementStatus.PROPOSED,
                    description="Add caching layer to reduce execution time",
                    proposed_changes={
                        "add_caching": True,
                        "cache_ttl_seconds": 300,
                        "expected_improvement": 0.60,  # 60% faster
                    },
                    baseline_metrics={
                        "avg_execution_time_ms": avg_time,
                        "median_execution_time_ms": median_time,
                        "std_execution_time_ms": std_time,
                    },
                    performance_delta=0.60,
                )
                improvements.append(improvement)

        # Analyze quality scores
        quality_scores = [
            fb.quality_score for fb in feedback_items if fb.quality_score is not None
        ]

        if quality_scores:
            avg_quality = mean(quality_scores)

            # If quality is suboptimal, suggest quality improvements
            if avg_quality < 0.85:
                improvement = ModelPatternImprovement(
                    pattern_id=UUID(pattern_id) if "-" in pattern_id else uuid4(),
                    improvement_type="quality",
                    status=ImprovementStatus.PROPOSED,
                    description="Improve code quality and error handling",
                    proposed_changes={
                        "add_validation": True,
                        "improve_error_handling": True,
                        "expected_improvement": 0.15,  # 15% better quality
                    },
                    baseline_metrics={"avg_quality_score": avg_quality},
                    performance_delta=0.15,
                )
                improvements.append(improvement)

        # Analyze success rate
        success_rate = sum(1 for fb in feedback_items if fb.success) / len(
            feedback_items
        )

        if success_rate < 0.90:
            improvement = ModelPatternImprovement(
                pattern_id=UUID(pattern_id) if "-" in pattern_id else uuid4(),
                improvement_type="reliability",
                status=ImprovementStatus.PROPOSED,
                description="Improve error handling and retry logic",
                proposed_changes={
                    "add_retry_logic": True,
                    "improve_error_recovery": True,
                    "expected_improvement": 0.10,  # 10% better success rate
                },
                baseline_metrics={"success_rate": success_rate},
                performance_delta=0.10,
            )
            improvements.append(improvement)

        self.logger.info(f"Generated {len(improvements)} improvement proposals")
        return improvements

    # ========================================================================
    # Step 3: A/B Testing Validation
    # ========================================================================

    async def _validate_improvements(
        self,
        pattern_id: str,
        improvements: List[ModelPatternImprovement],
        significance_level: float,
        min_sample_size: int,
    ) -> List[ModelPatternImprovement]:
        """
        Validate improvements with A/B testing and statistical significance.

        Implements:
        - A/B testing framework
        - Statistical hypothesis testing
        - P-value calculation
        - Confidence scoring

        Args:
            pattern_id: Pattern being tested
            improvements: Improvement proposals to validate
            significance_level: Required p-value (typically 0.05)
            min_sample_size: Minimum test sample size

        Returns:
            List of validated improvements with statistical results
        """
        validated = []

        for improvement in improvements:
            self.logger.info(
                f"Validating improvement: {improvement.description}",
                extra={"improvement_id": str(improvement.improvement_id)},
            )

            # Run A/B test (simulated for now)
            control_samples, treatment_samples = await self._run_ab_test(
                pattern_id=pattern_id,
                improvement=improvement,
                sample_size=min_sample_size,
            )

            # Calculate statistical significance
            if (
                len(control_samples) >= min_sample_size
                and len(treatment_samples) >= min_sample_size
            ):
                # Use t-test for comparing means
                t_stat, p_value = stats.ttest_ind(treatment_samples, control_samples)

                # Calculate confidence score (inverse of p-value, capped at 0.99)
                confidence = min(1.0 - p_value, 0.99)

                # Update improvement with test results
                improvement.p_value = float(p_value)
                improvement.confidence_score = float(confidence)
                improvement.sample_size = len(control_samples) + len(treatment_samples)
                improvement.status = (
                    ImprovementStatus.VALIDATED
                    if p_value < significance_level
                    else ImprovementStatus.REJECTED
                )

                # Calculate actual performance delta
                control_mean = mean(control_samples)
                treatment_mean = mean(treatment_samples)
                if control_mean > 0:
                    actual_delta = (control_mean - treatment_mean) / control_mean
                    improvement.performance_delta = float(actual_delta)

                # Store test results
                improvement.test_results = [
                    {
                        "control_mean": control_mean,
                        "treatment_mean": treatment_mean,
                        "t_statistic": float(t_stat),
                        "p_value": float(p_value),
                        "sample_size_control": len(control_samples),
                        "sample_size_treatment": len(treatment_samples),
                    }
                ]

                # Update improved metrics
                improvement.improved_metrics = {
                    "avg_execution_time_ms": treatment_mean,
                }

                if improvement.status == ImprovementStatus.VALIDATED:
                    validated.append(improvement)
                    self.logger.info(
                        f"Improvement validated: p={p_value:.4f}, confidence={confidence:.2f}"
                    )
                else:
                    self.logger.info(
                        f"Improvement rejected: p={p_value:.4f} >= {significance_level}"
                    )
            else:
                self.logger.warning(
                    f"Insufficient sample size for A/B test: {len(control_samples)} + {len(treatment_samples)}"
                )

        return validated

    async def _run_ab_test(
        self,
        pattern_id: str,
        improvement: ModelPatternImprovement,
        sample_size: int,
    ) -> tuple[List[float], List[float]]:
        """
        Run A/B test for an improvement.

        In production, this would:
        1. Deploy both versions (control and treatment)
        2. Randomly assign executions to each
        3. Collect performance metrics
        4. Return samples for statistical analysis

        For now, we simulate with realistic data.

        Args:
            pattern_id: Pattern being tested
            improvement: Improvement to test
            sample_size: Number of samples per variant

        Returns:
            Tuple of (control_samples, treatment_samples)
        """
        # Simulate control group (baseline performance)
        baseline_mean = improvement.baseline_metrics.get("avg_execution_time_ms", 450.0)
        baseline_std = improvement.baseline_metrics.get("std_execution_time_ms", 50.0)

        control_samples = [
            max(
                0,
                baseline_mean
                + baseline_std
                * (
                    int(hashlib.blake2b(f"{i}c".encode()).hexdigest()[:8], 16) % 100
                    - 50
                )
                / 25,
            )
            for i in range(sample_size)
        ]

        # Simulate treatment group (with improvement)
        expected_improvement = improvement.performance_delta
        treatment_mean = baseline_mean * (1 - expected_improvement)
        treatment_std = baseline_std * 0.8  # Improvements often reduce variance

        treatment_samples = [
            max(
                0,
                treatment_mean
                + treatment_std
                * (
                    int(hashlib.blake2b(f"{i}t".encode()).hexdigest()[:8], 16) % 100
                    - 50
                )
                / 25,
            )
            for i in range(sample_size)
        ]

        return control_samples, treatment_samples

    # ========================================================================
    # Step 4: Apply Improvements
    # ========================================================================

    async def _apply_improvements(
        self,
        pattern_id: str,
        improvements: List[ModelPatternImprovement],
        auto_apply_threshold: float,
    ) -> tuple[List[ModelPatternImprovement], List[ModelPatternImprovement]]:
        """
        Apply validated improvements and track lineage.

        Applies improvements with confidence >= auto_apply_threshold.
        Updates pattern storage and lineage graph.

        Args:
            pattern_id: Pattern to update
            improvements: Validated improvements
            auto_apply_threshold: Confidence threshold for auto-apply

        Returns:
            Tuple of (applied_improvements, rejected_improvements)
        """
        applied = []
        rejected = []

        for improvement in improvements:
            # Check if confidence meets threshold
            if improvement.confidence_score >= auto_apply_threshold:
                # Apply improvement
                improvement.status = ImprovementStatus.APPLIED
                improvement.applied_at = datetime.now(timezone.utc)

                # In production, this would:
                # 1. Update pattern in storage
                # 2. Create new pattern version
                # 3. Update lineage graph

                # For now, we track in memory
                self.improvement_store.append(improvement)

                # Track lineage
                await self._update_lineage(pattern_id, improvement)

                applied.append(improvement)
                self.logger.info(
                    f"Applied improvement: {improvement.description}",
                    extra={
                        "improvement_id": str(improvement.improvement_id),
                        "confidence": improvement.confidence_score,
                    },
                )
            else:
                # Reject improvement (confidence too low)
                improvement.status = ImprovementStatus.REJECTED
                rejected.append(improvement)
                self.logger.info(
                    f"Rejected improvement (low confidence): {improvement.description}",
                    extra={
                        "improvement_id": str(improvement.improvement_id),
                        "confidence": improvement.confidence_score,
                        "threshold": auto_apply_threshold,
                    },
                )

        return applied, rejected

    async def _update_lineage(
        self, pattern_id: str, improvement: ModelPatternImprovement
    ) -> None:
        """
        Update lineage graph with new pattern version.

        Creates new lineage node and edge to track pattern evolution.

        Args:
            pattern_id: Original pattern ID
            improvement: Applied improvement
        """
        # Create new version node
        new_node = ModelLineageNode(
            pattern_id=UUID(pattern_id) if "-" in pattern_id else uuid4(),
            pattern_name=f"{pattern_id}_improved",
            version=2,  # In production, increment from current version
            status=NodeStatus.ACTIVE,
            usage_count=0,
            success_rate=0.0,
            metadata={
                "improvement_id": str(improvement.improvement_id),
                "improvement_type": improvement.improvement_type,
                "performance_delta": improvement.performance_delta,
            },
        )

        # Add node to graph
        self.lineage_graph.add_node(new_node)

        # Create edge from old to new version
        edge = ModelLineageEdge(
            source_pattern_id=UUID(pattern_id) if "-" in pattern_id else uuid4(),
            target_pattern_id=new_node.pattern_id,
            relation_type=LineageRelationType.DERIVED_FROM,
            metadata={
                "improvement_description": improvement.description,
                "applied_at": (
                    improvement.applied_at.isoformat()
                    if improvement.applied_at
                    else None
                ),
            },
        )

        # Add edge to graph
        self.lineage_graph.add_edge(edge)

        self.logger.info(
            f"Updated lineage graph: {pattern_id} -> {new_node.pattern_id}"
        )

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _calculate_baseline_metrics(
        self, feedback_items: List[ModelPatternFeedback]
    ) -> Dict[str, float]:
        """Calculate baseline metrics from feedback."""
        execution_times = [
            fb.implicit_signals.get("execution_time_ms", 0) for fb in feedback_items
        ]
        quality_scores = [
            fb.quality_score for fb in feedback_items if fb.quality_score is not None
        ]
        success_rate = sum(1 for fb in feedback_items if fb.success) / len(
            feedback_items
        )

        return {
            "avg_execution_time_ms": mean(execution_times) if execution_times else 0,
            "median_execution_time_ms": (
                median(execution_times) if execution_times else 0
            ),
            "avg_quality_score": mean(quality_scores) if quality_scores else 0,
            "success_rate": success_rate,
        }

    def _calculate_improved_metrics(
        self,
        improvements: List[ModelPatternImprovement],
        baseline: Dict[str, float],
    ) -> Dict[str, float]:
        """Calculate improved metrics from applied improvements."""
        # Start with baseline
        improved = baseline.copy()

        # Apply performance deltas
        for imp in improvements:
            if imp.improvement_type == "performance":
                improved["avg_execution_time_ms"] *= 1 - imp.performance_delta
            elif imp.improvement_type == "quality":
                improved["avg_quality_score"] *= 1 + imp.performance_delta
            elif imp.improvement_type == "reliability":
                improved["success_rate"] = min(
                    1.0, improved["success_rate"] + imp.performance_delta
                )

        return improved

    def _build_result(
        self, output: ModelFeedbackLoopOutput, start_time: datetime
    ) -> ModelResult:
        """Build successful result."""
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        output.duration_ms = duration_ms

        self.logger.info(
            "Feedback loop completed successfully",
            extra={
                "correlation_id": str(output.correlation_id),
                "improvements_applied": output.improvements_applied,
                "performance_delta": output.performance_delta,
                "duration_ms": duration_ms,
            },
        )

        return ModelResult(
            success=True,
            data=output.model_dump(mode="json"),
            metadata={
                "correlation_id": str(output.correlation_id),
                "duration_ms": round(duration_ms, 2),
            },
        )

    def _build_error_result(
        self, error: str, error_type: str, correlation_id: UUID, start_time: datetime
    ) -> ModelResult:
        """Build error result."""
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        return ModelResult(
            success=False,
            error=error,
            metadata={
                "correlation_id": str(correlation_id),
                "duration_ms": round(duration_ms, 2),
                "error_type": error_type,
            },
        )


# ============================================================================
# Module Exports
# ============================================================================

__all__ = [
    "NodeFeedbackLoopOrchestrator",
    "ModelFeedbackLoopInput",
    "ModelFeedbackLoopOutput",
    "ModelContractFeedbackLoop",
]
