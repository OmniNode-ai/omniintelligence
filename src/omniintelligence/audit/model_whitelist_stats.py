# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelWhitelistStats - statistics about whitelist application for a file."""

from __future__ import annotations

from dataclasses import dataclass

from omniintelligence.audit.model_io_audit_violation import ModelIOAuditViolation


@dataclass
class ModelWhitelistStats:
    """Statistics about whitelist application for a file.

    Attributes:
        remaining: Violations remaining after whitelisting.
        yaml_count: Number of violations whitelisted by YAML rules.
        pragma_count: Number of violations whitelisted by inline pragmas.
    """

    remaining: list[ModelIOAuditViolation]
    yaml_count: int = 0
    pragma_count: int = 0
