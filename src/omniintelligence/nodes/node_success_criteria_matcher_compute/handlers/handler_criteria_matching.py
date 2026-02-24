# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler for success criteria matching computation.

This module provides pure functions for matching execution outcomes against
success criteria. All functions are side-effect-free and suitable for use
in compute nodes.

The matching system evaluates criteria using configurable operators:
    - equals/not_equals: Exact value comparison
    - greater_than/less_than/greater_or_equal/less_or_equal: Numeric comparison
    - contains/not_contains: Membership or substring tests
    - regex: Pattern matching via re.search
    - is_null/is_not_null: Null checks (MISSING fails both)

Field Path Resolution:
    - Supports dot-notation: "outputs.0.name"
    - List indices are non-negative integers: "items.0.value"
    - Returns MISSING sentinel for non-existent paths
    - Rejects invalid paths (empty tokens, invalid characters)

Example:
    from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers import (
        match_criteria,
        resolve_field_path,
    )

    outcome = {"status": "success", "exit_code": 0, "outputs": [{"name": "result"}]}
    criteria = [
        {"criterion_id": "status_ok", "field": "status", "operator": "equals", "expected_value": "success"},
        {"criterion_id": "exit_ok", "field": "exit_code", "operator": "equals", "expected_value": 0},
    ]

    result = match_criteria(outcome, criteria)
    if result["success"]:
        print(f"All required criteria passed! Score: {result['match_score']}")
"""

from __future__ import annotations

import re
from typing import Any, Final, cast

from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.exceptions import (
    CriteriaMatchingValidationError,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.protocols import (
    MISSING,
    VALID_OPERATORS,
    CriteriaMatchResult,
    CriterionMatchResultDict,
    EnumCriteriaOperator,
    JsonValue,
    MaybeJsonValue,
    get_type_name,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.models.model_success_criteria_input import (
    SuccessCriterionDict,
)

# =============================================================================
# Constants
# =============================================================================

# Pattern for valid field path tokens: alphanumeric + underscore
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_]+$")

# Pattern for non-negative integer (list index)
_INDEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")


# =============================================================================
# Main Matching Function
# =============================================================================


def match_criteria(
    outcome: dict[str, object],
    criteria: list[SuccessCriterionDict],
) -> CriteriaMatchResult:
    """Evaluate all criteria against an execution outcome.

    This is the main entry point for criteria matching. It validates the criteria
    set, evaluates each criterion against the outcome, and calculates aggregate
    scores.

    Algorithm:
        1. Validate criteria set (unique IDs, valid operators, non-negative weights,
           pre-compile regex patterns)
        2. For each criterion:
           a. Resolve field path from outcome (supports list indexing)
           b. Apply operator comparison
           c. Record pass/fail with weight
        3. Calculate weighted match_score
        4. Determine success (all required=True criteria must pass)

    Args:
        outcome: Dictionary containing execution results to match against.
        criteria: List of success criteria to evaluate.

    Returns:
        CriteriaMatchResult with match status, scores, and details.

    Edge Cases:
        - Empty criteria list: success=True, score=1.0
        - total_weight==0: score=1.0 if all required pass, else 0.0
        - MISSING field: is_null fails, is_not_null fails, other operators fail

    Raises:
        CriteriaMatchingValidationError: If criteria set is invalid.

    Example:
        >>> outcome = {"status": "success", "exit_code": 0}
        >>> criteria = [{"criterion_id": "c1", "field": "exit_code", "operator": "equals", "expected_value": 0}]
        >>> result = match_criteria(outcome, criteria)
        >>> result["success"]
        True
    """
    # Edge case: empty criteria = success
    if not criteria:
        return CriteriaMatchResult(
            success=True,
            matched_criteria=[],
            unmatched_criteria=[],
            match_score=1.0,
            match_details=[],
        )

    # Validate criteria set (may raise CriteriaMatchingValidationError)
    compiled_regex = _validate_criteria_set(criteria)

    # Evaluate each criterion
    match_details: list[CriterionMatchResultDict] = []
    matched_ids: list[str] = []
    unmatched_ids: list[str] = []
    all_required_passed = True
    weighted_sum = 0.0
    total_weight = 0.0

    for criterion in criteria:
        result = _evaluate_criterion(outcome, criterion, compiled_regex)
        match_details.append(result)

        weight = criterion.get("weight", 1.0)
        required = criterion.get("required", False)
        criterion_id = criterion.get("criterion_id", "")

        total_weight += weight

        if result["matched"]:
            matched_ids.append(criterion_id)
            weighted_sum += weight
        else:
            unmatched_ids.append(criterion_id)
            if required:
                all_required_passed = False

    # Calculate match score
    if total_weight > 0:
        match_score = weighted_sum / total_weight
    else:
        # No weighted criteria - base success on required criteria
        match_score = 1.0 if all_required_passed else 0.0

    return CriteriaMatchResult(
        success=all_required_passed,
        matched_criteria=matched_ids,
        unmatched_criteria=unmatched_ids,
        match_score=round(match_score, 4),
        match_details=match_details,
    )


# =============================================================================
# Field Path Resolution
# =============================================================================


def resolve_field_path(
    data: dict[str, Any], path: str
) -> MaybeJsonValue:  # any-ok: dict invariance -- callers pass deserialized JSON
    """Resolve a dot-notation field path from a nested data structure.

    Supports dictionary keys and list indices (non-negative integers).

    Args:
        data: The data dictionary to resolve the path from.
        path: Dot-notation path (e.g., "outputs.0.name").

    Returns:
        The value at the path, or MISSING if the path doesn't exist.

    Raises:
        CriteriaMatchingValidationError: If path syntax is invalid.

    Path Syntax Rules:
        - Tokens separated by dots: "a.b.c"
        - Allowed tokens: [A-Za-z0-9_]+ (alphanumeric and underscore only)
        - Rejects: empty tokens ("a..b"), leading/trailing dots, invalid characters
        - Returns MISSING (not None) for missing keys or out-of-range indexes

    Examples:
        >>> data = {"status": "ok", "items": [{"name": "a"}, {"name": "b"}]}
        >>> resolve_field_path(data, "status")
        'ok'
        >>> resolve_field_path(data, "items.0.name")
        'a'
        >>> resolve_field_path(data, "missing")
        MISSING
    """
    # Validate path is not empty
    if not path or not path.strip():
        raise CriteriaMatchingValidationError("Field path cannot be empty")

    # Check for leading/trailing dots
    if path.startswith(".") or path.endswith("."):
        raise CriteriaMatchingValidationError(
            f"Invalid field path '{path}': leading or trailing dots not allowed"
        )

    tokens = path.split(".")

    # Validate each token
    for token in tokens:
        if not token:
            raise CriteriaMatchingValidationError(
                f"Invalid field path '{path}': empty token (consecutive dots)"
            )
        if not _TOKEN_PATTERN.match(token):
            raise CriteriaMatchingValidationError(
                f"Invalid field path '{path}': token '{token}' contains invalid characters"
            )

    # Traverse the data structure
    # any-ok: traverses heterogeneous nested structures (dicts/lists)
    current: Any = data

    for token in tokens:
        # Check if token is a list index
        if _INDEX_PATTERN.match(token):
            index = int(token)
            if not isinstance(current, list | tuple):
                return MISSING
            if index >= len(current):
                return MISSING
            current = current[index]
        else:
            # Dictionary key access
            if not isinstance(current, dict):
                return MISSING
            if token not in current:
                return MISSING
            current = current[token]

    # Cast needed because 'current' is typed as object from dict traversal
    return cast("MaybeJsonValue", current)


# =============================================================================
# Operator Application
# =============================================================================


def apply_operator(
    actual: Any,  # any-ok: actual values come from heterogeneous JSON data, require dynamic dispatch
    operator: EnumCriteriaOperator,
    expected: JsonValue | None,
) -> tuple[bool, str]:
    """Apply a comparison operator between actual and expected values.

    Args:
        actual: The actual value from the outcome (may be MISSING).
        operator: The comparison operator to apply.
        expected: The expected value from the criterion.

    Returns:
        Tuple of (matched: bool, reason: str).
        The reason is a short, deterministic explanation.

    Operator Semantics:
        - equals: actual == expected (type-sensitive)
        - not_equals: actual != expected
        - greater_than: actual > expected (numeric only)
        - less_than: actual < expected (numeric only)
        - greater_or_equal: actual >= expected (numeric only)
        - less_or_equal: actual <= expected (numeric only)
        - contains:
            - str: str(expected) in actual
            - list/tuple/set: expected in actual
            - dict: expected in actual.keys()
            - else: fail with "contains unsupported for type"
        - not_contains: inverse of contains
        - regex: re.search(expected, str(actual)) where expected is str
        - is_null: actual is None (MISSING -> fail)
        - is_not_null: actual is not None and actual is not MISSING

    Examples:
        >>> apply_operator(0, EnumCriteriaOperator.EQUALS, 0)
        (True, '0 equals 0')
        >>> apply_operator(MISSING, EnumCriteriaOperator.IS_NULL, None)
        (False, 'value is missing, not null')
    """
    # Handle MISSING value first
    if actual is MISSING:
        if operator == EnumCriteriaOperator.IS_NULL:
            return False, "value is missing, not null"
        if operator == EnumCriteriaOperator.IS_NOT_NULL:
            return False, "value is missing"
        return False, "field is missing"

    # Handle null checks
    if operator == EnumCriteriaOperator.IS_NULL:
        if actual is None:
            return True, "value is null"
        return False, f"expected null, got {get_type_name(actual)}"

    if operator == EnumCriteriaOperator.IS_NOT_NULL:
        if actual is not None:
            return True, f"value is {get_type_name(actual)}, not null"
        return False, "value is null"

    # Handle equality operators
    if operator == EnumCriteriaOperator.EQUALS:
        if actual == expected:
            return True, f"{_safe_repr(actual)} equals {_safe_repr(expected)}"
        return False, f"{_safe_repr(actual)} does not equal {_safe_repr(expected)}"

    if operator == EnumCriteriaOperator.NOT_EQUALS:
        if actual != expected:
            return True, f"{_safe_repr(actual)} does not equal {_safe_repr(expected)}"
        return False, f"{_safe_repr(actual)} equals {_safe_repr(expected)}"

    # Handle numeric comparisons
    if operator in (
        EnumCriteriaOperator.GREATER_THAN,
        EnumCriteriaOperator.LESS_THAN,
        EnumCriteriaOperator.GREATER_OR_EQUAL,
        EnumCriteriaOperator.LESS_OR_EQUAL,
    ):
        return _apply_numeric_operator(actual, operator, expected)

    # Handle contains operators
    if operator == EnumCriteriaOperator.CONTAINS:
        return _apply_contains(actual, expected, negate=False)

    if operator == EnumCriteriaOperator.NOT_CONTAINS:
        return _apply_contains(actual, expected, negate=True)

    # Handle regex
    if operator == EnumCriteriaOperator.REGEX:
        return _apply_regex(actual, expected)

    # Should never reach here if operator validation worked
    return False, f"unknown operator: {operator}"


# =============================================================================
# Validation
# =============================================================================


def _validate_criteria_set(
    criteria: list[SuccessCriterionDict],
) -> dict[str, re.Pattern[str]]:
    """Validate criteria set before matching.

    Checks for:
        - Duplicate criterion_ids
        - Invalid operator names
        - Negative weights
        - Invalid regex patterns (pre-compiled to catch early)

    Args:
        criteria: List of criteria to validate.

    Returns:
        Dictionary mapping criterion_id to compiled regex pattern (if operator is regex).

    Raises:
        CriteriaMatchingValidationError: If any validation fails.
    """
    seen_ids: set[str] = set()
    compiled_regex: dict[str, re.Pattern[str]] = {}

    for criterion in criteria:
        criterion_id = criterion.get("criterion_id", "")

        # Check for duplicate IDs
        if criterion_id in seen_ids:
            raise CriteriaMatchingValidationError(
                f"Duplicate criterion_id: '{criterion_id}'"
            )
        seen_ids.add(criterion_id)

        # Validate operator
        operator = criterion.get("operator", "")
        if operator not in VALID_OPERATORS:
            raise CriteriaMatchingValidationError(
                f"Invalid operator '{operator}' for criterion '{criterion_id}'. "
                f"Valid operators: {sorted(VALID_OPERATORS)}"
            )

        # Validate weight is non-negative
        weight = criterion.get("weight", 1.0)
        if weight < 0:
            raise CriteriaMatchingValidationError(
                f"Negative weight ({weight}) for criterion '{criterion_id}'"
            )

        # Pre-compile regex patterns
        if operator == EnumCriteriaOperator.REGEX.value:
            expected = criterion.get("expected_value")
            if not isinstance(expected, str):
                raise CriteriaMatchingValidationError(
                    f"Regex operator requires string expected_value for criterion '{criterion_id}', "
                    f"got {type(expected).__name__}"
                )
            try:
                compiled_regex[criterion_id] = re.compile(expected)
            except re.error as e:
                raise CriteriaMatchingValidationError(
                    f"Invalid regex pattern for criterion '{criterion_id}': {e}"
                ) from None

    return compiled_regex


# =============================================================================
# Private Helper Functions
# =============================================================================


def _evaluate_criterion(
    outcome: dict[str, object],
    criterion: SuccessCriterionDict,
    compiled_regex: dict[str, re.Pattern[str]],
) -> CriterionMatchResultDict:
    """Evaluate a single criterion against the outcome.

    Args:
        outcome: The execution outcome to match against.
        criterion: The criterion to evaluate.
        compiled_regex: Pre-compiled regex patterns.

    Returns:
        CriterionMatchResultDict with detailed match result.
    """
    criterion_id = criterion.get("criterion_id", "")
    field = criterion.get("field", "")
    operator_str = criterion.get("operator", "equals")
    expected = criterion.get("expected_value")
    weight = criterion.get("weight", 1.0)
    required = criterion.get("required", False)

    # Resolve field path
    try:
        actual = resolve_field_path(outcome, field) if field else MISSING
    except CriteriaMatchingValidationError:
        # Invalid field path - treat as MISSING but record the error
        actual = MISSING

    # Convert operator string to enum
    operator = EnumCriteriaOperator(operator_str)

    # Apply operator (use pre-compiled regex if available)
    if operator == EnumCriteriaOperator.REGEX and criterion_id in compiled_regex:
        matched, reason = _apply_compiled_regex(actual, compiled_regex[criterion_id])
    else:
        matched, reason = apply_operator(actual, operator, expected)

    # Determine actual_value for output (None if MISSING)
    # Cast needed because mypy doesn't narrow MaybeJsonValue after MISSING check
    actual_for_output: JsonValue | None = (
        None if actual is MISSING else cast(JsonValue, actual)
    )

    return CriterionMatchResultDict(
        criterion_id=criterion_id,
        field=field,
        matched=matched,
        actual_value=actual_for_output,
        actual_type=get_type_name(actual),
        expected_value=expected,
        operator=operator_str,
        weight=weight,
        required=required,
        reason=reason,
    )


def _apply_numeric_operator(
    actual: Any,  # any-ok: actual values come from heterogeneous JSON data, require dynamic dispatch
    operator: EnumCriteriaOperator,
    expected: JsonValue | None,
) -> tuple[bool, str]:
    """Apply numeric comparison operator.

    Args:
        actual: The actual value.
        operator: One of the numeric comparison operators.
        expected: The expected value.

    Returns:
        Tuple of (matched, reason).
    """
    # Check if both values are numeric
    if not isinstance(actual, int | float) or isinstance(actual, bool):
        return False, f"cannot compare: {get_type_name(actual)} is not numeric"

    if not isinstance(expected, int | float) or isinstance(expected, bool):
        return (
            False,
            f"cannot compare: expected {get_type_name(expected)} is not numeric",
        )

    # Perform comparison
    if operator == EnumCriteriaOperator.GREATER_THAN:
        if actual > expected:
            return True, f"{actual} > {expected}"
        return False, f"{actual} is not > {expected}"

    if operator == EnumCriteriaOperator.LESS_THAN:
        if actual < expected:
            return True, f"{actual} < {expected}"
        return False, f"{actual} is not < {expected}"

    if operator == EnumCriteriaOperator.GREATER_OR_EQUAL:
        if actual >= expected:
            return True, f"{actual} >= {expected}"
        return False, f"{actual} is not >= {expected}"

    if operator == EnumCriteriaOperator.LESS_OR_EQUAL:
        if actual <= expected:
            return True, f"{actual} <= {expected}"
        return False, f"{actual} is not <= {expected}"

    return False, f"unsupported numeric operator: {operator}"


def _apply_contains(
    actual: Any,  # any-ok: actual values come from heterogeneous JSON data, require dynamic dispatch
    expected: JsonValue | None,
    negate: bool,
) -> tuple[bool, str]:
    """Apply contains or not_contains operator.

    Args:
        actual: The actual value to search in.
        expected: The value to search for.
        negate: If True, apply not_contains logic.

    Returns:
        Tuple of (matched, reason).
    """
    op_name = "not_contains" if negate else "contains"

    # String containment
    if isinstance(actual, str):
        search_str = str(expected) if expected is not None else ""
        found = search_str in actual
        if negate:
            found = not found
        if found:
            return True, f"'{_safe_repr(actual)}' {op_name} '{search_str}'"
        return (
            False,
            f"'{_safe_repr(actual)}' does not satisfy {op_name} '{search_str}'",
        )

    # Sequence/set membership
    if isinstance(actual, list | tuple | set):
        found = expected in actual
        if negate:
            found = not found
        if found:
            return True, f"{_safe_repr(expected)} {op_name} collection"
        return False, f"{_safe_repr(expected)} not in collection"

    # Dictionary key membership
    if isinstance(actual, dict):
        found = expected in actual
        if negate:
            found = not found
        if found:
            return True, f"{_safe_repr(expected)} {op_name} dict keys"
        return False, f"{_safe_repr(expected)} not in dict keys"

    return False, f"contains unsupported for type {get_type_name(actual)}"


def _apply_regex(
    actual: Any,  # any-ok: actual values come from heterogeneous JSON data, require dynamic dispatch
    expected: JsonValue | None,
) -> tuple[bool, str]:
    """Apply regex operator.

    Args:
        actual: The actual value to match against.
        expected: The regex pattern string.

    Returns:
        Tuple of (matched, reason).
    """
    if not isinstance(expected, str):
        return False, f"regex pattern must be string, got {get_type_name(expected)}"

    try:
        pattern = re.compile(expected)
        return _apply_compiled_regex(actual, pattern)
    except re.error as e:
        return False, f"invalid regex: {e}"


def _apply_compiled_regex(
    actual: Any,  # any-ok: actual values come from heterogeneous JSON data, require dynamic dispatch
    pattern: re.Pattern[str],
) -> tuple[bool, str]:
    """Apply a pre-compiled regex pattern.

    Args:
        actual: The actual value to match against.
        pattern: The compiled regex pattern.

    Returns:
        Tuple of (matched, reason).
    """
    # Convert actual to string for matching
    actual_str = str(actual) if actual is not None else ""

    if pattern.search(actual_str):
        return True, f"'{_truncate(actual_str, 30)}' matches pattern"
    return False, f"'{_truncate(actual_str, 30)}' does not match pattern"


def _safe_repr(value: object, max_len: int = 50) -> str:
    """Get a safe, truncated string representation of a value.

    Args:
        value: The value to represent.
        max_len: Maximum length of the result.

    Returns:
        String representation, truncated if necessary.
    """
    if value is MISSING:
        return "MISSING"
    if value is None:
        return "null"

    try:
        s = repr(value)
        return _truncate(s, max_len)
    except Exception:
        return f"<{type(value).__name__}>"


def _truncate(s: str, max_len: int) -> str:
    """Truncate a string with ellipsis if too long.

    Args:
        s: String to truncate.
        max_len: Maximum length.

    Returns:
        Truncated string with "..." suffix if truncated.
    """
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


# =============================================================================
# Public Wrapper (Naming Convention)
# =============================================================================


def handle_match_criteria(
    outcome: dict[str, object],
    criteria: list[SuccessCriterionDict],
) -> CriteriaMatchResult:
    """Handle success criteria matching (naming convention wrapper).

    This function follows the ONEX handler naming convention (handle_*)
    and delegates to the core match_criteria function.

    Args:
        outcome: Dictionary containing execution results to match against.
        criteria: List of success criteria to evaluate.

    Returns:
        CriteriaMatchResult with match status, scores, and details.

    Raises:
        CriteriaMatchingValidationError: If criteria set is invalid.
    """
    return match_criteria(outcome, criteria)


__all__ = [
    "apply_operator",
    "handle_match_criteria",
    "match_criteria",
    "resolve_field_path",
]
