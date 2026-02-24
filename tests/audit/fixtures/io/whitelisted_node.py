# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A node with whitelisted violations for testing whitelist functionality.

This fixture tests:
- Central YAML whitelist (file-level)
- Inline pragma whitelist (line-level)
"""

import os
from pathlib import Path


def get_debug_config() -> dict[str, str]:
    """This violation is whitelisted via YAML config."""
    # This os.getenv should be whitelisted via YAML
    debug_mode = os.getenv("DEBUG_MODE", "false")
    return {"debug": debug_mode}


def read_local_debug_file(path: Path) -> str:
    """This violation uses inline pragma."""
    # io-audit: ignore-next-line file-io
    return path.read_text()


def get_unwhitelisted_env() -> str:
    """This violation is NOT whitelisted and should fail."""
    # This should still be caught as a violation
    return os.getenv("NOT_WHITELISTED", "default")
