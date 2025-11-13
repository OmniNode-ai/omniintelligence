"""
Shared Logging Infrastructure for Archon Services

Provides unified correlation tracking and logging utilities
across all Archon microservices.
"""

from .pipeline_correlation import (
    CorrelationHeaders,
    PipelineCorrelation,
    create_pipeline_headers,
    get_pipeline_correlation,
    global_pipeline_correlation,
)

__all__ = [
    "PipelineCorrelation",
    "CorrelationHeaders",
    "global_pipeline_correlation",
    "get_pipeline_correlation",
    "create_pipeline_headers",
]
