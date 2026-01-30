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
        Values match the CHECK constraint in migration 006_create_pattern_injections.sql.
        If you add values here, update the SQL constraint too.

    See Also:
        - omnibase_core.enums.hooks.claude_code.EnumClaudeCodeHookEventType
        - deployment/database/migrations/006_create_pattern_injections.sql
    """

    SESSION_START = "SessionStart"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    SUBAGENT_START = "SubagentStart"


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
        Values match the CHECK constraint in migration 006_create_pattern_injections.sql.
        If you add values here, update the SQL constraint too.

    See Also:
        - deployment/database/migrations/006_create_pattern_injections.sql
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
    "EnumCohort",
    "EnumInjectionContext",
]
