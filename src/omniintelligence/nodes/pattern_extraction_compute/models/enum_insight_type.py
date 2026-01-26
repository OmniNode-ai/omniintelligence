"""Insight type enumeration for pattern extraction.

This module defines the types of insights that can be extracted from
codebase analysis and session traces.
"""

from __future__ import annotations

from enum import Enum


class EnumInsightType(str, Enum):
    """Types of codebase insights that can be extracted.

    Each insight type represents a different pattern category
    discovered through codebase and session analysis.

    Attributes:
        FILE_ACCESS_PATTERN: Recurring file access sequences.
        ERROR_PATTERN: Common error conditions and their contexts.
        ARCHITECTURE_PATTERN: Structural patterns in code organization.
        TOOL_USAGE_PATTERN: Patterns in tool/command usage.
        ENTRY_POINT_PATTERN: Common entry points for operations.
        MODIFICATION_CLUSTER: Files frequently modified together.
    """

    FILE_ACCESS_PATTERN = "file_access_pattern"
    ERROR_PATTERN = "error_pattern"
    ARCHITECTURE_PATTERN = "architecture_pattern"
    TOOL_USAGE_PATTERN = "tool_usage_pattern"
    ENTRY_POINT_PATTERN = "entry_point_pattern"
    MODIFICATION_CLUSTER = "modification_cluster"


__all__ = ["EnumInsightType"]
