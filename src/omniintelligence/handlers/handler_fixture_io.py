# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Fixture file reads for retrieval replay (I/O boundary kept out of compute nodes)."""

from __future__ import annotations

from pathlib import Path


def read_fixture_bytes(path: Path) -> bytes:
    """Return the raw bytes of one fixture file."""

    return path.read_bytes()
