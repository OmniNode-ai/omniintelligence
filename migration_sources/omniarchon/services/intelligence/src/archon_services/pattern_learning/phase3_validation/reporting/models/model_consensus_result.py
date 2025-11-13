"""
Consensus Validation Models - Multi-model consensus result structures.

Provides data models for multi-model consensus validation including:
- Individual model votes and confidence scores
- Consensus calculation and agreement metrics
- Detailed reasoning and recommendations

ONEX Compliance: Pure data models, no business logic
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


# NOTE: correlation_id support enabled for tracing
class EnumConsensusDecision(str, Enum):
    """Consensus decision types."""

    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_REVISION = "needs_revision"
    ABSTAIN = "abstain"


class EnumModelType(str, Enum):
    """AI model types for consensus validation."""

    GEMINI_FLASH = "gemini-flash"
    CODESTRAL = "codestral"
    DEEPSEEK_LITE = "deepseek-lite"
    LLAMA_31 = "llama-3.1"
    DEEPSEEK_FULL = "deepseek-full"


class ModelModelVote(BaseModel):
    """
    Individual model's validation vote.

    Represents a single AI model's validation assessment with
    reasoning and confidence scoring.
    """

    vote_id: UUID = Field(default_factory=uuid4, description="Unique vote identifier")
    model_type: EnumModelType = Field(..., description="AI model type")
    model_version: str = Field(..., description="Model version identifier")
    decision: EnumConsensusDecision = Field(..., description="Model's decision")
    confidence: float = Field(
        ..., description="Confidence in decision (0.0-1.0)", ge=0.0, le=1.0
    )
    score: float = Field(
        ..., description="Quality/compliance score (0.0-1.0)", ge=0.0, le=1.0
    )

    # Reasoning and analysis
    reasoning: str = Field(..., description="Detailed reasoning for decision")
    key_findings: list[str] = Field(
        default_factory=list, description="Key findings from analysis"
    )
    concerns: list[str] = Field(default_factory=list, description="Identified concerns")
    strengths: list[str] = Field(
        default_factory=list, description="Identified strengths"
    )

    # Recommendations
    recommendations: list[str] = Field(
        default_factory=list, description="Model's recommendations"
    )
    required_changes: list[str] = Field(
        default_factory=list, description="Required changes for approval"
    )

    # Execution metadata
    execution_time_ms: float = Field(
        default=0.0, description="Analysis execution time", ge=0.0
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Vote timestamp"
    )

    # Additional metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional vote metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model_type": "codestral",
                "model_version": "22b-v0.1-q4_K_M",
                "decision": "approve",
                "confidence": 0.92,
                "score": 0.95,
                "reasoning": "Code follows ONEX patterns with minor issues",
                "key_findings": [
                    "Correct node type suffix usage",
                    "Proper contract implementation",
                ],
                "recommendations": ["Add more comprehensive error handling"],
            }
        }
    )


class ModelConsensusResult(BaseModel):
    """
    Multi-model consensus validation result.

    Aggregates votes from multiple AI models to provide consensus-based
    validation with detailed analysis and recommendations.
    """

    # Consensus identification
    consensus_id: UUID = Field(
        default_factory=uuid4, description="Unique consensus identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Consensus timestamp"
    )
    version: str = Field(default="1.0.0", description="Consensus format version")

    # Validation context
    code_path: str = Field(..., description="Code path validated")
    decision_type: str = Field(
        ..., description="Type of decision (architecture, code_change, etc.)"
    )
    validation_scope: str = Field(
        ..., description="Scope of validation (file, module, project)"
    )

    # Model votes
    votes: list[ModelModelVote] = Field(..., description="Individual model votes")
    total_models: int = Field(..., description="Total models consulted", ge=1)
    models_voted: int = Field(..., description="Models that provided votes", ge=0)

    # Consensus results
    consensus_reached: bool = Field(..., description="Whether consensus was reached")
    consensus_decision: EnumConsensusDecision = Field(
        ..., description="Final consensus decision"
    )
    consensus_confidence: float = Field(
        ..., description="Consensus confidence (0.0-1.0)", ge=0.0, le=1.0
    )
    agreement_percentage: float = Field(
        ..., description="Percentage of models in agreement", ge=0.0, le=100.0
    )

    # Consensus threshold
    required_agreement: float = Field(
        default=0.67,
        description="Required agreement threshold (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    threshold_met: bool = Field(..., description="Whether threshold was met")

    # Aggregated analysis
    average_score: float = Field(
        ..., description="Average quality score (0.0-1.0)", ge=0.0, le=1.0
    )
    score_variance: float = Field(default=0.0, description="Variance in scores", ge=0.0)
    common_findings: list[str] = Field(
        default_factory=list, description="Findings mentioned by multiple models"
    )
    common_concerns: list[str] = Field(
        default_factory=list, description="Concerns mentioned by multiple models"
    )
    common_recommendations: list[str] = Field(
        default_factory=list, description="Recommendations from multiple models"
    )

    # Execution metadata
    total_execution_time_ms: float = Field(
        default=0.0, description="Total consensus execution time", ge=0.0
    )
    parallel_execution: bool = Field(
        default=True, description="Whether models ran in parallel"
    )

    # Additional metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional consensus metadata"
    )

    def get_approved_votes(self) -> list[ModelModelVote]:
        """Get all votes with APPROVE decision."""
        return [
            vote
            for vote in self.votes
            if vote.decision == EnumConsensusDecision.APPROVE
        ]

    def get_rejected_votes(self) -> list[ModelModelVote]:
        """Get all votes with REJECT decision."""
        return [
            vote for vote in self.votes if vote.decision == EnumConsensusDecision.REJECT
        ]

    def get_revision_votes(self) -> list[ModelModelVote]:
        """Get all votes with NEEDS_REVISION decision."""
        return [
            vote
            for vote in self.votes
            if vote.decision == EnumConsensusDecision.NEEDS_REVISION
        ]

    def calculate_consensus(self) -> None:
        """Calculate consensus from votes."""
        if not self.votes:
            self.consensus_reached = False
            self.threshold_met = False
            return

        # Count decisions
        decision_counts: dict[EnumConsensusDecision, int] = {}
        for vote in self.votes:
            decision_counts[vote.decision] = decision_counts.get(vote.decision, 0) + 1

        # Find majority decision
        max_count = max(decision_counts.values())
        majority_decision = [
            decision
            for decision, count in decision_counts.items()
            if count == max_count
        ][0]

        # Calculate agreement
        self.agreement_percentage = (max_count / len(self.votes)) * 100
        self.threshold_met = self.agreement_percentage >= (
            self.required_agreement * 100
        )
        self.consensus_reached = self.threshold_met
        self.consensus_decision = majority_decision

        # Calculate average confidence
        total_confidence = sum(vote.confidence for vote in self.votes)
        self.consensus_confidence = total_confidence / len(self.votes)

        # Calculate average score
        total_score = sum(vote.score for vote in self.votes)
        self.average_score = total_score / len(self.votes)

        # Calculate variance
        mean_score = self.average_score
        variance = sum((vote.score - mean_score) ** 2 for vote in self.votes) / len(
            self.votes
        )
        self.score_variance = variance

    def to_dict(self) -> dict[str, Any]:
        """Convert consensus result to dictionary."""
        return self.model_dump(mode="python")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code_path": "src/validators/node_validator_compute.py",
                "decision_type": "architecture",
                "consensus_reached": True,
                "consensus_decision": "approve",
                "agreement_percentage": 100.0,
                "average_score": 0.94,
                "total_models": 3,
                "models_voted": 3,
            }
        }
    )
