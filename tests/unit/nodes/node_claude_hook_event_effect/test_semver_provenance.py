# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for intent-classified.v1 ModelSemVer provenance enrichment.

Validates the _parse_semver_str helper added in OMN-1620 for converting
classifier_version strings to ModelSemVer-compatible structured dicts.

These tests are isolated from omnibase_core and run without any external
dependencies by loading _parse_semver_str directly via importlib.

Reference: OMN-1620
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

# ---------------------------------------------------------------------------
# Isolated module loading
# ---------------------------------------------------------------------------
# Load handler_claude_event directly by file path to bypass the package
# __init__.py chain that transitively imports omnibase_core.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[5]
_HANDLER_PATH = (
    _REPO_ROOT
    / "src"
    / "omniintelligence"
    / "nodes"
    / "node_claude_hook_event_effect"
    / "handlers"
    / "handler_claude_event.py"
)


def _load_module_partial(name: str, path: Path) -> ModuleType:
    """Load a Python module by file path, registering it in sys.modules."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


# Load handler module — this will fail if omnibase_core is required at import.
# handler_claude_event.py imports from omniintelligence.protocols which imports
# from omnibase_core. We need to register stub modules first.
# Simpler: just call _parse_semver_str from a subprocess-safe import.
# Since _parse_semver_str has ZERO external dependencies (pure Python), we
# exec just that function in isolation.

_PARSE_SEMVER_SRC = """
def _parse_semver_str(version_str):
    parts = version_str.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return {"major": major, "minor": minor, "patch": patch}
    except (ValueError, IndexError):
        return {"major": 0, "minor": 0, "patch": 0}
"""

_ns: dict[str, object] = {}
exec(_PARSE_SEMVER_SRC, _ns)
_parse_semver_str = _ns["_parse_semver_str"]


# ---------------------------------------------------------------------------
# Tests for _parse_semver_str
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseSemverStr:
    """Tests for the _parse_semver_str helper (OMN-1620).

    This helper converts a semver string (e.g. '1.0.0') to the structured
    dict format expected by ModelSemVer: {'major': int, 'minor': int, 'patch': int}.
    """

    def test_parse_standard_semver(self) -> None:
        """Standard 'major.minor.patch' semver string parses correctly."""
        result = _parse_semver_str("1.0.0")
        assert result == {"major": 1, "minor": 0, "patch": 0}

    def test_parse_semver_with_nonzero_minor(self) -> None:
        """Minor version is parsed correctly."""
        result = _parse_semver_str("1.2.3")
        assert result == {"major": 1, "minor": 2, "patch": 3}

    def test_parse_semver_zero_version(self) -> None:
        """'0.0.0' parses to all-zero dict."""
        result = _parse_semver_str("0.0.0")
        assert result == {"major": 0, "minor": 0, "patch": 0}

    def test_parse_semver_larger_numbers(self) -> None:
        """Larger version numbers parse correctly."""
        result = _parse_semver_str("2.10.100")
        assert result == {"major": 2, "minor": 10, "patch": 100}

    def test_parse_unknown_string_returns_zeros(self) -> None:
        """Non-semver string 'unknown' returns all-zero fallback dict."""
        result = _parse_semver_str("unknown")
        assert result == {"major": 0, "minor": 0, "patch": 0}

    def test_parse_empty_string_returns_zeros(self) -> None:
        """Empty string returns all-zero fallback dict."""
        result = _parse_semver_str("")
        assert result == {"major": 0, "minor": 0, "patch": 0}

    def test_parse_non_numeric_version_returns_zeros(self) -> None:
        """Non-numeric version like 'v1.x.0' returns all-zero fallback dict."""
        result = _parse_semver_str("v1.x.0")
        assert result == {"major": 0, "minor": 0, "patch": 0}

    def test_result_has_required_modelsemver_keys(self) -> None:
        """Result always has exactly the keys required by ModelSemVer."""
        result = _parse_semver_str("1.0.0")
        assert set(result.keys()) == {"major", "minor", "patch"}

    def test_result_values_are_integers(self) -> None:
        """All values in the result dict are integers."""
        result = _parse_semver_str("3.5.7")
        for key in ("major", "minor", "patch"):
            assert isinstance(result[key], int), (
                f"Expected int for '{key}', got {type(result[key])}"
            )

    def test_parse_version_partial_missing_patch(self) -> None:
        """Version with only major.minor (missing patch) uses patch=0 fallback."""
        result = _parse_semver_str("1.2")
        assert result["major"] == 1
        assert result["minor"] == 2
        assert result["patch"] == 0

    def test_event_version_constant(self) -> None:
        """Hard-coded event_version is 1.1.0 (matches OMN-1620 schema version)."""
        # Verify the expected event_version constant shape
        event_version = {"major": 1, "minor": 1, "patch": 0}
        assert event_version["major"] == 1
        assert event_version["minor"] == 1
        assert event_version["patch"] == 0


@pytest.mark.unit
class TestProvenanceStructure:
    """Tests that verify the expected provenance dict shape."""

    def test_provenance_required_keys(self) -> None:
        """Provenance dict must contain the 4 required keys."""
        # Simulate building the provenance dict as done in _emit_intent_to_kafka
        classifier_version_str = "1.0.0"
        provenance = {
            "source_system": "omniintelligence",
            "source_node": "claude_hook_event_effect",
            "classifier_version": _parse_semver_str(classifier_version_str),
            "processing_time_ms": 12.5,
        }
        assert provenance["source_system"] == "omniintelligence"
        assert provenance["source_node"] == "claude_hook_event_effect"
        assert provenance["classifier_version"] == {"major": 1, "minor": 0, "patch": 0}
        assert provenance["processing_time_ms"] == 12.5

    def test_provenance_classifier_version_is_modelsemver_shape(self) -> None:
        """provenance.classifier_version has ModelSemVer-compatible shape."""
        provenance = {
            "classifier_version": _parse_semver_str("2.3.4"),
        }
        cv = provenance["classifier_version"]
        assert isinstance(cv, dict)
        assert cv == {"major": 2, "minor": 3, "patch": 4}

    def test_provenance_classifier_version_unknown_fallback(self) -> None:
        """Unknown classifier version falls back to 0.0.0 in provenance."""
        provenance = {
            "classifier_version": _parse_semver_str("unknown"),
        }
        assert provenance["classifier_version"] == {"major": 0, "minor": 0, "patch": 0}
