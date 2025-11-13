"""
Pattern Learning Engine

Phase 1: Foundation - Task characteristics extraction and pattern matching.
Phase 2: Codegen integration - Pattern matching and mixin recommendations.
"""

from uuid import UUID, uuid4

from src.archon_services.pattern_learning.codegen_pattern_service import (
    CodegenPatternService,
)

__version__ = "0.1.0"

__all__ = ["CodegenPatternService"]
