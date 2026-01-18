"""Intelligence Reducer Node Package.

This module provides the legacy IntelligenceReducer class which handles
FSM-driven state management for intelligence operations.

Note: This is a legacy import. For new code, use the canonical nodes from
omniintelligence.nodes.intelligence_reducer instead.
"""

from omniintelligence._legacy.nodes.intelligence_reducer.v1_0_0.reducer import (
    IntelligenceReducer,
)

__all__ = [
    "IntelligenceReducer",
]
