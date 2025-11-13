"""
Common models and contracts for services.

Re-exports frequently used models to avoid deep import paths.
"""

from src.archon_services.pattern_learning.phase1_foundation.storage.model_contract_pattern_storage import (
    ModelResult,
)

__all__ = ["ModelResult"]
