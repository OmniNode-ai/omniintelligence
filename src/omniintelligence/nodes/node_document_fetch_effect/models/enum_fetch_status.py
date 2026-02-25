# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Fetch status enum for DocumentFetchEffect.

Ticket: OMN-2389
"""

from __future__ import annotations

from enum import Enum


class EnumFetchStatus(str, Enum):
    """Result status for a document fetch operation.

    Attributes:
        SUCCESS: Content fetched successfully.
        FILE_NOT_FOUND: Source file was not found at fetch time.
            A document.removed.v1 event is emitted in this case.
        GIT_SHA_UNAVAILABLE: Git SHA resolution failed; content still returned
            but source_version is None.
        FETCH_FAILED: Unrecoverable fetch error after retries (dead-lettered).
    """

    SUCCESS = "success"
    FILE_NOT_FOUND = "file_not_found"
    GIT_SHA_UNAVAILABLE = "git_sha_unavailable"
    FETCH_FAILED = "fetch_failed"


__all__ = ["EnumFetchStatus"]
