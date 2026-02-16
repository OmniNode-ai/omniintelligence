"""REST API for OmniIntelligence pattern queries.

This package provides FastAPI routers for querying the pattern store.
Routers are mounted by the application entrypoint or RuntimeHostProcess.

Ticket: OMN-2253
"""

from omniintelligence.api.router_patterns import create_pattern_router

__all__ = [
    "create_pattern_router",
]
