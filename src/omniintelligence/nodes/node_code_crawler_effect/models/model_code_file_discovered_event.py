# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Wire event model for code file discovery.

Emitted by node_code_crawler_effect when a Python source file is discovered
during a filesystem crawl. Downstream consumers (e.g., AST extraction) subscribe
to code-file-discovered.v1 events.

Ticket: OMN-5658
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelCodeFileDiscoveredEvent(BaseModel):
    """Event emitted when a Python source file is discovered during a crawl.

    Published to: onex.evt.omniintelligence.code-file-discovered.v1

    Attributes:
        event_id: Unique event identifier (UUID).
        crawl_id: Batch identifier grouping all events from a single crawl run.
        repo_name: Name of the repository being crawled.
        file_path: Path relative to the repository root.
        file_hash: SHA-256 hex digest of the file content.
        file_size_bytes: Size of the file in bytes.
        timestamp: When the file was discovered.
        contract_version: Version of this event schema.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    event_id: str = Field(description="UUID identifying this event")
    crawl_id: str = Field(description="Batch identifier for the crawl run")
    repo_name: str = Field(description="Name of the repository")
    file_path: str = Field(description="Relative path from repo root")
    file_hash: str = Field(description="SHA-256 hex digest of file content")
    file_size_bytes: int = Field(description="File size in bytes")
    timestamp: datetime = Field(description="When the file was discovered")
    contract_version: str = Field(default="1.0.0", description="Event schema version")


__all__ = ["ModelCodeFileDiscoveredEvent"]
