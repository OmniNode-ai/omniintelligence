"""Type protocols for success criteria matching handler results.

This module defines TypedDict structures and enums for type-safe handler responses,
enabling static type checking with mypy and improved IDE support.

Design Decisions:
    - TypedDict is used because handlers return dicts, not objects with methods.
    - MISSING sentinel distinguishes "key not found" from "key is None".
    - All operators are enumerated for explicit, validated comparisons.
    - CriterionMatchResultDict provides detailed per-criterion results.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final, TypedDict


# =============================================================================
# Type Aliases
# =============================================================================

# JSON-compatible types for execution outcome values
# Matches the expected_value type from SuccessCriterionDict
JsonPrimitive = str | int | float | bool | None
JsonValue = JsonPrimitive | list[Any] | dict[str, Any]


# =============================================================================
# MISSING Sentinel
# =============================================================================


class _MissingSentinel:
    """Sentinel class for distinguishing missing keys from None values.

    This is a singleton class - only one instance (MISSING) should exist.
    Used when resolving field paths to distinguish between:
    - Field exists with value None
    - Field does not exist at all

    Example:
        >>> outcome = {"status": None}
        >>> resolve_field_path(outcome, "status")  # Returns None
        >>> resolve_field_path(outcome, "missing_key")  # Returns MISSING
    """

    _instance: _MissingSentinel | None = None

    def __new__(cls) -> _MissingSentinel:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        # MISSING is falsy but distinct from None
        return False


# Singleton instance - use this throughout the codebase
MISSING: Final[_MissingSentinel] = _MissingSentinel()


# =============================================================================
# Enums
# =============================================================================


class EnumCriteriaOperator(StrEnum):
    """Supported comparison operators for criteria matching.

    Each operator defines a specific comparison semantic:
        - equals/not_equals: Exact value comparison
        - greater_than/less_than/etc: Numeric comparisons
        - contains/not_contains: Membership or substring tests
        - regex: Pattern matching via re.search
        - is_null/is_not_null: Null checks (MISSING fails both)

    Note:
        MISSING values fail all comparisons except explicit null checks,
        and even then MISSING is distinct from None (null).
    """

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_OR_EQUAL = "less_or_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    REGEX = "regex"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


# Set of valid operator values for fast lookup
VALID_OPERATORS: Final[frozenset[str]] = frozenset(
    op.value for op in EnumCriteriaOperator
)


# =============================================================================
# TypedDicts
# =============================================================================


class CriterionMatchResultDict(TypedDict):
    """Result for a single criterion evaluation.

    This provides detailed information about how a single criterion was matched,
    including the actual value found, the comparison performed, and the outcome.

    Attributes:
        criterion_id: Identifier of the criterion that was evaluated.
        field: The field path that was resolved (echoed from input).
        matched: Whether the criterion was satisfied.
        actual_value: The value found at the field path (None if MISSING).
        actual_type: Type name of actual_value for debugging.
        expected_value: The expected value from the criterion.
        operator: The comparison operator used.
        weight: The weight assigned to this criterion.
        required: Whether this criterion was marked as required.
        reason: Short, deterministic explanation of the result.

    Example:
        >>> result: CriterionMatchResultDict = {
        ...     "criterion_id": "exit_success",
        ...     "field": "exit_code",
        ...     "matched": True,
        ...     "actual_value": 0,
        ...     "actual_type": "int",
        ...     "expected_value": 0,
        ...     "operator": "equals",
        ...     "weight": 1.0,
        ...     "required": True,
        ...     "reason": "0 equals 0",
        ... }
    """

    criterion_id: str
    field: str
    matched: bool
    actual_value: JsonValue | None  # None represents MISSING
    actual_type: str
    expected_value: JsonValue | None
    operator: str
    weight: float
    required: bool
    reason: str


class CriteriaMatchResult(TypedDict):
    """Internal result from match_criteria() function.

    This is the intermediate result before being converted to the output model.
    It contains aggregated match information across all criteria.

    Attributes:
        success: True if all required criteria passed.
        matched_criteria: List of criterion_ids that matched.
        unmatched_criteria: List of criterion_ids that did not match.
        match_score: Weighted score from 0.0 to 1.0.
        match_details: Per-criterion detailed results.

    Scoring Rules:
        - Empty criteria list: success=True, score=1.0
        - All criteria matched: success=True, score=weighted_sum/total_weight
        - Required criterion failed: success=False
        - total_weight==0: score=1.0 if all required pass, else 0.0

    Example:
        >>> result: CriteriaMatchResult = {
        ...     "success": True,
        ...     "matched_criteria": ["crit_1", "crit_2"],
        ...     "unmatched_criteria": ["crit_3"],
        ...     "match_score": 0.75,
        ...     "match_details": [...],
        ... }
    """

    success: bool
    matched_criteria: list[str]
    unmatched_criteria: list[str]
    match_score: float
    match_details: list[CriterionMatchResultDict]


def get_type_name(value: Any) -> str:
    """Get human-readable type name for debugging.

    Maps Python types to simple string names for use in match result details.

    Args:
        value: Any value to get the type name for.

    Returns:
        Type name string: 'int', 'float', 'str', 'bool', 'list', 'dict',
        'null' (for None), 'missing' (for MISSING), or the class name.

    Example:
        >>> get_type_name(42)
        'int'
        >>> get_type_name(None)
        'null'
        >>> get_type_name(MISSING)
        'missing'
    """
    if value is MISSING:
        return "missing"
    if value is None:
        return "null"
    if isinstance(value, bool):
        # Check bool before int since bool is subclass of int
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


# Type alias for values that can be MISSING or a JSON value
# Used for resolve_field_path return type
MaybeJsonValue = JsonValue | _MissingSentinel


__all__ = [
    "MISSING",
    "VALID_OPERATORS",
    "CriteriaMatchResult",
    "CriterionMatchResultDict",
    "EnumCriteriaOperator",
    "JsonPrimitive",
    "JsonValue",
    "MaybeJsonValue",
    "get_type_name",
]
