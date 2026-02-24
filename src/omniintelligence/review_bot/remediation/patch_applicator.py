"""Patch applicator for the Code Intelligence Review Bot.

Safely applies git diff patches from ReviewFinding objects.
Only applies patches for safe refactor types from the allowlist.

OMN-2498: Implement auto-remediation pipeline.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum


class SafeRefactorType(str, Enum):
    """Safe refactor types eligible for auto-remediation.

    Only these types may be auto-applied without human semantic review.
    """

    TYPE_COMPLETER = "type_completer"
    FORMATTER = "formatter"
    IMPORT_SORT = "import_sort"
    TRIVIAL_RENAME = "trivial_rename"


# The complete allowlist of safe refactor types
SAFE_REFACTOR_ALLOWLIST = frozenset(t.value for t in SafeRefactorType)


@dataclass
class PatchResult:
    """Result of attempting to apply a patch.

    Attributes:
        success: True if the patch was applied successfully.
        patch_content: The patch that was applied.
        error: Error message if the patch failed, else None.
    """

    success: bool
    patch_content: str
    error: str | None = None


class PatchApplicator:
    """Applies git diff patches safely in an isolated working directory.

    Only patches with a safe refactor type are eligible. All others
    are silently skipped.

    Usage::

        applicator = PatchApplicator(work_dir="/path/to/repo")
        result = applicator.apply_patch(patch_content)
        if not result.success:
            print(f"Patch failed: {result.error}")
    """

    def __init__(self, work_dir: str = ".") -> None:
        self._work_dir = work_dir

    def is_safe_refactor_type(self, refactor_type: str | None) -> bool:
        """Check if a refactor type is in the safe allowlist.

        Args:
            refactor_type: The refactor type string to check.

        Returns:
            True if the type is safe for auto-application.
        """
        if refactor_type is None:
            return False
        return refactor_type in SAFE_REFACTOR_ALLOWLIST

    def apply_patch(self, patch_content: str) -> PatchResult:
        """Apply a git diff patch using git apply.

        Args:
            patch_content: Git unified diff patch string.

        Returns:
            PatchResult indicating success or failure.
        """
        if not patch_content.strip():
            return PatchResult(
                success=False,
                patch_content=patch_content,
                error="Empty patch content",
            )

        try:
            proc = subprocess.run(
                ["git", "apply", "--check", "-"],
                input=patch_content,
                text=True,
                capture_output=True,
                cwd=self._work_dir,
                check=False,
            )
            if proc.returncode != 0:
                return PatchResult(
                    success=False,
                    patch_content=patch_content,
                    error=f"Patch would not apply cleanly: {proc.stderr.strip()}",
                )

            # Actually apply
            apply_proc = subprocess.run(
                ["git", "apply", "-"],
                input=patch_content,
                text=True,
                capture_output=True,
                cwd=self._work_dir,
                check=False,
            )
            if apply_proc.returncode != 0:
                return PatchResult(
                    success=False,
                    patch_content=patch_content,
                    error=f"Patch application failed: {apply_proc.stderr.strip()}",
                )

            return PatchResult(success=True, patch_content=patch_content)

        except OSError as exc:
            return PatchResult(
                success=False,
                patch_content=patch_content,
                error=f"OS error applying patch: {exc}",
            )


__all__ = [
    "SAFE_REFACTOR_ALLOWLIST",
    "PatchApplicator",
    "PatchResult",
    "SafeRefactorType",
]
