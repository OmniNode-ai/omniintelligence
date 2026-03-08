# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""StrEnum for semantic analysis domains.

Replaces stringly-typed domain keys in ``DOMAIN_KEYWORDS`` and
``DOMAIN_TO_INTENT_MAP`` (handler_langextract.py) with a type-safe StrEnum.
Values match the canonical lowercase string keys so existing dict lookups
and serialization continue to work unchanged.

Reference: OMN-1481
"""

from __future__ import annotations

from enum import StrEnum


class EnumSemanticDomain(StrEnum):
    """Semantic analysis domain indicators.

    These domains are detected via keyword matching in ``handler_langextract.py``
    and mapped to intent boosts via ``DOMAIN_TO_INTENT_MAP``.
    """

    API_DESIGN = "api_design"
    CODE_GENERATION = "code_generation"
    TESTING = "testing"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    DATABASE = "database"
    DEVOPS = "devops"
    SECURITY = "security"
    ANALYSIS = "analysis"
    PATTERN_LEARNING = "pattern_learning"
    QUALITY_ASSESSMENT = "quality_assessment"
    SEMANTIC_ANALYSIS = "semantic_analysis"


__all__ = ["EnumSemanticDomain"]
