# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node NavigationRetrieverEffect — RAG retrieval of prior navigation paths from OmniMemory.

NodeNavigationRetrieverEffect is lazily imported to avoid loading omnibase_core
at package import time (matching the pattern used across all other nodes in this package).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omniintelligence.nodes.node_navigation_retriever_effect.node import (
        NodeNavigationRetrieverEffect as NodeNavigationRetrieverEffect,
    )


def __getattr__(name: str) -> object:
    if name == "NodeNavigationRetrieverEffect":
        module = importlib.import_module(
            "omniintelligence.nodes.node_navigation_retriever_effect.node"
        )
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["NodeNavigationRetrieverEffect"]
