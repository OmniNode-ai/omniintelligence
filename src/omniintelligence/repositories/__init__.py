"""Repository contracts for omniintelligence.

This module contains YAML contract files defining database repository
operations. Contracts are loaded and executed by PostgresRepositoryRuntime
from omnibase_infra.

Contract files:
- learned_patterns.repository.yaml: Operations for learned_patterns table
"""

from pathlib import Path

REPOSITORY_DIR = Path(__file__).parent

__all__ = ["REPOSITORY_DIR"]
