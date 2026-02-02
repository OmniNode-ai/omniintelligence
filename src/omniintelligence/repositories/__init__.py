"""Repository contracts for omniintelligence.

This module contains YAML contract files defining database repository
operations. Contracts are loaded and executed by PostgresRepositoryRuntime
from omnibase_infra.

Contract files:
- learned_patterns.repository.yaml: Operations for learned_patterns table

Adapters:
- AdapterPatternStore: Bridges PostgresRepositoryRuntime to ProtocolPatternStore
"""

from pathlib import Path

from omniintelligence.repositories.adapter_pattern_store import (
    AdapterPatternStore,
    create_pattern_store_adapter,
    load_contract,
)

REPOSITORY_DIR = Path(__file__).parent

__all__ = [
    "REPOSITORY_DIR",
    "AdapterPatternStore",
    "create_pattern_store_adapter",
    "load_contract",
]
