# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Pure compute handlers for intent drift detection.

All functions are pure (no I/O, no side effects). Sensitivity configuration
is passed in by the caller so tests can supply controlled values.

Detection is observational only — it NEVER blocks execution.

Public API:
    detect_drift    — Classify a tool-call event for drift; returns signal or None.
    score_severity  — Map a raw drift score to a severity literal.

Reference: OMN-2489
"""

from __future__ import annotations

from typing import Literal

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass

from omniintelligence.nodes.node_intent_drift_detect_compute.models.model_drift_config import (
    ModelDriftSensitivity,
    get_suspicious_tools,
)
from omniintelligence.nodes.node_intent_drift_detect_compute.models.model_intent_drift import (
    ModelIntentDriftInput,
    ModelIntentDriftSignal,
)

# ---------------------------------------------------------------------------
# Severity thresholds (shared between tool_mismatch and file_surface)
# A raw score in [0, 1] maps to:
#   < 0.33  → info
#   < 0.66  → warning
#   >= 0.66 → alert
# ---------------------------------------------------------------------------
_SEV_WARN_CUTOFF: float = 0.33
_SEV_ALERT_CUTOFF: float = 0.66


def score_severity(
    score: float,
) -> Literal["info", "warning", "alert"]:
    """Map a normalised drift score in [0, 1] to a severity string.

    Args:
        score: Normalised drift score (0.0 = minimal, 1.0 = maximum).

    Returns:
        One of 'info', 'warning', 'alert'.
    """
    if score >= _SEV_ALERT_CUTOFF:
        return "alert"
    if score >= _SEV_WARN_CUTOFF:
        return "warning"
    return "info"


def _check_tool_mismatch(
    intent_class: EnumIntentClass,
    tool_name: str,
    sensitivity: ModelDriftSensitivity,
) -> ModelIntentDriftSignal | None:
    """Return a tool_mismatch drift signal if the tool is suspicious.

    Args:
        intent_class: The active intent class.
        tool_name: The tool that was called.
        sensitivity: Sensitivity thresholds.

    Returns:
        ModelIntentDriftSignal if drift detected, else None.
    """
    # FEATURE has an empty suspicious set — never triggers tool_mismatch
    suspicious = get_suspicious_tools(intent_class)
    if not suspicious:
        return None

    if tool_name not in suspicious:
        return None

    threshold = sensitivity.tool_mismatch_threshold
    if threshold == 0.0:
        return None

    # Score = threshold (direct mapping; suspicious match raises to sensitivity level)
    severity = score_severity(threshold)

    return None  # sentinel — returned below with proper data


def _detect_tool_mismatch(
    input_data: ModelIntentDriftInput,
    sensitivity: ModelDriftSensitivity,
) -> ModelIntentDriftSignal | None:
    """Detect tool_mismatch drift.

    A tool_mismatch occurs when the called tool is in the suspicious set for
    the active intent class.

    Args:
        input_data: Frozen drift detection input.
        sensitivity: Sensitivity thresholds.

    Returns:
        ModelIntentDriftSignal if drift detected, else None.
    """
    suspicious = get_suspicious_tools(input_data.intent_class)
    if not suspicious:
        return None  # FEATURE and other unrestricted classes

    if input_data.tool_name not in suspicious:
        return None

    threshold = sensitivity.tool_mismatch_threshold
    if threshold == 0.0:
        return None

    severity = score_severity(threshold)

    return ModelIntentDriftSignal(
        session_id=input_data.session_id,
        correlation_id=input_data.correlation_id,
        intent_class=input_data.intent_class,
        drift_type="tool_mismatch",
        severity=severity,
        tool_name=input_data.tool_name,
        files_modified=list(input_data.files_modified),
        reason=(
            f"Tool '{input_data.tool_name}' is suspicious for "
            f"{input_data.intent_class.value} intent"
        ),
        detected_at=input_data.detected_at,
    )


def _detect_file_surface(
    input_data: ModelIntentDriftInput,
    sensitivity: ModelDriftSensitivity,
) -> ModelIntentDriftSignal | None:
    """Detect file_surface drift.

    A file_surface drift occurs when a tool call modifies files outside the
    expected scope for the intent class. Detection heuristic:
    - BUGFIX: new file creation (files not previously known) is suspicious
    - DOCUMENTATION: modifying .py source files (code edits during doc intent)
    - SECURITY: broad edits to files outside security-relevant paths

    For a pure compute node without file-system access, the heuristic uses
    path naming conventions and counts:
    - Writing/modifying many files (>5) in a BUGFIX session is suspicious
    - Modifying .py files during DOCUMENTATION intent is suspicious

    Args:
        input_data: Frozen drift detection input.
        sensitivity: Sensitivity thresholds.

    Returns:
        ModelIntentDriftSignal if drift detected, else None.
    """
    threshold = sensitivity.file_surface_threshold
    if threshold == 0.0:
        return None

    files = input_data.files_modified
    if not files:
        return None

    intent_class = input_data.intent_class
    reason: str | None = None

    if intent_class == EnumIntentClass.DOCUMENTATION:
        # Code files (.py, .ts, .go) modified during DOCUMENTATION intent
        code_files = [
            f
            for f in files
            if any(f.endswith(ext) for ext in (".py", ".ts", ".go", ".rs", ".java"))
            and not f.endswith(("__init__.py",))
        ]
        if code_files:
            reason = (
                f"DOCUMENTATION intent modified {len(code_files)} code file(s): "
                f"{', '.join(code_files[:3])}"
            )

    elif intent_class == EnumIntentClass.BUGFIX:
        # Creating many new files during BUGFIX is suspicious (scope expansion)
        # Pure heuristic: many files touched in a single Bash/Write call
        if len(files) > 5:
            reason = (
                f"BUGFIX intent touched {len(files)} files in one tool call "
                "(expected narrow file scope)"
            )

    if reason is None:
        return None

    severity = score_severity(threshold)
    return ModelIntentDriftSignal(
        session_id=input_data.session_id,
        correlation_id=input_data.correlation_id,
        intent_class=input_data.intent_class,
        drift_type="file_surface",
        severity=severity,
        tool_name=input_data.tool_name,
        files_modified=list(input_data.files_modified),
        reason=reason,
        detected_at=input_data.detected_at,
    )


def _detect_scope_expansion(
    input_data: ModelIntentDriftInput,
    sensitivity: ModelDriftSensitivity,
) -> ModelIntentDriftSignal | None:
    """Detect scope_expansion drift.

    A scope_expansion drift occurs when the execution scope grows beyond the
    intent boundary. Heuristic: REFACTOR intent that calls Write (new files)
    is likely adding net-new features, not just restructuring.

    Args:
        input_data: Frozen drift detection input.
        sensitivity: Sensitivity thresholds.

    Returns:
        ModelIntentDriftSignal if drift detected, else None.
    """
    threshold = sensitivity.scope_expansion_threshold
    if threshold == 0.0:
        return None

    intent_class = input_data.intent_class
    tool_name = input_data.tool_name

    # REFACTOR + Write tool = likely adding new code, not just moving/renaming
    if intent_class == EnumIntentClass.REFACTOR and tool_name == "Write":
        severity = score_severity(threshold)
        return ModelIntentDriftSignal(
            session_id=input_data.session_id,
            correlation_id=input_data.correlation_id,
            intent_class=input_data.intent_class,
            drift_type="scope_expansion",
            severity=severity,
            tool_name=tool_name,
            files_modified=list(input_data.files_modified),
            reason=(
                "REFACTOR intent used Write tool — may indicate new feature "
                "creation beyond refactoring scope"
            ),
            detected_at=input_data.detected_at,
        )

    return None


def detect_drift(
    input_data: ModelIntentDriftInput,
    sensitivity: ModelDriftSensitivity,
) -> ModelIntentDriftSignal | None:
    """Classify a tool-call event for drift. Returns the first detected signal.

    Detection runs per-tool-call. Checks are applied in priority order:
    1. tool_mismatch (tool is in suspicious set for intent class)
    2. file_surface (files outside expected scope)
    3. scope_expansion (execution scope grew beyond intent boundary)

    Detection is NEVER blocking — it always returns promptly and has no
    side effects. Callers may emit the returned signal to Kafka but are not
    required to.

    FEATURE intent never triggers tool_mismatch (broad scope is expected).

    Args:
        input_data: Frozen drift detection input with session, intent, and tool call.
        sensitivity: Sensitivity thresholds controlling trigger levels.

    Returns:
        First detected ModelIntentDriftSignal, or None if no drift detected.
    """
    # Priority 1: tool_mismatch
    signal = _detect_tool_mismatch(input_data, sensitivity)
    if signal is not None:
        return signal

    # Priority 2: file_surface
    signal = _detect_file_surface(input_data, sensitivity)
    if signal is not None:
        return signal

    # Priority 3: scope_expansion
    signal = _detect_scope_expansion(input_data, sensitivity)
    if signal is not None:
        return signal

    return None


__all__ = [
    "detect_drift",
    "score_severity",
]
