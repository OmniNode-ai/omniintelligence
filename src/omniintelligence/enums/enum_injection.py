"""Injection-related enums for pattern injection tracking.

This module contains enums for the pattern_injections table:
- EnumInjectionContext: Valid hook events where patterns can be injected
- EnumCohort: A/B experiment cohort assignment

ONEX Compliance:
    - Enum-based naming: Enum{Category}
    - String-based enum for JSON serialization
    - Integration with Pydantic models

Ticket: OMN-1670
"""

from enum import Enum


class EnumInjectionContext(str, Enum):
    """Valid contexts where pattern injection can occur.

    This is a subset of Claude Code hook event types, limited to the
    lifecycle points where pattern injection is semantically valid.

    Attributes:
        SESSION_START: Injection at session initialization
        USER_PROMPT_SUBMIT: Injection when user submits a prompt
        PRE_TOOL_USE: Injection before tool execution
        SUBAGENT_START: Injection when a subagent spawns

    Example:
        >>> from omniintelligence.enums import EnumInjectionContext
        >>> context = EnumInjectionContext.SESSION_START
        >>> assert context.value == "SessionStart"

    Note:
        Values match the CHECK constraint in migration 007_create_pattern_injections.sql.
        If you add values here, update the SQL constraint too.

    See Also:
        - omnibase_core.enums.hooks.claude_code.EnumClaudeCodeHookEventType
        - deployment/database/migrations/007_create_pattern_injections.sql
    """

    SESSION_START = "SessionStart"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    SUBAGENT_START = "SubagentStart"


class EnumHeuristicMethod(str, Enum):
    """Heuristic method for contribution attribution.

    These methods distribute credit among patterns injected during a session.
    This is explicitly a HEURISTIC, not causal attribution - multi-injection
    sessions make true causal attribution impossible without controlled experiments.

    Attributes:
        EQUAL_SPLIT: Equal credit to all patterns (1/N each)
        RECENCY_WEIGHTED: More credit to later patterns (linear ramp)
        FIRST_MATCH: All credit to the first pattern

    Confidence levels reflect the inherent uncertainty:
        - EQUAL_SPLIT: 0.5 (moderate - at least it's fair)
        - RECENCY_WEIGHTED: 0.4 (lower - recency bias is an assumption)
        - FIRST_MATCH: 0.3 (lowest - ignores all but one pattern)

    Example:
        >>> from omniintelligence.enums import EnumHeuristicMethod
        >>> method = EnumHeuristicMethod.EQUAL_SPLIT
        >>> assert method.value == "equal_split"

    Note:
        Values match the heuristic_method column in pattern_injections table.

    See Also:
        - OMN-1679: FEEDBACK-004 contribution heuristic implementation
        - ~/.claude/plans/elegant-waddling-hinton.md
    """

    EQUAL_SPLIT = "equal_split"
    RECENCY_WEIGHTED = "recency_weighted"
    FIRST_MATCH = "first_match"


# Confidence scores for each heuristic method
HEURISTIC_CONFIDENCE: dict[str, float] = {
    EnumHeuristicMethod.EQUAL_SPLIT.value: 0.5,
    EnumHeuristicMethod.RECENCY_WEIGHTED.value: 0.4,
    EnumHeuristicMethod.FIRST_MATCH.value: 0.3,
}


class EnumCohort(str, Enum):
    """A/B experiment cohort for pattern injection.

    Sessions are assigned to cohorts using a deterministic hash-based
    algorithm: hash(session_id + salt) % 100. The split is currently
    20% control, 80% treatment.

    The cohort value is stored on each injection record so the assignment
    logic can evolve without rewriting historical data.

    Attributes:
        CONTROL: No pattern injection (baseline for comparison)
        TREATMENT: Receives validated pattern injection

    Example:
        >>> from omniintelligence.enums import EnumCohort
        >>> cohort = EnumCohort.TREATMENT
        >>> assert cohort.value == "treatment"

    Note:
        Values match the CHECK constraint in migration 007_create_pattern_injections.sql.
        If you add values here, update the SQL constraint too.

    See Also:
        - deployment/database/migrations/007_create_pattern_injections.sql
        - ~/.claude/plans/elegant-waddling-hinton.md (A/B experiment design)
    """

    CONTROL = "control"
    TREATMENT = "treatment"


# Constants for cohort assignment
COHORT_CONTROL_PERCENTAGE = 20
COHORT_TREATMENT_PERCENTAGE = 80


__all__ = [
    "COHORT_CONTROL_PERCENTAGE",
    "COHORT_TREATMENT_PERCENTAGE",
    "HEURISTIC_CONFIDENCE",
    "EnumCohort",
    "EnumHeuristicMethod",
    "EnumInjectionContext",
]
