# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Fixture file reads for retrieval replay (I/O boundary kept out of compute nodes)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def read_fixture_bytes(source_path: Path) -> bytes:
    """Return the raw bytes of one fixture file."""

    return source_path.read_bytes()


class HandlerReadFixtureBytes:
    """Contract-bound handler for ``read_fixture_bytes``."""

    def __init__(self, **dependencies: Any) -> None:
        self._dependencies = dependencies

    def handle(self, request: Path) -> bytes:
        return read_fixture_bytes(request, **self._dependencies)
