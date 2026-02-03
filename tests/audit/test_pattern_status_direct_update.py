"""Audit test: Forbid direct pattern status updates outside effect node.

This test enforces OMN-1805's architectural invariant:
"All pattern status changes MUST flow through the reducer -> effect node pipeline."

Any direct SQL UPDATE to learned_patterns.status outside the effect node
is a violation that will cause race conditions and audit log gaps.

Ticket: OMN-1805
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

# Apply audit marker to all tests in this module
pytestmark = pytest.mark.audit

# Files that ARE allowed to update status
# Per ONEX invariant: "Effect nodes must never block on Kafka"
# When Kafka is unavailable, promotion handler uses direct SQL as fallback.
# This is documented in handler_promotion.py docstring.
ALLOWED_FILES = {
    "handler_transition.py",  # Primary path: effect node handler
    "handler_promotion.py",  # Fallback path: direct SQL when Kafka unavailable
}

# Forbidden patterns - direct status updates
FORBIDDEN_PATTERNS = [
    # Direct SQL UPDATE statements targeting learned_patterns.status
    r"UPDATE\s+learned_patterns\s+.*SET\s+.*status\s*=",
    r"SET\s+status\s*=\s*['\"](?:candidate|provisional|validated|deprecated)['\"]",
    # Helper method bypasses
    r"\.update_status\s*\(",
    r"\.set_status\s*\(",
    # Direct assignment patterns that might indicate bypass
    # (only match when it looks like a database operation context)
    r"['\"]status['\"]\s*:\s*['\"](?:candidate|provisional|validated|deprecated)['\"]",
]

# Directories to scan - all pattern-related effect node handlers
# that might be tempted to update status directly
SCAN_DIRS = [
    "src/omniintelligence/nodes/node_pattern_promotion_effect/handlers",
    "src/omniintelligence/nodes/node_pattern_demotion_effect/handlers",
    "src/omniintelligence/nodes/pattern_storage_effect/handlers",
    "src/omniintelligence/nodes/node_pattern_feedback_effect/handlers",
    # Also scan node_pattern_lifecycle_effect/handlers but allow handler_transition.py
    "src/omniintelligence/nodes/node_pattern_lifecycle_effect/handlers",
]


def _get_project_root() -> Path:
    """Get project root directory."""
    # Navigate from tests/audit/ to project root
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root")


def _scan_file_for_violations(file_path: Path) -> list[str]:
    """Scan a file for forbidden patterns.

    Args:
        file_path: Path to the Python file to scan.

    Returns:
        List of violation strings with format "filename:line: Found forbidden pattern: ..."

    Raises:
        OSError: If file cannot be read (permissions, encoding issues, etc.)
    """
    violations = []

    try:
        content = file_path.read_text()
    except OSError as e:
        # Do not silently ignore file read errors - they could hide violations
        logger.error(
            "Failed to read file during audit scan: %s - %s",
            file_path,
            e,
        )
        raise OSError(
            f"Audit scan failed: Cannot read file {file_path}. "
            f"Error: {e}. This may hide architectural violations."
        ) from e

    for pattern in FORBIDDEN_PATTERNS:
        matches = list(re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE))
        for match in matches:
            # Find line number
            line_num = content[: match.start()].count("\n") + 1
            # Truncate match for readability
            matched_text = match.group()
            if len(matched_text) > 50:
                matched_text = matched_text[:50] + "..."
            violations.append(f"{file_path.name}:{line_num}: Found forbidden pattern: {matched_text}")

    return violations


class TestPatternStatusDirectUpdate:
    """Tests ensuring pattern status updates only occur via the lifecycle effect node."""

    def test_no_direct_pattern_status_updates(self) -> None:
        """Verify no unauthorized handler directly updates learned_patterns.status.

        This test enforces the architectural invariant from OMN-1805:
        All status changes must use authorized code paths.

        Authorized handlers:
        - handler_transition.py: Primary path (reducer -> effect node pipeline)
        - handler_promotion.py: Fallback path (direct SQL when Kafka unavailable)

        All other handlers must emit ModelPatternLifecycleEvent to Kafka.
        """
        project_root = _get_project_root()
        all_violations: list[str] = []

        for scan_dir in SCAN_DIRS:
            dir_path = project_root / scan_dir
            if not dir_path.exists():
                continue

            for handler_file in dir_path.glob("handler_*.py"):
                # Skip allowed files
                if handler_file.name in ALLOWED_FILES:
                    continue

                violations = _scan_file_for_violations(handler_file)
                if violations:
                    all_violations.extend([f"{scan_dir}/{v}" for v in violations])

        assert not all_violations, (
            "Direct pattern status updates found outside authorized handlers!\n\n"
            "OMN-1805 VIOLATION: Status changes must use authorized code paths.\n\n"
            "Violations found:\n"
            + "\n".join(f"  - {v}" for v in all_violations)
            + "\n\n"
            "Fix: Emit ModelPatternLifecycleEvent to Kafka instead of direct SQL UPDATE.\n"
            "Authorized handlers:\n"
            "  - handler_transition.py: Primary path (reducer -> effect node)\n"
            "  - handler_promotion.py: Fallback path (when Kafka unavailable)"
        )

    def test_effect_node_handler_exists(self) -> None:
        """Verify the effect node handler exists (sanity check).

        This ensures the authorized transition handler exists at the expected
        location, which is required for the OMN-1805 pattern lifecycle state machine.
        """
        project_root = _get_project_root()
        effect_handler = (
            project_root / "src/omniintelligence/nodes/node_pattern_lifecycle_effect/handlers/handler_transition.py"
        )
        assert effect_handler.exists(), (
            f"Effect node handler not found at {effect_handler}. "
            "This is required for OMN-1805 pattern lifecycle state machine."
        )

    def test_allowed_file_can_update_status(self) -> None:
        """Verify handler_transition.py contains status update logic.

        This is a positive test to ensure the authorized handler actually
        does what it's supposed to do - update pattern status.
        """
        project_root = _get_project_root()
        effect_handler = (
            project_root / "src/omniintelligence/nodes/node_pattern_lifecycle_effect/handlers/handler_transition.py"
        )

        if not effect_handler.exists():
            pytest.skip("handler_transition.py not found")

        content = effect_handler.read_text()

        # The authorized handler should have SQL for updating status
        assert "UPDATE learned_patterns" in content, (
            "handler_transition.py should contain UPDATE learned_patterns SQL "
            "as it is the authorized status update handler."
        )
        assert "SET status" in content, (
            "handler_transition.py should contain SET status clause "
            "as it is the authorized status update handler."
        )

    def test_scan_directories_exist(self) -> None:
        """Verify at least some scan directories exist.

        This sanity check ensures we're actually scanning meaningful directories.
        If no directories exist, the audit would silently pass.
        """
        project_root = _get_project_root()
        existing_dirs = [d for d in SCAN_DIRS if (project_root / d).exists()]

        assert len(existing_dirs) >= 1, (
            f"None of the configured scan directories exist.\n"
            f"Expected directories: {SCAN_DIRS}\n"
            f"Project root: {project_root}\n"
            "This may indicate a misconfiguration or directory structure change."
        )
