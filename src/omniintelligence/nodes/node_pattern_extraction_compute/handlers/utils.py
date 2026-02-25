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

__all__ = ["get_extension"]


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
