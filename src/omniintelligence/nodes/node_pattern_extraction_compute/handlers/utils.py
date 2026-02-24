# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Shared utility functions for pattern extraction handlers.

This module provides common utility functions used across multiple
pattern extraction handlers, following DRY principles.

ONEX Compliance:
    - Pure functional design (no side effects)
    - Deterministic results for same inputs
    - No external service calls or I/O operations
"""

from __future__ import annotations

__all__ = ["get_extension", "normalize_path"]


def normalize_path(file_path: str) -> str:
    """Normalize path separators to forward slashes for cross-platform compatibility.

    Replaces backslash separators (Windows-style) with forward slashes so that
    all downstream path comparisons and prefix operations work uniformly
    regardless of the platform that produced the session data.

    This is the canonical path normalization utility for all pattern extraction
    handlers. Any handler that touches file paths should call this function
    before performing directory splitting, prefix matching, or equality checks.

    Args:
        file_path: File path string, potentially containing backslash separators.

    Returns:
        Path string with all backslashes replaced by forward slashes.
        Empty string is returned unchanged.

    Examples:
        >>> normalize_path("src/api/routes.py")
        'src/api/routes.py'
        >>> normalize_path("src\\\\api\\\\routes.py")
        'src/api/routes.py'
        >>> normalize_path("")
        ''
        >>> normalize_path("C:\\\\Users\\\\dev\\\\project\\\\file.py")
        'C:/Users/dev/project/file.py'
    """
    return file_path.replace("\\", "/")


def get_extension(file_path: str) -> str:
    """Extract file extension from path.

    Returns the extension including the leading dot (e.g., '.py')
    or empty string if no extension found.

    Args:
        file_path: File path to extract extension from.

    Returns:
        File extension with leading dot, or empty string.

    Examples:
        >>> get_extension("/path/to/file.py")
        '.py'
        >>> get_extension("README")
        ''
        >>> get_extension("config.settings.yaml")
        '.yaml'
    """
    if "." in file_path:
        return "." + file_path.rsplit(".", 1)[-1]
    return ""
