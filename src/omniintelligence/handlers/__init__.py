# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handlers for omniintelligence operations.

Handlers are stateless functions that perform specific operations
on intelligence data, such as pattern compilation and validation.
"""

from omniintelligence.handlers.handler_compile_pattern import (
    COMPILER_VERSION,
    CompilationResult,
    compile_pattern,
    format_pattern_snippet,
)

__all__ = [
    "COMPILER_VERSION",
    "CompilationResult",
    "compile_pattern",
    "format_pattern_snippet",
]
