"""
Intelligence Events API

Provides real-time event stream endpoints for the Pattern Dashboard Event Flow page.
"""

from src.api.intelligence_events.routes import router

__all__ = ["router"]
