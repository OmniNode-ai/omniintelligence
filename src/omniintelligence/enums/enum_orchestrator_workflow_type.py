# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Orchestrator workflow type enum for high-level intelligence operations."""

from enum import Enum


class EnumOrchestratorWorkflowType(str, Enum):
    """Orchestrator workflow types for high-level intelligence operations.

    This enum defines the workflow types used by the intelligence orchestrator
    to coordinate multi-step intelligence operations.
    """

    DOCUMENT_INGESTION = "DOCUMENT_INGESTION"
    PATTERN_LEARNING = "PATTERN_LEARNING"
    QUALITY_ASSESSMENT = "QUALITY_ASSESSMENT"
    SEMANTIC_ANALYSIS = "SEMANTIC_ANALYSIS"
    RELATIONSHIP_DETECTION = "RELATIONSHIP_DETECTION"


__all__ = ["EnumOrchestratorWorkflowType"]
