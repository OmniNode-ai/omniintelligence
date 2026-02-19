"""ModelWhitelistEntry - a single whitelist entry for a file or pattern."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelWhitelistEntry:
    """A single whitelist entry for a file or pattern.

    Attributes:
        path: File path or glob pattern.
        reason: Documented reason for the exception.
        allowed_rules: List of rule IDs allowed for this file.
    """

    path: str
    reason: str
    allowed_rules: list[str] = field(default_factory=list)
