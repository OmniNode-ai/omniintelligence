"""
Pydantic Models for Track 3 Autonomous Execution APIs

Complete type definitions for agent prediction, time estimation,
safety scoring, and pattern management for Track 4 Autonomous System.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Enums
# ============================================================================


# NOTE: correlation_id support enabled for tracing
class TaskComplexity(str, Enum):
    """Task complexity levels"""

    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"


class ChangeScope(str, Enum):
    """Scope of changes for a task"""

    SINGLE_FILE = "single_file"
    MULTIPLE_FILES = "multiple_files"
    MODULE = "module"
    SERVICE = "service"
    SYSTEM_WIDE = "system_wide"


class TaskType(str, Enum):
    """Types of tasks"""

    CODE_GENERATION = "code_generation"
    CODE_MODIFICATION = "code_modification"
    BUG_FIX = "bug_fix"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    DEBUGGING = "debugging"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    SECURITY = "security"


class ConfidenceLevel(str, Enum):
    """Confidence levels for predictions"""

    VERY_LOW = "very_low"  # <0.3
    LOW = "low"  # 0.3-0.5
    MEDIUM = "medium"  # 0.5-0.7
    HIGH = "high"  # 0.7-0.9
    VERY_HIGH = "very_high"  # >0.9


class SafetyRating(str, Enum):
    """Safety ratings for autonomous execution"""

    SAFE = "safe"  # >0.8 - Can execute autonomously
    CAUTION = "caution"  # 0.6-0.8 - Requires review
    UNSAFE = "unsafe"  # <0.6 - Human intervention required


# ============================================================================
# Request Models
# ============================================================================


class TaskCharacteristics(BaseModel):
    """
    Comprehensive task characteristics for agent prediction and time estimation.

    Used by Track 4 Autonomous System to request predictions about optimal
    agent selection, execution time, and safety assessments.
    """

    task_description: str = Field(
        ..., description="Natural language description of the task", min_length=10
    )

    task_type: TaskType = Field(..., description="Type/category of the task")

    complexity: TaskComplexity = Field(
        default=TaskComplexity.MODERATE,
        description="Estimated complexity level of the task",
    )

    change_scope: ChangeScope = Field(
        default=ChangeScope.MULTIPLE_FILES,
        description="Expected scope of changes required",
    )

    estimated_files_affected: Optional[int] = Field(
        default=None, description="Number of files expected to be modified", ge=0
    )

    requires_testing: bool = Field(
        default=True, description="Whether the task requires test execution"
    )

    requires_validation: bool = Field(
        default=True, description="Whether the task requires validation steps"
    )

    project_id: Optional[str] = Field(
        default=None, description="Associated project identifier"
    )

    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context (file paths, dependencies, constraints)",
    )

    historical_similar_tasks: Optional[List[str]] = Field(
        default=None, description="UUIDs of similar tasks previously executed"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_description": "Implement OAuth2 authentication with Google provider",
                "task_type": "code_generation",
                "complexity": "complex",
                "change_scope": "module",
                "estimated_files_affected": 5,
                "requires_testing": True,
                "requires_validation": True,
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "context": {
                    "framework": "FastAPI",
                    "language": "python",
                    "dependencies": ["authlib", "pydantic"],
                },
            }
        }
    )


class AgentOption(BaseModel):
    """Alternative agent option with reasoning"""

    agent_name: str = Field(..., description="Agent identifier")
    confidence: float = Field(..., description="Confidence score 0.0-1.0", ge=0, le=1)
    reasoning: str = Field(..., description="Why this agent is suitable")
    estimated_success_rate: float = Field(
        ..., description="Historical success rate for similar tasks", ge=0, le=1
    )


class AgentPrediction(BaseModel):
    """
    Agent prediction response with primary recommendation and alternatives.

    Provides intelligent agent selection based on task characteristics,
    historical performance, and capability matching.
    """

    recommended_agent: str = Field(
        ..., description="Primary recommended agent for the task"
    )

    confidence_score: float = Field(
        ..., description="Confidence in recommendation (0.0-1.0)", ge=0, le=1
    )

    confidence_level: ConfidenceLevel = Field(
        ..., description="Human-readable confidence level"
    )

    reasoning: str = Field(..., description="Detailed reasoning for agent selection")

    alternative_agents: List[AgentOption] = Field(
        default_factory=list,
        description="Alternative agent options ranked by confidence",
    )

    expected_success_rate: float = Field(
        ...,
        description="Historical success rate for this agent on similar tasks",
        ge=0,
        le=1,
    )

    capability_match_score: float = Field(
        ...,
        description="How well agent capabilities match task requirements",
        ge=0,
        le=1,
    )

    historical_data_points: int = Field(
        default=0, description="Number of historical executions used for prediction"
    )

    prediction_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional prediction metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recommended_agent": "agent-api-architect",
                "confidence_score": 0.87,
                "confidence_level": "high",
                "reasoning": "Agent has 92% success rate on OAuth2 implementations with FastAPI",
                "alternative_agents": [
                    {
                        "agent_name": "agent-code-quality-analyzer",
                        "confidence": 0.73,
                        "reasoning": "Can assist with OAuth2 code quality verification",
                        "estimated_success_rate": 0.85,
                    }
                ],
                "expected_success_rate": 0.92,
                "capability_match_score": 0.94,
                "historical_data_points": 47,
                "prediction_metadata": {
                    "similar_tasks_found": 12,
                    "average_duration_ms": 285000,
                    "common_patterns_used": ["oauth2_pkce", "token_refresh"],
                },
            }
        }
    )


class TimeBreakdown(BaseModel):
    """Detailed time breakdown for task execution"""

    planning_ms: int = Field(default=0, description="Estimated planning/analysis time")
    implementation_ms: int = Field(default=0, description="Core implementation time")
    testing_ms: int = Field(default=0, description="Testing and validation time")
    review_ms: int = Field(default=0, description="Code review time")
    overhead_ms: int = Field(default=0, description="System overhead and coordination")


class TimeEstimate(BaseModel):
    """
    Time estimation response with percentile-based predictions.

    Provides realistic time estimates based on historical execution data,
    including best-case, typical, and worst-case scenarios.
    """

    estimated_duration_ms: int = Field(
        ..., description="P50 (median) estimated duration in milliseconds"
    )

    p25_duration_ms: int = Field(..., description="P25 (optimistic) estimated duration")

    p75_duration_ms: int = Field(
        ..., description="P75 (pessimistic) estimated duration"
    )

    p95_duration_ms: int = Field(..., description="P95 (worst-case) estimated duration")

    confidence_score: float = Field(
        ..., description="Confidence in estimate (0.0-1.0)", ge=0, le=1
    )

    time_breakdown: TimeBreakdown = Field(
        ..., description="Detailed breakdown of estimated time"
    )

    historical_variance: float = Field(
        ...,
        description="Historical variance in execution time (standard deviation)",
        ge=0,
    )

    factors_affecting_time: List[str] = Field(
        default_factory=list,
        description="Key factors that may affect execution time",
    )

    similar_tasks_analyzed: int = Field(
        default=0, description="Number of similar historical tasks used for estimation"
    )

    estimation_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional estimation metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "estimated_duration_ms": 285000,
                "p25_duration_ms": 180000,
                "p75_duration_ms": 420000,
                "p95_duration_ms": 650000,
                "confidence_score": 0.82,
                "time_breakdown": {
                    "planning_ms": 45000,
                    "implementation_ms": 180000,
                    "testing_ms": 40000,
                    "review_ms": 15000,
                    "overhead_ms": 5000,
                },
                "historical_variance": 95000,
                "factors_affecting_time": [
                    "complexity_of_oauth2_provider_integration",
                    "test_coverage_requirements",
                    "documentation_completeness",
                ],
                "similar_tasks_analyzed": 12,
            }
        }
    )


class RiskFactor(BaseModel):
    """Individual risk factor analysis"""

    factor: str = Field(..., description="Risk factor name")
    severity: str = Field(..., description="Severity level (low, medium, high)")
    likelihood: float = Field(
        ..., description="Likelihood of occurrence (0.0-1.0)", ge=0, le=1
    )
    mitigation: str = Field(..., description="Suggested mitigation strategy")


class SafetyScore(BaseModel):
    """
    Safety score assessment for autonomous execution.

    Determines whether a task is safe for autonomous execution or requires
    human oversight based on historical success rates, risk factors, and
    task characteristics.
    """

    safety_score: float = Field(
        ...,
        description="Overall safety score for autonomous execution (0.0-1.0)",
        ge=0,
        le=1,
    )

    safety_rating: SafetyRating = Field(..., description="Human-readable safety rating")

    can_execute_autonomously: bool = Field(
        ..., description="Whether autonomous execution is recommended"
    )

    requires_human_review: bool = Field(
        ..., description="Whether human review is required before execution"
    )

    historical_success_rate: float = Field(
        ...,
        description="Success rate for similar tasks with same agent",
        ge=0,
        le=1,
    )

    historical_failure_rate: float = Field(
        ...,
        description="Failure rate for similar tasks with same agent",
        ge=0,
        le=1,
    )

    risk_factors: List[RiskFactor] = Field(
        default_factory=list, description="Identified risk factors"
    )

    safety_checks_required: List[str] = Field(
        default_factory=list,
        description="Required safety checks before execution",
    )

    rollback_capability: bool = Field(
        default=True, description="Whether rollback is possible if execution fails"
    )

    impact_radius: str = Field(
        ...,
        description="Potential impact radius (isolated, module, service, system)",
    )

    confidence_in_assessment: float = Field(
        ..., description="Confidence in safety assessment (0.0-1.0)", ge=0, le=1
    )

    safety_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional safety assessment metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "safety_score": 0.78,
                "safety_rating": "caution",
                "can_execute_autonomously": True,
                "requires_human_review": True,
                "historical_success_rate": 0.88,
                "historical_failure_rate": 0.12,
                "risk_factors": [
                    {
                        "factor": "oauth2_security_complexity",
                        "severity": "medium",
                        "likelihood": 0.3,
                        "mitigation": "Automated security scanning before deployment",
                    },
                    {
                        "factor": "external_dependency_integration",
                        "severity": "low",
                        "likelihood": 0.15,
                        "mitigation": "Mock testing with provider sandbox",
                    },
                ],
                "safety_checks_required": [
                    "security_audit",
                    "test_coverage_threshold",
                    "integration_test_pass",
                ],
                "rollback_capability": True,
                "impact_radius": "module",
                "confidence_in_assessment": 0.85,
            }
        }
    )


class SuccessPattern(BaseModel):
    """
    Success pattern learned from historical executions.

    Represents a proven execution pattern with high success rate that can
    be replayed for similar tasks.
    """

    pattern_id: UUID = Field(default_factory=uuid4, description="Unique pattern ID")

    pattern_name: str = Field(..., description="Human-readable pattern name")

    pattern_hash: str = Field(
        ..., description="Hash of pattern characteristics for matching"
    )

    task_type: TaskType = Field(..., description="Type of task this pattern applies to")

    agent_sequence: List[str] = Field(
        ..., description="Sequence of agents used in this pattern"
    )

    success_count: int = Field(default=0, description="Number of successful executions")

    failure_count: int = Field(default=0, description="Number of failed executions")

    success_rate: float = Field(
        ..., description="Success rate for this pattern (0.0-1.0)", ge=0, le=1
    )

    average_duration_ms: int = Field(
        default=0, description="Average execution duration in milliseconds"
    )

    confidence_score: float = Field(
        ..., description="Confidence in pattern reliability (0.0-1.0)", ge=0, le=1
    )

    prerequisites: List[str] = Field(
        default_factory=list, description="Prerequisites for using this pattern"
    )

    constraints: List[str] = Field(
        default_factory=list, description="Constraints or limitations of this pattern"
    )

    best_practices: List[str] = Field(
        default_factory=list, description="Best practices when using this pattern"
    )

    example_tasks: List[str] = Field(
        default_factory=list,
        description="Example task descriptions where pattern succeeded",
    )

    last_used_at: Optional[datetime] = Field(
        default=None, description="Timestamp of last successful use"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Pattern creation timestamp",
    )

    pattern_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional pattern metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_name": "oauth2_fastapi_implementation",
                "pattern_hash": "a8f7e3d2c1b0",
                "task_type": "code_generation",
                "agent_sequence": [
                    "agent-api-architect",
                    "agent-testing",
                    "agent-security-audit",
                ],
                "success_count": 24,
                "failure_count": 2,
                "success_rate": 0.923,
                "average_duration_ms": 285000,
                "confidence_score": 0.91,
                "prerequisites": [
                    "FastAPI framework installed",
                    "OAuth2 provider credentials configured",
                ],
                "constraints": [
                    "Requires external OAuth2 provider access",
                    "Needs environment variables for secrets",
                ],
                "best_practices": [
                    "Use PKCE for enhanced security",
                    "Implement token refresh mechanism",
                    "Add comprehensive error handling",
                ],
                "example_tasks": [
                    "Implement Google OAuth2 login",
                    "Add GitHub OAuth2 authentication",
                ],
                "last_used_at": "2025-10-01T14:30:00Z",
            }
        }
    )


class ExecutionOutcome(BaseModel):
    """Outcome of a task execution for pattern learning"""

    success: bool = Field(..., description="Whether execution succeeded")
    duration_ms: int = Field(..., description="Total execution duration", ge=0)
    error_type: Optional[str] = Field(default=None, description="Error type if failed")
    error_message: Optional[str] = Field(
        default=None, description="Error message if failed"
    )
    quality_score: Optional[float] = Field(
        default=None, description="Quality score of result", ge=0, le=1
    )
    test_coverage: Optional[float] = Field(
        default=None, description="Test coverage achieved", ge=0, le=1
    )


class ExecutionDetails(BaseModel):
    """Details of task execution for pattern learning"""

    agent_used: str = Field(..., description="Agent that executed the task")
    start_time: datetime = Field(..., description="Execution start timestamp")
    end_time: datetime = Field(..., description="Execution end timestamp")
    steps_executed: List[str] = Field(
        default_factory=list, description="Execution steps performed"
    )
    files_modified: List[str] = Field(
        default_factory=list, description="Files that were modified"
    )
    commands_executed: List[str] = Field(
        default_factory=list, description="Commands executed during task"
    )
    tools_used: List[str] = Field(
        default_factory=list, description="Tools/APIs used during execution"
    )


class ExecutionPattern(BaseModel):
    """
    Complete execution pattern for ingestion into learning system.

    Contains all information needed to learn from a completed task execution
    and potentially create or update success patterns.
    """

    execution_id: UUID = Field(
        default_factory=uuid4, description="Unique execution identifier"
    )

    task_characteristics: TaskCharacteristics = Field(
        ..., description="Characteristics of the executed task"
    )

    execution_details: ExecutionDetails = Field(
        ..., description="Details of how task was executed"
    )

    outcome: ExecutionOutcome = Field(..., description="Execution outcome and metrics")

    learned_insights: Optional[List[str]] = Field(
        default=None, description="Insights learned from this execution"
    )

    pattern_contribution: Optional[str] = Field(
        default=None,
        description="How this execution contributes to pattern learning",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "execution_id": "660f9500-f3ac-42e5-b827-557766550111",
                "task_characteristics": {
                    "task_description": "Implement OAuth2 authentication with Google",
                    "task_type": "code_generation",
                    "complexity": "complex",
                    "change_scope": "module",
                },
                "execution_details": {
                    "agent_used": "agent-api-architect",
                    "start_time": "2025-10-01T10:00:00Z",
                    "end_time": "2025-10-01T10:15:30Z",
                    "steps_executed": [
                        "analyze_requirements",
                        "design_architecture",
                        "implement_oauth2_flow",
                        "write_tests",
                        "validate_security",
                    ],
                    "files_modified": [
                        "src/auth/oauth2.py",
                        "src/auth/providers/google.py",
                        "tests/test_oauth2.py",
                    ],
                },
                "outcome": {
                    "success": True,
                    "duration_ms": 930000,
                    "quality_score": 0.89,
                    "test_coverage": 0.92,
                },
            }
        }
    )


class PatternID(BaseModel):
    """Response for pattern ingestion containing pattern identifier"""

    pattern_id: UUID = Field(..., description="ID of created/updated pattern")
    pattern_name: str = Field(..., description="Name of the pattern")
    is_new_pattern: bool = Field(
        ..., description="Whether this created a new pattern or updated existing"
    )
    success_rate: float = Field(
        ..., description="Current success rate of the pattern", ge=0, le=1
    )
    total_executions: int = Field(
        default=0, description="Total executions contributing to this pattern"
    )
    confidence_score: float = Field(
        ..., description="Confidence in pattern reliability", ge=0, le=1
    )
    message: str = Field(..., description="Human-readable result message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_name": "oauth2_fastapi_implementation",
                "is_new_pattern": False,
                "success_rate": 0.923,
                "total_executions": 25,
                "confidence_score": 0.91,
                "message": "Pattern updated successfully with new execution data",
            }
        }
    )


class PatternQueryFilter(BaseModel):
    """Filter parameters for querying success patterns"""

    min_success_rate: float = Field(
        default=0.8, description="Minimum success rate", ge=0, le=1
    )
    task_type: Optional[TaskType] = Field(
        default=None, description="Filter by task type"
    )
    agent: Optional[str] = Field(default=None, description="Filter by agent used")
    limit: int = Field(
        default=20, description="Maximum patterns to return", ge=1, le=100
    )
    offset: int = Field(default=0, description="Pagination offset", ge=0)
