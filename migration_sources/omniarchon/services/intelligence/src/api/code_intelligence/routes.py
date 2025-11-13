"""
Code Intelligence API Routes

FastAPI router for code analysis metrics and insights.
"""

import logging

from fastapi import APIRouter
from src.api.code_intelligence.models import CodeAnalysisResponse
from src.api.code_intelligence.service import CodeIntelligenceService
from src.api.utils import api_error_handler

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/intelligence/code", tags=["Code Intelligence"])

# Initialize service (will be used by all endpoints)
code_intelligence_service = CodeIntelligenceService()


@router.get(
    "/analysis",
    response_model=CodeAnalysisResponse,
    summary="Get Code Analysis Metrics",
    description=(
        "Get aggregated code analysis metrics from pattern and quality data. "
        "Provides insights into code complexity, quality issues, and security concerns."
    ),
)
@api_error_handler("get_code_analysis")
async def get_code_analysis():
    """
    Get code analysis metrics.

    Returns aggregated metrics including:
    - files_analyzed: Total number of code files analyzed
    - avg_complexity: Average cyclomatic complexity
    - code_smells: Number of detected code quality issues
    - security_issues: Number of detected security issues

    **Response:**
    - files_analyzed: Total patterns (representing analyzed files)
    - avg_complexity: Average complexity score
    - code_smells: Low-quality patterns count
    - security_issues: Security-related patterns count
    """
    result = await code_intelligence_service.get_code_analysis()

    logger.info(f"Code analysis metrics retrieved | files={result['files_analyzed']}")

    return CodeAnalysisResponse(**result)
