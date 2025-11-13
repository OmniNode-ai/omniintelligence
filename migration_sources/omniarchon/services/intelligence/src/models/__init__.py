"""
Data Models Module

Provides Pydantic models for all intelligence service operations.
Includes request/response models, validation logic, and type definitions.

Performance: Validation overhead <5ms per request
"""

from .file_location import (
    ErrorResponse,
    FileMatch,
    FileMetadata,
    FileSearchRequest,
    FileSearchResult,
    IndexingProgress,
    ProjectIndexRequest,
    ProjectIndexResult,
    ProjectIndexStatus,
    ProjectStatusRequest,
)

__all__ = [
    # Request models
    "ProjectIndexRequest",
    "FileSearchRequest",
    "ProjectStatusRequest",
    # Response models
    "FileSearchResult",
    "ProjectIndexResult",
    "ProjectIndexStatus",
    "ErrorResponse",
    # Result models
    "FileMatch",
    # Internal models
    "FileMetadata",
    "IndexingProgress",
]
