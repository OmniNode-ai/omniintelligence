"""
Pydantic models for Intelligence Metrics API
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TimeWindow(str, Enum):
    """Time window options for metrics queries"""

    ONE_HOUR = "1h"
    TWENTY_FOUR_HOURS = "24h"
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"


class QualityImprovementData(BaseModel):
    """Single quality improvement data point"""

    timestamp: datetime = Field(
        ..., description="When the quality measurement was taken"
    )
    before_quality: float = Field(
        ...,
        description="Quality score before pattern application (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    after_quality: float = Field(
        ...,
        description="Quality score after pattern application (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    impact: float = Field(..., description="Quality improvement delta (after - before)")
    pattern_applied: Optional[str] = Field(
        None, description="Pattern name/ID that was applied"
    )
    pattern_id: Optional[str] = Field(None, description="UUID of the pattern")
    confidence: Optional[float] = Field(
        None, description="Confidence in the quality measurement", ge=0.0, le=1.0
    )


class QualityImpactResponse(BaseModel):
    """Response model for quality impact endpoint"""

    improvements: List[QualityImprovementData] = Field(
        ..., description="List of quality improvements over time"
    )
    total_improvements: int = Field(
        ..., description="Total number of improvement records"
    )
    avg_impact: float = Field(..., description="Average quality improvement")
    max_impact: float = Field(..., description="Maximum quality improvement observed")
    min_impact: float = Field(..., description="Minimum quality improvement observed")
    time_window: str = Field(
        ..., description="Time window for the data (1h, 24h, 7d, 30d)"
    )
    generated_at: datetime = Field(..., description="When this response was generated")


class OperationsPerMinuteResponse(BaseModel):
    """Response model for operations-per-minute endpoint"""

    timestamps: List[datetime] = Field(
        description="Timestamps for each data point (truncated to minute)"
    )
    operations: List[int] = Field(description="Number of operations for each timestamp")
    time_window: str = Field(description="Time window used for the query")
    total_operations: int = Field(description="Total operations in the time window")
    avg_operations_per_minute: float = Field(
        description="Average operations per minute"
    )
