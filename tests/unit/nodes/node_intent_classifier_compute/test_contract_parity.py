# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Contract parity tests for intent classifier enums.

Ensures that EnumIntentCategory and EnumSemanticDomain stay in sync with the
INTENT_PATTERNS and DOMAIN_KEYWORDS dictionaries, and that the typed-class
mapping covers every intent category.

Reference: OMN-1481
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_intent_classification import (
    INTENT_PATTERNS,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_langextract import (
    DOMAIN_KEYWORDS,
    DOMAIN_TO_INTENT_MAP,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_typed_classification import (
    get_category_to_typed_class_mapping,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.enum_intent_category import (
    EnumIntentCategory,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.enum_semantic_domain import (
    EnumSemanticDomain,
)

# ---------------------------------------------------------------------------
# EnumIntentCategory <-> INTENT_PATTERNS parity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnumIntentCategoryParity:
    """Verify EnumIntentCategory stays in sync with INTENT_PATTERNS."""

    def test_every_pattern_key_is_an_enum_member(self) -> None:
        """Every key in INTENT_PATTERNS must be an EnumIntentCategory member."""
        pattern_keys = set(INTENT_PATTERNS.keys())
        enum_values = {
            m.value for m in EnumIntentCategory if m != EnumIntentCategory.UNKNOWN
        }

        missing_from_enum = {str(k) for k in pattern_keys} - enum_values
        assert not missing_from_enum, (
            f"INTENT_PATTERNS has keys not in EnumIntentCategory: {missing_from_enum}. "
            "Add them to EnumIntentCategory or remove from INTENT_PATTERNS."
        )

    def test_every_enum_member_except_unknown_has_a_pattern(self) -> None:
        """Every EnumIntentCategory (except UNKNOWN) must have a matching INTENT_PATTERNS entry."""
        enum_values = {
            m.value for m in EnumIntentCategory if m != EnumIntentCategory.UNKNOWN
        }
        pattern_keys = {str(k) for k in INTENT_PATTERNS}

        missing_from_patterns = enum_values - pattern_keys
        assert not missing_from_patterns, (
            f"EnumIntentCategory members without INTENT_PATTERNS entry: {missing_from_patterns}. "
            "Add patterns or remove the enum member."
        )

    def test_intent_patterns_values_are_frozenset(self) -> None:
        """All INTENT_PATTERNS values must be frozenset (immutable)."""
        for key, value in INTENT_PATTERNS.items():
            assert isinstance(value, frozenset), (
                f"INTENT_PATTERNS[{key!r}] is {type(value).__name__}, expected frozenset."
            )

    def test_intent_patterns_keys_are_enum_instances(self) -> None:
        """All INTENT_PATTERNS keys must be EnumIntentCategory instances."""
        for key in INTENT_PATTERNS:
            assert isinstance(key, EnumIntentCategory), (
                f"INTENT_PATTERNS key {key!r} is {type(key).__name__}, "
                "expected EnumIntentCategory."
            )


# ---------------------------------------------------------------------------
# EnumSemanticDomain <-> DOMAIN_KEYWORDS parity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnumSemanticDomainParity:
    """Verify EnumSemanticDomain stays in sync with DOMAIN_KEYWORDS."""

    def test_every_domain_key_is_an_enum_member(self) -> None:
        """Every key in DOMAIN_KEYWORDS must be an EnumSemanticDomain member."""
        domain_keys = {str(k) for k in DOMAIN_KEYWORDS}
        enum_values = {m.value for m in EnumSemanticDomain}

        missing_from_enum = domain_keys - enum_values
        assert not missing_from_enum, (
            f"DOMAIN_KEYWORDS has keys not in EnumSemanticDomain: {missing_from_enum}. "
            "Add them to EnumSemanticDomain or remove from DOMAIN_KEYWORDS."
        )

    def test_every_enum_member_has_a_domain_entry(self) -> None:
        """Every EnumSemanticDomain must have a matching DOMAIN_KEYWORDS entry."""
        enum_values = {m.value for m in EnumSemanticDomain}
        domain_keys = {str(k) for k in DOMAIN_KEYWORDS}

        missing_from_domains = enum_values - domain_keys
        assert not missing_from_domains, (
            f"EnumSemanticDomain members without DOMAIN_KEYWORDS entry: {missing_from_domains}. "
            "Add keywords or remove the enum member."
        )

    def test_domain_keywords_values_are_frozenset(self) -> None:
        """All DOMAIN_KEYWORDS values must be frozenset (immutable)."""
        for key, value in DOMAIN_KEYWORDS.items():
            assert isinstance(value, frozenset), (
                f"DOMAIN_KEYWORDS[{key!r}] is {type(value).__name__}, expected frozenset."
            )

    def test_domain_keywords_keys_are_enum_instances(self) -> None:
        """All DOMAIN_KEYWORDS keys must be EnumSemanticDomain instances."""
        for key in DOMAIN_KEYWORDS:
            assert isinstance(key, EnumSemanticDomain), (
                f"DOMAIN_KEYWORDS key {key!r} is {type(key).__name__}, "
                "expected EnumSemanticDomain."
            )


# ---------------------------------------------------------------------------
# Typed-class mapping coverage
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTypedClassMappingCoverage:
    """Verify the typed-class mapping covers all non-UNKNOWN intent categories."""

    def test_every_intent_category_has_typed_class_mapping(self) -> None:
        """Every EnumIntentCategory (except UNKNOWN) must appear in the typed-class mapping."""
        mapping = get_category_to_typed_class_mapping()
        enum_values = {
            m.value for m in EnumIntentCategory if m != EnumIntentCategory.UNKNOWN
        }

        missing = enum_values - set(mapping.keys())
        assert not missing, (
            f"Intent categories without typed-class mapping: {missing}. "
            "Add them to _CATEGORY_TO_TYPED_CLASS in handler_typed_classification.py."
        )


# ---------------------------------------------------------------------------
# DOMAIN_TO_INTENT_MAP consistency
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDomainToIntentMapConsistency:
    """Verify DOMAIN_TO_INTENT_MAP values are valid EnumIntentCategory members."""

    def test_all_intent_map_values_are_valid_categories(self) -> None:
        """Every value in DOMAIN_TO_INTENT_MAP must be a valid EnumIntentCategory value."""
        valid_values = {m.value for m in EnumIntentCategory}

        invalid = {
            k: v for k, v in DOMAIN_TO_INTENT_MAP.items() if v not in valid_values
        }
        assert not invalid, (
            f"DOMAIN_TO_INTENT_MAP has values not in EnumIntentCategory: {invalid}. "
            "Update the map or add missing enum members."
        )


# ---------------------------------------------------------------------------
# StrEnum backwards compatibility
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStrEnumBackwardsCompatibility:
    """Verify StrEnum members compare equal to their plain string values."""

    def test_intent_category_equals_string(self) -> None:
        """EnumIntentCategory members must equal their string values for dict lookups."""
        assert EnumIntentCategory.DEBUGGING == "debugging"
        assert EnumIntentCategory.CODE_GENERATION == "code_generation"
        assert EnumIntentCategory.UNKNOWN == "unknown"

    def test_semantic_domain_equals_string(self) -> None:
        """EnumSemanticDomain members must equal their string values for dict lookups."""
        assert EnumSemanticDomain.API_DESIGN == "api_design"
        assert EnumSemanticDomain.TESTING == "testing"
        assert EnumSemanticDomain.SECURITY == "security"

    def test_intent_category_in_dict_lookup(self) -> None:
        """EnumIntentCategory members must work as dict keys with string access."""
        d: dict[str, int] = {EnumIntentCategory.DEBUGGING: 1}
        assert d["debugging"] == 1
        assert d[EnumIntentCategory.DEBUGGING] == 1

    def test_semantic_domain_in_dict_lookup(self) -> None:
        """EnumSemanticDomain members must work as dict keys with string access."""
        d: dict[str, int] = {EnumSemanticDomain.API_DESIGN: 1}
        assert d["api_design"] == 1
        assert d[EnumSemanticDomain.API_DESIGN] == 1
