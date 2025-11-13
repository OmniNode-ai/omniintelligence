"""
Compliance Reporting Models - Data structures for validation results.

Provides comprehensive data models for compliance reports, gate results,
consensus validation, and quality assessments.
"""

from uuid import UUID, uuid4

from src.archon_services.pattern_learning.phase3_validation.reporting.models.model_compliance_report import (
    ModelComplianceReport,
    ModelGateResult,
    ModelIssue,
    ModelRecommendation,
)
from src.archon_services.pattern_learning.phase3_validation.reporting.models.model_consensus_result import (
    ModelConsensusResult,
    ModelModelVote,
)

__all__ = [
    "ModelComplianceReport",
    "ModelGateResult",
    "ModelIssue",
    "ModelRecommendation",
    "ModelConsensusResult",
    "ModelModelVote",
]
