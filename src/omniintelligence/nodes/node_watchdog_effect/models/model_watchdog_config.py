# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""ModelWatchdogConfig — configurable paths and settings for WatchdogEffect.

All watched paths and polling intervals are configurable (not hardcoded)
per the ticket DoD.  Default values match the design doc:
    omni_save/design/DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §4

Reference: OMN-2386
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Default polling interval in seconds for the fallback observer
_DEFAULT_POLLING_INTERVAL_SECONDS: int = 5

# File suffixes/names that are always skipped (editor swap files, temps)
_DEFAULT_IGNORED_SUFFIXES: frozenset[str] = frozenset(
    {
        ".swp",
        ".swo",
        ".tmp",
        ".bak",
        "~",
    }
)


def _default_watched_paths() -> list[str]:
    """Build default watched paths from the design doc §4.

    Returns absolute paths after expanding ``~``.  The home directory is
    expanded at call time so tests can override HOME if needed.
    """
    home = Path.home()
    paths = [
        str(home / ".claude"),
    ]
    return paths


class ModelWatchdogConfig(BaseModel):
    """Configuration for WatchdogEffect watched paths and observer settings.

    Attributes:
        watched_paths: Absolute paths to watch recursively.  Relative paths
            are rejected at validation time.
        polling_interval_seconds: Interval between polls for the fallback
            polling observer.  Ignored when a native observer is used.
        ignored_suffixes: File suffixes (including the leading dot) and exact
            filenames that should be silently skipped when changed.
        crawl_scope: Logical crawl scope emitted in crawl-requested.v1 events.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    watched_paths: list[str] = Field(
        default_factory=_default_watched_paths,
        description=(
            "Absolute directory paths to watch recursively for file changes.  "
            "Defaults to ``~/.claude/`` per the design doc §4."
        ),
    )

    polling_interval_seconds: int = Field(
        default=_DEFAULT_POLLING_INTERVAL_SECONDS,
        ge=1,
        description=(
            "Polling interval in seconds for the fallback polling observer.  "
            "Ignored when a native FSEvents or inotify observer is active."
        ),
    )

    ignored_suffixes: frozenset[str] = Field(
        default=_DEFAULT_IGNORED_SUFFIXES,
        description=(
            "File suffixes (e.g. '.swp') and exact filenames (e.g. '~') that "
            "are silently skipped when a change event arrives.  "
            "The comparison is suffix-based: ``path.endswith(suffix)``."
        ),
    )

    crawl_scope: str = Field(
        default="omninode/shared/global-standards",
        description="Logical crawl scope emitted in crawl-requested.v1 events.",
    )

    @field_validator("watched_paths", mode="before")
    @classmethod
    def expand_and_validate_paths(cls, v: list[str]) -> list[str]:
        """Expand ``~`` and validate that all paths are absolute.

        Raises:
            ValueError: If any path is not absolute after ``~`` expansion.
        """
        expanded = []
        for raw in v:
            path = os.path.expanduser(raw)
            if not os.path.isabs(path):
                raise ValueError(
                    f"watched_paths must be absolute after ~ expansion. Got: {raw!r}"
                )
            expanded.append(path)
        return expanded

    def is_ignored(self, file_path: str) -> bool:
        """Return True if the file should be silently skipped.

        Args:
            file_path: Absolute path of the changed file.

        Returns:
            True if any configured ignored suffix matches the path.
        """
        return any(file_path.endswith(suffix) for suffix in self.ignored_suffixes)


__all__ = ["ModelWatchdogConfig"]
