#!/usr/bin/env python3
"""
ONEX Canary Impure Tool Output State Model

Model for output state of the Tier 3 Impure/Side Effect canary tool, demonstrating
comprehensive side effect tracking with full security and audit metadata.
"""

from typing import Optional

from omnibase.model.core.model_onex_output_state import ModelOnexOutputState
from pydantic import BaseModel, Field

from .model_audit_metadata import ModelAuditMetadata
from .model_http_headers import ModelHttpHeaders
from .model_output_field import ModelOutputField


class ModelSideEffectResult(BaseModel):
    """Results of side effect operations."""

    operation_performed: str = Field(
        description="Name of side effect operation that was performed"
    )
    operation_successful: bool = Field(
        description="Whether the side effect operation was successful"
    )
    operation_time_ms: float = Field(
        description="Time taken for operation in milliseconds"
    )
    side_effects_created: list[str] = Field(
        default_factory=list, description="List of side effects that were created"
    )
    rollback_possible: bool = Field(
        description="Whether the side effects can be rolled back"
    )
    rollback_instructions: Optional[str] = Field(
        default=None, description="Instructions for rolling back side effects"
    )


class ModelFileOperationResult(BaseModel):
    """Results of file operations."""

    file_path: str = Field(description="Path of file that was operated on")
    file_size_bytes: Optional[int] = Field(
        default=None, description="Size of file in bytes"
    )
    file_exists: bool = Field(description="Whether file exists after operation")
    file_permissions: Optional[str] = Field(
        default=None, description="File permissions"
    )
    file_content_preview: Optional[str] = Field(
        default=None, description="Preview of file content (first 100 chars)"
    )


class ModelHttpRequestResult(BaseModel):
    """Results of HTTP requests."""

    status_code: int = Field(description="HTTP response status code")
    response_headers: ModelHttpHeaders = Field(
        default_factory=ModelHttpHeaders, description="HTTP response headers"
    )
    response_body: Optional[str] = Field(
        default=None, description="HTTP response body (truncated if large)"
    )
    response_size_bytes: int = Field(description="Size of HTTP response in bytes")
    request_duration_ms: float = Field(
        description="Duration of HTTP request in milliseconds"
    )


class ModelAuditResult(BaseModel):
    """Results of audit operations."""

    audit_id: str = Field(description="Unique identifier for audit entry")
    audit_timestamp: str = Field(description="Timestamp when audit was created")
    audit_level: str = Field(
        description="Audit log level", pattern="^(INFO|WARN|ERROR|CRITICAL)$"
    )
    audit_message: str = Field(description="Audit message that was logged")
    audit_metadata: ModelAuditMetadata = Field(
        default_factory=ModelAuditMetadata, description="Additional audit metadata"
    )


class ModelSecurityAssessment(BaseModel):
    """Security assessment results."""

    sandbox_active: bool = Field(description="Whether sandbox mode was active")
    security_violations: list[str] = Field(
        default_factory=list, description="Any security violations detected"
    )
    risk_level: str = Field(
        description="Assessed risk level of operation",
        pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$",
    )
    mitigation_applied: list[str] = Field(
        default_factory=list, description="Security mitigations that were applied"
    )


class ModelCanaryImpureOutputState(ModelOnexOutputState):
    """Output state for Tier 3 Impure/Side Effect canary tool operations."""

    # Side effect results
    side_effect_result: Optional[ModelSideEffectResult] = Field(
        default=None, description="Results of side effect operation"
    )

    # File operation results
    file_operation_result: Optional[ModelFileOperationResult] = Field(
        default=None, description="Results of file operations"
    )

    # HTTP request results
    http_request_result: Optional[ModelHttpRequestResult] = Field(
        default=None, description="Results of HTTP requests"
    )

    # Audit results
    audit_result: Optional[ModelAuditResult] = Field(
        default=None, description="Results of audit operations"
    )

    # Security results
    security_assessment: Optional[ModelSecurityAssessment] = Field(
        default=None, description="Security assessment results"
    )

    # Output field passthrough
    output_field: Optional[ModelOutputField] = Field(
        default=None, description="Dynamic output field for computed results"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "File write operation completed successfully",
                "exit_code": 0,
                "side_effect_result": {
                    "operation_performed": "file_write",
                    "operation_successful": True,
                    "operation_time_ms": 2.5,
                    "side_effects_created": ["/tmp/canary_output.txt created"],
                    "rollback_possible": True,
                    "rollback_instructions": "Delete file: rm /tmp/canary_output.txt",
                },
                "file_operation_result": {
                    "file_path": "/tmp/canary_output.txt",
                    "file_size_bytes": 32,
                    "file_exists": True,
                    "file_permissions": "rw-r--r--",
                    "file_content_preview": "Hello from canary impure tool",
                },
                "security_assessment": {
                    "sandbox_active": True,
                    "security_violations": [],
                    "risk_level": "LOW",
                    "mitigation_applied": ["sandbox_restriction", "path_validation"],
                },
            }
        }
