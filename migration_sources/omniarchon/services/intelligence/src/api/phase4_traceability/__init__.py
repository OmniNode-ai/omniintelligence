"""
Phase 4 Pattern Traceability API Package

Provides FastAPI routes for:
- Pattern lineage tracking
- Usage analytics computation
- Feedback loop orchestration
"""

from src.api.phase4_traceability.routes import router

__all__ = ["router"]
