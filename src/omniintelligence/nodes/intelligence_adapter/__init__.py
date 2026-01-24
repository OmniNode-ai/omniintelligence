"""Intelligence Adapter Effect Node.

This module exports the declarative effect node for code analysis.
The node follows the ONEX pattern where all routing logic is defined
in contract.yaml and executed by the runtime.

Migration Note (OMN-1437):
    The original 2397-line monolith has been replaced with a ~140-line
    declarative shell. Event payload models are in omniintelligence.models.events,
    enums in omniintelligence.enums.enum_code_analysis, and handlers in
    the handlers/ subpackage.
"""

from omniintelligence.nodes.intelligence_adapter.node import (
    NodeIntelligenceAdapterEffect,
)

__all__ = ["NodeIntelligenceAdapterEffect"]
