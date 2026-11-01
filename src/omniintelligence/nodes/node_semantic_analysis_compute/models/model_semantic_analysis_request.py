# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for the pure AST semantic analysis handler."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelSemanticAnalysisRequest(BaseModel):
    """Source code and extraction options for semantic analysis.

    Attributes:
        content: Source code content to analyze.
        language: Programming language (e.g., "python"). Non-Python languages
            return a result with parse_ok=False.
        include_call_graph: Whether to extract function call relationships.
        include_import_graph: Whether to extract import relationships.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    content: str = Field(description="Source code content to analyze.")
    language: str = Field(default="python", description="Programming language.")
    include_call_graph: bool = Field(default=True)
    include_import_graph: bool = Field(default=True)


__all__ = ["ModelSemanticAnalysisRequest"]
