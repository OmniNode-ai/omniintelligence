"""
Developer Metrics API Module

Provides developer experience and productivity metrics.
"""

from src.api.developer_metrics.routes import initialize_services, router

__all__ = ["router", "initialize_services"]
