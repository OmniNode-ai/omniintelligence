"""Operation metadata model for canary impure tool."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ModelOperationMetadata(BaseModel):
    """Model for operation metadata in side effect operations."""

    operation_id: str = Field(description="Unique identifier for the operation")
    user_agent: Optional[str] = Field(
        default=None, description="User agent performing the operation"
    )
    source_ip: Optional[str] = Field(default=None, description="Source IP address")
    target_resource: Optional[str] = Field(
        default=None, description="Target resource being accessed"
    )
    security_context: str = Field(description="Security context for the operation")
    risk_level: str = Field(description="Risk level assessment for the operation")
    required_permissions: List[str] = Field(
        default_factory=list, description="Required permissions"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "operation_id": "op_123456",
                    "user_agent": "ONEX Canary Tool/1.0.0",
                    "source_ip": "127.0.0.1",
                    "target_resource": "/tmp/test_file.txt",
                    "security_context": "system",
                    "risk_level": "low",
                    "required_permissions": ["file_write", "file_read"],
                }
            ]
        }
