# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for the intent drift detect compute node.

Tests cover:
    - Tool allowlist configuration per intent class
    - Tool mismatch drift detection
    - File surface drift detection
    - Scope expansion drift detection
    - FEATURE intent immunity (broad scope — no tool_mismatch)
    - Severity scoring
    - Frozen model constraints

Reference: OMN-2489
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from pydantic import ValidationError

from omniintelligence.nodes.node_intent_drift_detect_compute.handlers import (
    detect_drift,
    score_severity,
)
from omniintelligence.nodes.node_intent_drift_detect_compute.models import (
    DriftDetectionSettings,
    ModelDriftSensitivity,
    ModelIntentDriftInput,
    ModelIntentDriftSignal,
    get_suspicious_tools,
    get_tool_allowlist,
)
from omniintelligence.nodes.node_intent_drift_detect_compute.node import (
    NodeIntentDriftDetectCompute,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime(2026, 2, 21, 12, 0, 0, tzinfo=UTC)


def _make_input(
    *,
    intent_class: EnumIntentClass = EnumIntentClass.REFACTOR,
    tool_name: str = "Read",
    files_modified: list[str] | None = None,
) -> ModelIntentDriftInput:
    return ModelIntentDriftInput(
        session_id="sess-001",
        correlation_id=uuid4(),
        intent_class=intent_class,
        tool_name=tool_name,
        files_modified=files_modified or [],
        detected_at=_now(),
    )


def _default_sensitivity() -> ModelDriftSensitivity:
    return ModelDriftSensitivity()


def _zero_sensitivity() -> ModelDriftSensitivity:
    return ModelDriftSensitivity(
        tool_mismatch_threshold=0.0,
        file_surface_threshold=0.0,
        scope_expansion_threshold=0.0,
    )


def _high_sensitivity() -> ModelDriftSensitivity:
    return ModelDriftSensitivity(
        tool_mismatch_threshold=1.0,
        file_surface_threshold=1.0,
        scope_expansion_threshold=1.0,
    )


# ---------------------------------------------------------------------------
# Tool allowlist / suspicious tool configuration
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.drift
class TestToolAllowlists:
    """Tests for per-intent-class tool allowlist configuration."""

    def test_bugfix_allowlist_contains_expected_tools(self) -> None:
        """BUGFIX intent allowlist includes Read, Grep, Edit, Bash."""
        allowlist = get_tool_allowlist(EnumIntentClass.BUGFIX)
        assert "Read" in allowlist
        assert "Grep" in allowlist
        assert "Edit" in allowlist
        assert "Bash" in allowlist

    def test_documentation_suspicious_tools_includes_bash(self) -> None:
        """DOCUMENTATION intent marks Bash as suspicious."""
        suspicious = get_suspicious_tools(EnumIntentClass.DOCUMENTATION)
        assert "Bash" in suspicious

    def test_feature_has_no_suspicious_tools(self) -> None:
        """FEATURE intent has an empty suspicious tool set (broad scope)."""
        suspicious = get_suspicious_tools(EnumIntentClass.FEATURE)
        assert len(suspicious) == 0

    def test_refactor_marks_write_as_suspicious(self) -> None:
        """REFACTOR intent marks Write as suspicious."""
        suspicious = get_suspicious_tools(EnumIntentClass.REFACTOR)
        assert "Write" in suspicious

    def test_all_intent_classes_have_allowlists(self) -> None:
        """All 8 intent classes have tool allowlists."""
        for cls in EnumIntentClass:
            allowlist = get_tool_allowlist(cls)
            assert isinstance(allowlist, set)


# ---------------------------------------------------------------------------
# Severity scoring
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.drift
class TestScoreSeverity:
    """Tests for severity scoring function."""

    def test_zero_score_is_info(self) -> None:
        assert score_severity(0.0) == "info"

    def test_low_score_is_info(self) -> None:
        assert score_severity(0.2) == "info"

    def test_medium_score_is_warning(self) -> None:
        assert score_severity(0.5) == "warning"

    def test_high_score_is_alert(self) -> None:
        assert score_severity(0.8) == "alert"

    def test_max_score_is_alert(self) -> None:
        assert score_severity(1.0) == "alert"

    def test_threshold_boundary_warning(self) -> None:
        """Score exactly at warning cutoff is warning."""
        assert score_severity(0.33) == "warning"

    def test_threshold_boundary_alert(self) -> None:
        """Score exactly at alert cutoff is alert."""
        assert score_severity(0.66) == "alert"


# ---------------------------------------------------------------------------
# Tool mismatch drift detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.drift
class TestToolMismatchDrift:
    """Tests for tool_mismatch drift detection."""

    def test_documentation_intent_bash_triggers_drift(self) -> None:
        """DOCUMENTATION intent calling Bash triggers tool_mismatch drift."""
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION, tool_name="Bash"
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        assert signal.drift_type == "tool_mismatch"
        assert signal.intent_class == EnumIntentClass.DOCUMENTATION
        assert signal.tool_name == "Bash"

    def test_bugfix_intent_write_triggers_drift(self) -> None:
        """BUGFIX intent calling Write triggers tool_mismatch drift."""
        input_data = _make_input(intent_class=EnumIntentClass.BUGFIX, tool_name="Write")
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        assert signal.drift_type == "tool_mismatch"

    def test_feature_intent_bash_no_drift(self) -> None:
        """FEATURE intent calling Bash does NOT trigger drift (broad scope)."""
        input_data = _make_input(intent_class=EnumIntentClass.FEATURE, tool_name="Bash")
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is None

    def test_feature_intent_write_no_drift(self) -> None:
        """FEATURE intent calling Write does NOT trigger drift."""
        input_data = _make_input(
            intent_class=EnumIntentClass.FEATURE, tool_name="Write"
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is None

    def test_refactor_read_no_drift(self) -> None:
        """REFACTOR intent calling Read is normal — no drift."""
        input_data = _make_input(
            intent_class=EnumIntentClass.REFACTOR, tool_name="Read"
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is None

    def test_zero_threshold_suppresses_drift(self) -> None:
        """tool_mismatch_threshold=0.0 suppresses all tool_mismatch detection."""
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION, tool_name="Bash"
        )
        sensitivity = ModelDriftSensitivity(tool_mismatch_threshold=0.0)
        signal = detect_drift(input_data, sensitivity)
        assert signal is None

    def test_drift_signal_is_frozen(self) -> None:
        """Drift signal is immutable after construction."""
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION, tool_name="Bash"
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        with pytest.raises((TypeError, ValidationError)):
            signal.drift_type = "scope_expansion"  # type: ignore[misc]

    def test_signal_contains_reason(self) -> None:
        """Drift signal includes a human-readable reason."""
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION, tool_name="Bash"
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        assert len(signal.reason) > 0
        assert "Bash" in signal.reason or "DOCUMENTATION" in signal.reason

    def test_signal_session_id_preserved(self) -> None:
        """Session ID from input is preserved in the drift signal."""
        input_data = ModelIntentDriftInput(
            session_id="my-session-123",
            correlation_id=uuid4(),
            intent_class=EnumIntentClass.DOCUMENTATION,
            tool_name="Bash",
            files_modified=[],
            detected_at=_now(),
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        assert signal.session_id == "my-session-123"

    def test_high_sensitivity_produces_alert(self) -> None:
        """High sensitivity (1.0) produces alert severity."""
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION, tool_name="Bash"
        )
        signal = detect_drift(input_data, _high_sensitivity())
        assert signal is not None
        assert signal.severity == "alert"

    def test_medium_sensitivity_produces_warning(self) -> None:
        """Medium sensitivity (0.5 default) produces warning or info severity."""
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION, tool_name="Bash"
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        assert signal.severity in ("info", "warning")


# ---------------------------------------------------------------------------
# File surface drift detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.drift
class TestFileSurfaceDrift:
    """Tests for file_surface drift detection."""

    def test_documentation_intent_modifies_py_file_triggers_drift(self) -> None:
        """DOCUMENTATION intent modifying a .py file triggers drift.

        Edit is suspicious for DOCUMENTATION (tool_mismatch fires first via
        priority ordering). Use a non-suspicious tool (Glob) so file_surface
        fires instead of tool_mismatch.
        """
        # Glob is not suspicious for DOCUMENTATION, so file_surface can fire
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION,
            tool_name="Glob",
            files_modified=["src/omniintelligence/nodes/node_foo/node.py"],
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        assert signal.drift_type == "file_surface"

    def test_documentation_intent_modifies_md_file_no_drift(self) -> None:
        """DOCUMENTATION intent modifying a .md file is normal — no drift."""
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION,
            tool_name="Write",
            files_modified=["docs/README.md"],
        )
        signal = detect_drift(input_data, _default_sensitivity())
        # May trigger tool_mismatch for Write+DOCUMENTATION, but NOT file_surface
        if signal is not None:
            assert signal.drift_type != "file_surface"

    def test_bugfix_many_files_triggers_drift(self) -> None:
        """BUGFIX intent touching >5 files in one call triggers file_surface drift."""
        many_files = [f"src/module_{i}.py" for i in range(7)]
        input_data = _make_input(
            intent_class=EnumIntentClass.BUGFIX,
            tool_name="Edit",
            files_modified=many_files,
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        assert signal.drift_type == "file_surface"

    def test_bugfix_few_files_no_file_surface_drift(self) -> None:
        """BUGFIX intent touching 3 files is normal — no file_surface drift."""
        input_data = _make_input(
            intent_class=EnumIntentClass.BUGFIX,
            tool_name="Edit",
            files_modified=["src/module_a.py", "src/module_b.py", "tests/test_a.py"],
        )
        signal = detect_drift(input_data, _default_sensitivity())
        # No file_surface drift; may have none at all
        if signal is not None:
            assert signal.drift_type != "file_surface"

    def test_zero_file_surface_threshold_suppresses_detection(self) -> None:
        """file_surface_threshold=0.0 suppresses all file_surface detection."""
        many_files = [f"src/module_{i}.py" for i in range(7)]
        input_data = _make_input(
            intent_class=EnumIntentClass.BUGFIX,
            tool_name="Edit",
            files_modified=many_files,
        )
        sensitivity = ModelDriftSensitivity(file_surface_threshold=0.0)
        signal = detect_drift(input_data, sensitivity)
        if signal is not None:
            assert signal.drift_type != "file_surface"


# ---------------------------------------------------------------------------
# Scope expansion drift detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.drift
class TestScopeExpansionDrift:
    """Tests for scope_expansion drift detection."""

    def test_refactor_write_triggers_scope_expansion(self) -> None:
        """REFACTOR intent using Write triggers scope_expansion drift."""
        input_data = _make_input(
            intent_class=EnumIntentClass.REFACTOR, tool_name="Write"
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        assert signal.drift_type in ("tool_mismatch", "scope_expansion")

    def test_refactor_edit_no_scope_expansion(self) -> None:
        """REFACTOR intent using Edit is normal — no scope_expansion."""
        input_data = _make_input(
            intent_class=EnumIntentClass.REFACTOR, tool_name="Edit"
        )
        signal = detect_drift(input_data, _default_sensitivity())
        # Edit is in the REFACTOR allowlist; should not trigger scope_expansion
        if signal is not None:
            assert signal.drift_type != "scope_expansion"

    def test_zero_scope_expansion_threshold_suppresses_detection(self) -> None:
        """scope_expansion_threshold=0.0 suppresses scope_expansion detection."""
        input_data = _make_input(
            intent_class=EnumIntentClass.REFACTOR, tool_name="Write"
        )
        sensitivity = ModelDriftSensitivity(
            tool_mismatch_threshold=0.0,
            scope_expansion_threshold=0.0,
        )
        signal = detect_drift(input_data, sensitivity)
        assert signal is None

    def test_feature_write_no_scope_expansion(self) -> None:
        """FEATURE intent using Write is expected — no scope_expansion."""
        input_data = _make_input(
            intent_class=EnumIntentClass.FEATURE, tool_name="Write"
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is None


# ---------------------------------------------------------------------------
# Clean path (no drift)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.drift
class TestNoDrift:
    """Tests for clean tool calls that should not trigger drift."""

    def test_clean_refactor_read_no_drift(self) -> None:
        signal = detect_drift(
            _make_input(intent_class=EnumIntentClass.REFACTOR, tool_name="Read"),
            _default_sensitivity(),
        )
        assert signal is None

    def test_clean_bugfix_grep_no_drift(self) -> None:
        signal = detect_drift(
            _make_input(intent_class=EnumIntentClass.BUGFIX, tool_name="Grep"),
            _default_sensitivity(),
        )
        assert signal is None

    def test_clean_security_read_no_drift(self) -> None:
        signal = detect_drift(
            _make_input(intent_class=EnumIntentClass.SECURITY, tool_name="Read"),
            _default_sensitivity(),
        )
        assert signal is None

    def test_zero_sensitivity_never_triggers(self) -> None:
        """With all thresholds at 0.0 no drift signal fires."""
        cases = [
            (EnumIntentClass.DOCUMENTATION, "Bash"),
            (EnumIntentClass.BUGFIX, "Write"),
            (EnumIntentClass.REFACTOR, "Write"),
        ]
        for intent_class, tool_name in cases:
            signal = detect_drift(
                _make_input(intent_class=intent_class, tool_name=tool_name),
                _zero_sensitivity(),
            )
            assert signal is None, (
                f"Expected no signal for {intent_class}/{tool_name} at zero sensitivity"
            )


# ---------------------------------------------------------------------------
# Drift detection settings
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.drift
class TestDriftDetectionSettings:
    """Tests for DriftDetectionSettings Pydantic Settings model."""

    def test_default_settings_produce_valid_sensitivity(self) -> None:
        """Default settings convert to a valid ModelDriftSensitivity."""
        settings = DriftDetectionSettings()
        sensitivity = settings.to_sensitivity()
        assert isinstance(sensitivity, ModelDriftSensitivity)
        assert 0.0 <= sensitivity.tool_mismatch_threshold <= 1.0
        assert 0.0 <= sensitivity.file_surface_threshold <= 1.0
        assert 0.0 <= sensitivity.scope_expansion_threshold <= 1.0

    def test_sensitivity_is_frozen(self) -> None:
        """ModelDriftSensitivity is immutable after construction."""
        sensitivity = ModelDriftSensitivity()
        with pytest.raises((TypeError, ValidationError)):
            sensitivity.tool_mismatch_threshold = 0.9  # type: ignore[misc]

    def test_custom_sensitivity_values(self) -> None:
        """ModelDriftSensitivity accepts custom threshold values."""
        sensitivity = ModelDriftSensitivity(
            tool_mismatch_threshold=0.8,
            file_surface_threshold=0.3,
            scope_expansion_threshold=0.7,
        )
        assert sensitivity.tool_mismatch_threshold == pytest.approx(0.8)
        assert sensitivity.file_surface_threshold == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Frozen model constraints
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.drift
class TestFrozenModels:
    """Tests for frozen Pydantic model constraints."""

    def test_drift_input_is_frozen(self) -> None:
        """ModelIntentDriftInput is immutable after construction."""
        input_data = _make_input()
        with pytest.raises((TypeError, ValidationError)):
            input_data.tool_name = "Bash"  # type: ignore[misc]

    def test_drift_signal_event_type_is_literal(self) -> None:
        """Drift signal event_type is 'IntentDriftSignal'."""
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION, tool_name="Bash"
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        assert signal.event_type == "IntentDriftSignal"

    def test_drift_signal_detected_at_preserved(self) -> None:
        """Drift signal preserves the detected_at timestamp from input."""
        ts = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        input_data = ModelIntentDriftInput(
            session_id="s",
            correlation_id=uuid4(),
            intent_class=EnumIntentClass.DOCUMENTATION,
            tool_name="Bash",
            files_modified=[],
            detected_at=ts,
        )
        signal = detect_drift(input_data, _default_sensitivity())
        assert signal is not None
        assert signal.detected_at == ts

    def test_construct_drift_signal_directly(self) -> None:
        """ModelIntentDriftSignal can be constructed directly with all fields."""
        signal = ModelIntentDriftSignal(
            session_id="s",
            correlation_id=uuid4(),
            intent_class=EnumIntentClass.REFACTOR,
            drift_type="tool_mismatch",
            severity="warning",
            tool_name="Write",
            files_modified=["foo.py"],
            reason="Test signal",
            detected_at=_now(),
        )
        assert signal.drift_type == "tool_mismatch"
        assert signal.severity == "warning"


# ---------------------------------------------------------------------------
# Node sensitivity injection
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.drift
class TestNodeCompute:
    """Tests for NodeIntentDriftDetectCompute.compute() via env-var configuration."""

    @pytest.mark.asyncio
    async def test_node_compute_returns_signal_with_high_sensitivity_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Node.compute() produces alert when env thresholds are set to 1.0."""
        monkeypatch.setenv("DRIFT_TOOL_MISMATCH_THRESHOLD", "1.0")
        monkeypatch.setenv("DRIFT_FILE_SURFACE_THRESHOLD", "1.0")
        monkeypatch.setenv("DRIFT_SCOPE_EXPANSION_THRESHOLD", "1.0")
        container = ModelONEXContainer()
        node = NodeIntentDriftDetectCompute(container)
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION, tool_name="Bash"
        )
        signal = await node.compute(input_data)
        assert signal is not None
        assert signal.severity == "alert"

    @pytest.mark.asyncio
    async def test_node_compute_returns_none_with_zero_sensitivity_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Node.compute() returns None when env thresholds are set to 0.0."""
        monkeypatch.setenv("DRIFT_TOOL_MISMATCH_THRESHOLD", "0.0")
        monkeypatch.setenv("DRIFT_FILE_SURFACE_THRESHOLD", "0.0")
        monkeypatch.setenv("DRIFT_SCOPE_EXPANSION_THRESHOLD", "0.0")
        container = ModelONEXContainer()
        node = NodeIntentDriftDetectCompute(container)
        input_data = _make_input(
            intent_class=EnumIntentClass.DOCUMENTATION, tool_name="Bash"
        )
        signal = await node.compute(input_data)
        assert signal is None
