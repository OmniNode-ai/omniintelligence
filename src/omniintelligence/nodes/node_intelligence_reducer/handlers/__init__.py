# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handlers for Intelligence Reducer Node.

This module provides handler functions for FSM transitions in the intelligence
reducer. Each FSM type (INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT,
PATTERN_LIFECYCLE) has dedicated handler logic.

Current Handlers:
    - PATTERN_LIFECYCLE: handle_pattern_lifecycle_transition
    - PROCESS: handle_pattern_lifecycle_process (builds ModelReducerOutput)
"""

from omniintelligence.nodes.node_intelligence_reducer.handlers.handler_pattern_lifecycle import (
    ERROR_GUARD_CONDITION_FAILED,
    ERROR_INVALID_FROM_STATE,
    ERROR_INVALID_TRANSITION,
    ERROR_INVALID_TRIGGER,
    ERROR_STATE_MISMATCH,
    GUARD_CONDITIONS,
    VALID_STATES,
    VALID_TRANSITIONS,
    VALID_TRIGGERS,
    PatternLifecycleTransitionResult,
    get_fsm_transition_table,
    get_guard_conditions,
    handle_pattern_lifecycle_transition,
    validate_transition,
)
from omniintelligence.nodes.node_intelligence_reducer.handlers.handler_process import (
    handle_pattern_lifecycle_process,
)

__all__ = [
    "ERROR_GUARD_CONDITION_FAILED",
    "ERROR_INVALID_FROM_STATE",
    "ERROR_INVALID_TRANSITION",
    "ERROR_INVALID_TRIGGER",
    "ERROR_STATE_MISMATCH",
    "GUARD_CONDITIONS",
    "VALID_STATES",
    "VALID_TRANSITIONS",
    "VALID_TRIGGERS",
    "PatternLifecycleTransitionResult",
    "get_fsm_transition_table",
    "get_guard_conditions",
    "handle_pattern_lifecycle_process",
    "handle_pattern_lifecycle_transition",
    "validate_transition",
]
