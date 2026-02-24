# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""EnforcementMode enum for the Code Intelligence Review Bot rollout system.

Controls how review findings affect CI across three phases:
- OBSERVE: Silent mode; CI always passes; no comments posted
- WARN: Visible mode; CI always passes; inline comments posted
- BLOCK: Gate mode; CI fails on BLOCKER findings; comments posted

OMN-2500: Implement OBSERVE -> WARN -> BLOCK rollout progression.
"""

from __future__ import annotations

from enum import Enum


class EnforcementMode(str, Enum):
    """Three-phase enforcement mode for the Code Intelligence Review Bot.

    Phase progression is always manual (human decision). The system tracks
    readiness signals but never auto-promotes.

    | Mode    | CI Result        | Comment Posted | Block on BLOCKER |
    |---------|-----------------|----------------|-----------------|
    | OBSERVE | Always pass      | No             | No              |
    | WARN    | Always pass      | Yes            | No              |
    | BLOCK   | Fail on BLOCKER  | Yes            | Yes             |
    """

    OBSERVE = "OBSERVE"
    WARN = "WARN"
    BLOCK = "BLOCK"

    @classmethod
    def from_policy_string(cls, value: str) -> EnforcementMode:
        """Parse a policy YAML enforcement_mode string.

        Accepts both uppercase and lowercase values for compatibility
        with existing policy YAML files that use lowercase strings
        (observe, warn, block).

        Args:
            value: The string value from policy YAML.

        Returns:
            The corresponding EnforcementMode.

        Raises:
            ValueError: If the value is not a valid enforcement mode.
        """
        normalized = value.upper()
        try:
            return cls(normalized)
        except ValueError:
            valid = sorted(m.value for m in cls)
            raise ValueError(
                f"Invalid enforcement_mode: {value!r}. Must be one of: {valid}"
            ) from None

    @property
    def posts_comments(self) -> bool:
        """True if this mode posts inline PR comments."""
        return self in (EnforcementMode.WARN, EnforcementMode.BLOCK)

    @property
    def blocks_on_blocker(self) -> bool:
        """True if this mode fails CI on BLOCKER findings."""
        return self is EnforcementMode.BLOCK

    @property
    def ci_always_passes(self) -> bool:
        """True if this mode never causes CI to fail."""
        return self in (EnforcementMode.OBSERVE, EnforcementMode.WARN)


__all__ = ["EnforcementMode"]
