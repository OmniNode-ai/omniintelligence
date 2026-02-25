# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelInlinePragma - parsed inline pragma comment."""

from __future__ import annotations

from dataclasses import dataclass

from omniintelligence.audit.enum_io_audit_rule import EnumIOAuditRule


@dataclass
class ModelInlinePragma:
    """Represents a parsed inline pragma comment.

    Attributes:
        rule: The rule being whitelisted.
        scope: The scope of the pragma (e.g., "next-line").
        line: The line number where the pragma appears.
    """

    rule: EnumIOAuditRule
    scope: str
    line: int
