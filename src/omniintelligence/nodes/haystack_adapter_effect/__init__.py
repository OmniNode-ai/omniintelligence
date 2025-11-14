"""
Haystack Adapter Effect Node

Adapts Haystack RAG pipelines for the ONEX architecture.
"""

from .v1_0_0 import (
    HaystackAdapterEffect,
    ModelHaystackAdapterInput,
    ModelHaystackAdapterOutput,
    ModelHaystackAdapterConfig,
)

__version__ = "1.0.0"

__all__ = [
    "HaystackAdapterEffect",
    "ModelHaystackAdapterInput",
    "ModelHaystackAdapterOutput",
    "ModelHaystackAdapterConfig",
]
