"""
Pattern Analytics API

Provides REST endpoints for pattern success rate tracking and analytics reporting.
Part of MVP Phase 5A - Intelligence Features Enhancement.
"""

from src.api.pattern_analytics.routes import router

__all__ = ["router"]
