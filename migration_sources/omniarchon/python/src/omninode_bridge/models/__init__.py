"""
OmniNode Bridge Models

API contract models for external service integrations.
"""

from omninode_bridge.models.model_intelligence_api_contracts import (  # Request Models; Response Models; Supporting Models; Enums
    ArchitecturalCompliance,
    ArchitecturalComplianceDetails,
    ArchitecturalEra,
    BaselineMetrics,
    DetectedPattern,
    MaintainabilityMetrics,
    ModelErrorResponse,
    ModelHealthCheckResponse,
    ModelPatternDetectionRequest,
    ModelPatternDetectionResponse,
    ModelPerformanceAnalysisRequest,
    ModelPerformanceAnalysisResponse,
    ModelQualityAssessmentRequest,
    ModelQualityAssessmentResponse,
    OnexComplianceDetails,
    OptimizationOpportunity,
    PatternCategory,
    ValidationStatus,
)

__all__ = [
    # Request Models
    "ModelQualityAssessmentRequest",
    "ModelPerformanceAnalysisRequest",
    "ModelPatternDetectionRequest",
    # Response Models
    "ModelQualityAssessmentResponse",
    "ModelPerformanceAnalysisResponse",
    "ModelPatternDetectionResponse",
    "ModelHealthCheckResponse",
    "ModelErrorResponse",
    # Supporting Models
    "ArchitecturalCompliance",
    "MaintainabilityMetrics",
    "OnexComplianceDetails",
    "BaselineMetrics",
    "OptimizationOpportunity",
    "DetectedPattern",
    "ArchitecturalComplianceDetails",
    # Enums
    "ArchitecturalEra",
    "ValidationStatus",
    "PatternCategory",
]
