"""
Quality Analysis Integration - Integrate with code quality tools.

Provides integration adapters for:
- agent-code-quality-analyzer
- mcp__zen__codereview
- mcp__zen__consensus

These integrations enable comprehensive quality assessment and
multi-model validation for compliance reporting.
"""

from uuid import UUID, uuid4

from src.archon_services.pattern_learning.phase3_validation.reporting.integration.quality_analyzer_integration import (
    QualityAnalyzerIntegration,
)

__all__ = ["QualityAnalyzerIntegration"]
