"""Audit entry model for canary impure tool."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ModelAuditEntry(BaseModel):
    """Model for audit log entries in the canary impure tool."""

    timestamp: datetime = Field(description="When the audit entry was created")
    operation: str = Field(description="Type of operation being audited")
    correlation_id: str = Field(description="Correlation ID for tracing")
    user_id: Optional[str] = Field(
        default=None, description="User performing the operation"
    )
    resource_path: Optional[str] = Field(
        default=None, description="Resource being accessed"
    )
    operation_status: str = Field(
        description="Status of the operation (success/failure)"
    )
    details: Optional[str] = Field(
        default=None, description="Additional operation details"
    )
    security_level: str = Field(description="Security classification of the operation")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "timestamp": "2025-07-29T12:00:00Z",
                    "operation": "file_write",
                    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "user_id": "system",
                    "resource_path": "/tmp/test_file.txt",
                    "operation_status": "success",
                    "details": "File written successfully with 1024 bytes",
                    "security_level": "standard",
                }
            ]
        }
