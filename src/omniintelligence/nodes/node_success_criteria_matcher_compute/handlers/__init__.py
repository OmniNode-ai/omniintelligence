"""Success Criteria Matcher Compute Handlers.

This module provides pure handler functions for success criteria matching operations.
Handlers implement the computation logic following the ONEX "pure shell pattern"
where nodes delegate to side-effect-free handler functions.

Handler Pattern:
    Each handler is a pure function that:
    - Accepts execution outcome and criteria configuration
    - Evaluates criteria against the outcome
    - Returns a typed result dictionary
    - Has no side effects (pure computation)

Operator Support:
    The matching system supports 11 comparison operators:
    - equals/not_equals: Exact value comparison
    - greater_than/less_than/greater_or_equal/less_or_equal: Numeric comparison
    - contains/not_contains: Membership or substring tests
    - regex: Pattern matching via re.search
    - is_null/is_not_null: Null checks (MISSING fails both)

Field Path Resolution:
    - Supports dot-notation: "outputs.0.name"
    - List indices are non-negative integers
    - Returns MISSING sentinel for non-existent paths

Usage:
    from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers import (
        match_criteria,
        resolve_field_path,
        apply_operator,
        EnumCriteriaOperator,
        MISSING,
    )

    outcome = {"status": "success", "exit_code": 0}
    criteria = [
        {
            "criterion_id": "exit_ok",
            "field": "exit_code",
            "operator": "equals",
            "expected_value": 0,
            "required": True,
        }
    ]

    result = match_criteria(outcome, criteria)
    if result["success"]:
        print(f"All required criteria passed! Score: {result['match_score']}")

Example:
    >>> from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers import (
    ...     match_criteria,
    ...     MISSING,
    ... )
    >>> outcome = {"status": "success", "items": [{"name": "a"}, {"name": "b"}]}
    >>> criteria = [
    ...     {"criterion_id": "c1", "field": "status", "operator": "equals", "expected_value": "success"},
    ...     {"criterion_id": "c2", "field": "items.0.name", "operator": "equals", "expected_value": "a"},
    ... ]
    >>> result = match_criteria(outcome, criteria)
    >>> result["success"]
    True
    >>> result["match_score"]
    1.0
"""

from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.exceptions import (
    CriteriaMatchingComputeError,
    CriteriaMatchingValidationError,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.handler_compute import (
    handle_success_criteria_compute,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.handler_criteria_matching import (
    apply_operator,
    handle_match_criteria,
    match_criteria,
    resolve_field_path,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.protocols import (
    MISSING,
    VALID_OPERATORS,
    CriteriaMatchResult,
    CriterionMatchResultDict,
    EnumCriteriaOperator,
    JsonPrimitive,
    JsonValue,
    MaybeJsonValue,
    get_type_name,
)

__all__ = [
    "MISSING",
    "VALID_OPERATORS",
    "CriteriaMatchResult",
    "CriteriaMatchingComputeError",
    "CriteriaMatchingValidationError",
    "CriterionMatchResultDict",
    "EnumCriteriaOperator",
    "JsonPrimitive",
    "JsonValue",
    "MaybeJsonValue",
    "apply_operator",
    "get_type_name",
    "handle_match_criteria",
    "handle_success_criteria_compute",
    "match_criteria",
    "resolve_field_path",
]
