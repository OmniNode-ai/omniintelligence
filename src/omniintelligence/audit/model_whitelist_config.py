# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelWhitelistConfig - complete whitelist configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from omniintelligence.audit.model_whitelist_entry import ModelWhitelistEntry


@dataclass
class ModelWhitelistConfig:
    """Complete whitelist configuration.

    Attributes:
        files: List of whitelisted file entries.
        schema_version: Version of the whitelist schema.
    """

    files: list[ModelWhitelistEntry] = field(default_factory=list)
    schema_version: str = "1.0.0"
