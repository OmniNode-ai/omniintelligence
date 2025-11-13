"""Audit metadata model for canary impure tool output state."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ModelAuditMetadata(BaseModel):
    """Model for audit metadata in output state."""

    audit_id: str = Field(description="Unique identifier for the audit record")
    operation_summary: str = Field(description="Summary of the audited operation")
    security_classification: str = Field(
        description="Security classification of the operation"
    )
    compliance_status: str = Field(description="Compliance status of the operation")
    risk_assessment: str = Field(description="Risk assessment result")
    mitigation_actions: List[str] = Field(
        default_factory=list, description="Applied mitigation actions"
    )
    reviewer: Optional[str] = Field(
        default=None, description="Security reviewer if applicable"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "audit_id": "audit_123456",
                    "operation_summary": "File write operation to sandboxed location",
                    "security_classification": "standard",
                    "compliance_status": "compliant",
                    "risk_assessment": "low",
                    "mitigation_actions": ["sandbox_enforcement", "path_validation"],
                    "reviewer": "system_auditor",
                }
            ]
        }
