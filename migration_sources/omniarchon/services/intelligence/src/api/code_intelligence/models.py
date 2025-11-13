"""
Pydantic models for Code Intelligence API

Response models for code analysis metrics and insights.
"""

from pydantic import BaseModel, Field


class CodeAnalysisResponse(BaseModel):
    """Response model for GET /api/intelligence/code/analysis"""

    files_analyzed: int = Field(
        ..., ge=0, description="Total number of code files analyzed"
    )
    avg_complexity: float = Field(
        ...,
        ge=0.0,
        description="Average cyclomatic complexity score across all patterns",
    )
    code_smells: int = Field(
        ..., ge=0, description="Number of detected code smells (low quality patterns)"
    )
    security_issues: int = Field(
        ..., ge=0, description="Number of detected security-related issues"
    )
