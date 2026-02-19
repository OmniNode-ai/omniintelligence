"""Domain models shared across omniintelligence.

This module contains core domain models that are used across multiple nodes
and modules. Moving these here breaks circular import chains.
"""

from omniintelligence.models.domain.enum_run_result import EnumRunResult
from omniintelligence.models.domain.model_gate_snapshot import (
    EvidenceTierLiteral,
    ModelGateSnapshot,
)

__all__ = ["EnumRunResult", "EvidenceTierLiteral", "ModelGateSnapshot"]
