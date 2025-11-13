"""Operation parameters model for canary impure tool."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ModelOperationParameters(BaseModel):
    """Model for operation parameters in side effect operations."""

    operation_type: str = Field(description="Type of operation being performed")
    target_path: Optional[str] = Field(
        default=None, description="Target file or resource path"
    )
    content: Optional[str] = Field(
        default=None, description="Content to write or process"
    )
    method: Optional[str] = Field(
        default=None, description="HTTP method for network operations"
    )
    url: Optional[str] = Field(default=None, description="URL for network operations")
    timeout_seconds: Optional[int] = Field(
        default=30, description="Operation timeout in seconds"
    )
    retry_count: Optional[int] = Field(
        default=0, description="Number of retries to attempt"
    )
    parameters: List[str] = Field(
        default_factory=list, description="Additional operation parameters"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "operation_type": "file_write",
                    "target_path": "/tmp/test_file.txt",
                    "content": "Hello World",
                    "timeout_seconds": 30,
                    "retry_count": 3,
                    "parameters": ["create_backup", "verify_write"],
                }
            ]
        }
