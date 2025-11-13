"""
ONEX Orchestrator Node: Multi-Model Consensus Validator

Purpose: Orchestrate multi-model consensus validation for code quality decisions
Node Type: Orchestrator (Workflow coordination, parallel model execution)
File: node_consensus_validator_orchestrator.py
Class: NodeConsensusValidatorOrchestrator

Pattern: ONEX 4-Node Architecture - Orchestrator
Track: Track 3-3.7 - Phase 3 Compliance Reporting
ONEX Compliant: Suffix naming (Node*Orchestrator), file pattern (node_*_orchestrator.py)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from src.archon_services.pattern_learning.phase3_validation.reporting.models.model_consensus_result import (
    EnumConsensusDecision,
    EnumModelType,
    ModelConsensusResult,
    ModelModelVote,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Contract Model
# ============================================================================


class ModelContractConsensusValidator(BaseModel):
    """
    Contract for multi-model consensus validation operations.

    Defines the input structure for orchestrating consensus validation
    across multiple AI models.
    """

    name: str = Field(..., description="Operation name")
    operation: str = Field(..., description="Operation type: validate_consensus")
    correlation_id: UUID = Field(
        default_factory=uuid4, description="Correlation ID for tracking"
    )

    # Validation inputs
    code_path: str = Field(..., description="Path to code being validated")
    decision_type: str = Field(
        ..., description="Type of decision: architecture, code_change, refactoring"
    )
    validation_scope: str = Field(
        default="file", description="Scope: file, module, project"
    )
    code_content: str | None = Field(
        default=None, description="Code content to validate"
    )

    # Model configuration
    models: list[str] = Field(
        default_factory=lambda: ["gemini-flash", "codestral", "deepseek-lite"],
        description="Models to consult",
    )
    required_agreement: float = Field(
        default=0.67,
        description="Required agreement threshold (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    parallel_execution: bool = Field(
        default=True, description="Execute models in parallel"
    )

    # Validation criteria
    validation_criteria: dict[str, Any] = Field(
        default_factory=dict, description="Specific validation criteria"
    )

    # MCP integration settings
    use_mcp_zen: bool = Field(
        default=True, description="Use mcp__zen__consensus for validation"
    )
    use_code_quality_analyzer: bool = Field(
        default=True, description="Integrate with agent-code-quality-analyzer"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ModelResult(BaseModel):
    """Result model for Orchestrator operations."""

    success: bool = Field(..., description="Operation success status")
    data: dict[str, Any] | None = Field(default=None, description="Result data")
    error: str | None = Field(default=None, description="Error message if failed")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


# ============================================================================
# ONEX Orchestrator Node: Consensus Validator
# ============================================================================


class NodeConsensusValidatorOrchestrator:
    """
    ONEX Orchestrator Node for multi-model consensus validation.

    Implements:
    - ONEX naming convention: Node<Name>Orchestrator
    - File pattern: node_*_orchestrator.py
    - Method signature: async def execute_orchestration(contract) -> ModelResult
    - Parallel model execution coordination
    - Consensus calculation and aggregation
    - Integration with mcp__zen__consensus and agent-code-quality-analyzer

    Responsibilities:
    - Coordinate parallel model validation
    - Collect and aggregate model votes
    - Calculate consensus decision
    - Identify common findings across models
    - Generate consensus report

    Performance Targets:
    - Parallel execution: All models complete within 5-10s
    - Sequential execution: <30s total
    - Consensus calculation: <100ms

    Consensus Logic:
    - Default: 2 of 3 models must agree (67% threshold)
    - Configurable threshold via contract
    - Ties resolved by highest average confidence

    Example:
        >>> node = NodeConsensusValidatorOrchestrator()
        >>> contract = ModelContractConsensusValidator(
        ...     name="validate_architecture",
        ...     operation="validate_consensus",
        ...     code_path="src/validators/node_validator.py",
        ...     decision_type="architecture"
        ... )
        >>> result = await node.execute_orchestration(contract)
        >>> print(result.data["consensus_reached"])
    """

    def __init__(self):
        """Initialize consensus validator Orchestrator node."""
        self.logger = logging.getLogger("NodeConsensusValidatorOrchestrator")

    async def execute_orchestration(
        self, contract: ModelContractConsensusValidator
    ) -> ModelResult:
        """
        Execute multi-model consensus validation.

        ONEX Method Signature: async def execute_orchestration(contract) -> ModelResult

        Args:
            contract: ModelContractConsensusValidator with validation details

        Returns:
            ModelResult with consensus decision and detailed analysis

        Workflow:
            1. Validate inputs and prepare validation context
            2. Execute models in parallel (or sequential if configured)
            3. Collect votes from each model
            4. Calculate consensus and agreement metrics
            5. Identify common findings and recommendations
            6. Generate comprehensive consensus report

        Performance:
            - Parallel: 5-10s for 3 models
            - Sequential: <30s total
        """
        start_time = datetime.now(timezone.utc)
        operation_name = contract.operation

        try:
            self.logger.info(
                f"Starting multi-model consensus validation: {operation_name}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "code_path": contract.code_path,
                    "decision_type": contract.decision_type,
                    "models": contract.models,
                },
            )

            # Initialize consensus result
            consensus_result = ModelConsensusResult(
                code_path=contract.code_path,
                decision_type=contract.decision_type,
                validation_scope=contract.validation_scope,
                votes=[],
                total_models=len(contract.models),
                models_voted=0,
                consensus_reached=False,
                consensus_decision=EnumConsensusDecision.ABSTAIN,
                consensus_confidence=0.0,
                agreement_percentage=0.0,
                required_agreement=contract.required_agreement,
                threshold_met=False,
                average_score=0.0,
                parallel_execution=contract.parallel_execution,
            )

            # Execute model validations
            if contract.parallel_execution:
                votes = await self._execute_parallel_validation(contract)
            else:
                votes = await self._execute_sequential_validation(contract)

            consensus_result.votes = votes
            consensus_result.models_voted = len(votes)

            # Calculate consensus
            consensus_result.calculate_consensus()

            # Extract common findings
            consensus_result.common_findings = self._extract_common_findings(votes)
            consensus_result.common_concerns = self._extract_common_concerns(votes)
            consensus_result.common_recommendations = (
                self._extract_common_recommendations(votes)
            )

            # Calculate total execution time
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            consensus_result.total_execution_time_ms = duration_ms

            self.logger.info(
                f"Consensus validation completed: {consensus_result.consensus_decision.value}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "consensus_reached": consensus_result.consensus_reached,
                    "agreement_percentage": consensus_result.agreement_percentage,
                    "duration_ms": duration_ms,
                },
            )

            return ModelResult(
                success=True,
                data=consensus_result.to_dict(),
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                },
            )

        except ValueError as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.error(
                f"Validation error: {e}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                },
            )
            return ModelResult(
                success=False,
                error=f"Validation error: {str(e)}",
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "validation_error",
                },
            )

        except Exception as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.error(
                f"Consensus validation failed: {e}",
                exc_info=True,
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                },
            )
            return ModelResult(
                success=False,
                error=f"Operation failed: {str(e)}",
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(e).__name__,
                },
            )

    # ========================================================================
    # Execution Coordination
    # ========================================================================

    async def _execute_parallel_validation(
        self, contract: ModelContractConsensusValidator
    ) -> list[ModelModelVote]:
        """Execute model validations in parallel."""
        self.logger.info(
            f"Executing {len(contract.models)} models in parallel",
            extra={"correlation_id": str(contract.correlation_id)},
        )

        # Create tasks for each model
        tasks = [
            self._validate_with_model(contract, model_name)
            for model_name in contract.models
        ]

        # Execute in parallel with timeout
        votes = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log failures
        valid_votes = []
        for i, vote in enumerate(votes):
            if isinstance(vote, Exception):
                self.logger.warning(
                    f"Model {contract.models[i]} failed: {vote}",
                    extra={"correlation_id": str(contract.correlation_id)},
                )
            else:
                valid_votes.append(vote)

        return valid_votes

    async def _execute_sequential_validation(
        self, contract: ModelContractConsensusValidator
    ) -> list[ModelModelVote]:
        """Execute model validations sequentially."""
        self.logger.info(
            f"Executing {len(contract.models)} models sequentially",
            extra={"correlation_id": str(contract.correlation_id)},
        )

        votes = []
        for model_name in contract.models:
            try:
                vote = await self._validate_with_model(contract, model_name)
                votes.append(vote)
            except Exception as e:
                self.logger.warning(
                    f"Model {model_name} failed: {e}",
                    extra={"correlation_id": str(contract.correlation_id)},
                )

        return votes

    async def _validate_with_model(
        self, contract: ModelContractConsensusValidator, model_name: str
    ) -> ModelModelVote:
        """
        Validate code with a specific AI model.

        Args:
            contract: Validation contract
            model_name: Name of model to use

        Returns:
            ModelModelVote with model's decision and analysis

        Note:
            In production, this would integrate with:
            - mcp__zen__consensus for consensus validation
            - agent-code-quality-analyzer for quality analysis
            - Direct model API calls

            For now, returns simulated votes for testing.
        """
        start_time = datetime.now(timezone.utc)

        # TODO: Integrate with actual model APIs
        # This is a placeholder implementation for testing

        # Simulate model analysis (replace with real integration)
        await asyncio.sleep(0.1)  # Simulate API call

        # Mock decision logic (replace with real model analysis)
        decision = EnumConsensusDecision.APPROVE
        confidence = 0.85
        score = 0.90

        # Create vote
        vote = ModelModelVote(
            model_type=self._get_model_type(model_name),
            model_version="1.0.0",
            decision=decision,
            confidence=confidence,
            score=score,
            reasoning=f"Code analysis by {model_name}: Follows ONEX patterns",
            key_findings=[
                "Correct ONEX naming conventions",
                "Proper contract implementation",
                "Good error handling",
            ],
            concerns=["Could improve documentation", "Add more comprehensive tests"],
            strengths=["Clean architecture", "Type safety", "Performance optimized"],
            recommendations=[
                "Add inline documentation",
                "Expand test coverage to 90%",
            ],
            required_changes=[],
            execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds()
            * 1000,
        )

        self.logger.info(
            f"Model {model_name} vote: {decision.value} (confidence: {confidence:.2f})",
            extra={"correlation_id": str(contract.correlation_id)},
        )

        return vote

    def _get_model_type(self, model_name: str) -> EnumModelType:
        """Map model name to EnumModelType."""
        model_map = {
            "gemini-flash": EnumModelType.GEMINI_FLASH,
            "codestral": EnumModelType.CODESTRAL,
            "deepseek-lite": EnumModelType.DEEPSEEK_LITE,
            "llama-3.1": EnumModelType.LLAMA_31,
            "deepseek-full": EnumModelType.DEEPSEEK_FULL,
        }
        return model_map.get(model_name, EnumModelType.GEMINI_FLASH)

    # ========================================================================
    # Analysis Aggregation
    # ========================================================================

    def _extract_common_findings(self, votes: list[ModelModelVote]) -> list[str]:
        """Extract findings mentioned by multiple models."""
        findings_count: dict[str, int] = {}

        for vote in votes:
            for finding in vote.key_findings:
                findings_count[finding] = findings_count.get(finding, 0) + 1

        # Return findings mentioned by at least 2 models
        threshold = min(2, len(votes))
        return [
            finding for finding, count in findings_count.items() if count >= threshold
        ]

    def _extract_common_concerns(self, votes: list[ModelModelVote]) -> list[str]:
        """Extract concerns mentioned by multiple models."""
        concerns_count: dict[str, int] = {}

        for vote in votes:
            for concern in vote.concerns:
                concerns_count[concern] = concerns_count.get(concern, 0) + 1

        # Return concerns mentioned by at least 2 models
        threshold = min(2, len(votes))
        return [
            concern for concern, count in concerns_count.items() if count >= threshold
        ]

    def _extract_common_recommendations(self, votes: list[ModelModelVote]) -> list[str]:
        """Extract recommendations mentioned by multiple models."""
        recommendations_count: dict[str, int] = {}

        for vote in votes:
            for recommendation in vote.recommendations:
                recommendations_count[recommendation] = (
                    recommendations_count.get(recommendation, 0) + 1
                )

        # Return recommendations mentioned by at least 2 models
        threshold = min(2, len(votes))
        return [
            rec for rec, count in recommendations_count.items() if count >= threshold
        ]
