# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""StrEnum for TF-IDF intent categories.

Replaces stringly-typed intent category labels with a type-safe StrEnum.
Values are the canonical lowercase string keys used in INTENT_PATTERNS,
DOMAIN_KEYWORDS, and contract.yaml. Using StrEnum means enum members
serialize as plain strings (e.g., ``EnumIntentCategory.DEBUGGING == "debugging"``),
so existing dict lookups, JSON payloads, and test assertions work unchanged.

Reference: OMN-1481
"""

from __future__ import annotations

from enum import StrEnum


class EnumIntentCategory(StrEnum):
    """TF-IDF intent classification categories.

    The 15 categories used by the keyword-based TF-IDF classifier:
    6 original legacy categories, 3 intelligence-focused categories,
    5 domain-specific categories, and 1 fallback.
    """

    # Original 6 categories from legacy omniarchon
    CODE_GENERATION = "code_generation"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ANALYSIS = "analysis"

    # Intelligence-focused categories
    PATTERN_LEARNING = "pattern_learning"
    QUALITY_ASSESSMENT = "quality_assessment"
    SEMANTIC_ANALYSIS = "semantic_analysis"

    # Domain-specific categories
    API_DESIGN = "api_design"
    ARCHITECTURE = "architecture"
    DATABASE = "database"
    DEVOPS = "devops"
    SECURITY = "security"

    # Fallback
    UNKNOWN = "unknown"


__all__ = ["EnumIntentCategory"]
