"""Domain models shared across omniintelligence.

This module contains core domain models that are used across multiple nodes
and modules. Moving these here breaks circular import chains.
"""

from omniintelligence.models.domain.model_gate_snapshot import ModelGateSnapshot

__all__ = ["ModelGateSnapshot"]
