"""
MCP API Pydantic Models

Data models for MCP server configuration, responses, and tool calls.
"""

from typing import Any

from pydantic import BaseModel


class ServerConfig(BaseModel):
    """MCP server configuration."""

    transport: str = "sse"
    host: str = "localhost"
    port: int = 8051


class ServerResponse(BaseModel):
    """MCP server operation response."""

    success: bool
    message: str
    status: str | None = None
    pid: int | None = None


class LogEntry(BaseModel):
    """MCP server log entry."""

    timestamp: str
    level: str
    message: str


class ToolCallRequest(BaseModel):
    """Request to call a tool on an MCP client."""

    client_id: str
    tool_name: str
    arguments: dict[str, Any]


# ============================================
# PYDANTIC VALIDATION MODELS FOR TOOL PARAMETERS
# ============================================


class ListTasksParams(BaseModel):
    """Parameters for list_tasks tool."""

    project_id: str | None = None
    filter_by: str | None = None
    filter_value: str | None = None


class CreateTaskParams(BaseModel):
    """Parameters for create_task tool."""

    project_id: str
    title: str
    description: str | None = None
    assignee: str | None = None

    @classmethod
    def model_validate(cls, obj: Any, **kwargs) -> "CreateTaskParams":
        """Validate with custom error handling."""
        validated = super().model_validate(obj, **kwargs)

        # Additional validation for non-empty strings
        if not validated.project_id or not validated.project_id.strip():
            raise ValueError("project_id cannot be empty")
        if not validated.title or not validated.title.strip():
            raise ValueError("title cannot be empty")

        return validated


class GetTaskParams(BaseModel):
    """Parameters for get_task tool."""

    task_id: str

    @classmethod
    def model_validate(cls, obj: Any, **kwargs) -> "GetTaskParams":
        """Validate with custom error handling."""
        validated = super().model_validate(obj, **kwargs)

        if not validated.task_id or not validated.task_id.strip():
            raise ValueError("task_id cannot be empty")

        return validated


class UpdateTaskParams(BaseModel):
    """Parameters for update_task tool."""

    task_id: str
    title: str | None = None
    status: str | None = None
    assignee: str | None = None

    @classmethod
    def model_validate(cls, obj: Any, **kwargs) -> "UpdateTaskParams":
        """Validate with custom error handling."""
        validated = super().model_validate(obj, **kwargs)

        if not validated.task_id or not validated.task_id.strip():
            raise ValueError("task_id cannot be empty")

        return validated


class ListProjectsParams(BaseModel):
    """Parameters for list_projects tool (no parameters required)."""

    pass
