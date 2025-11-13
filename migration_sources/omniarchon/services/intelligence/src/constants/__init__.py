"""
Constants package for centralized configuration values.

Exports:
    - MemgraphLabels: Canonical node label enum
    - MemgraphRelationships: Canonical relationship type enum
    - LABEL_* constants: Individual label constants for quick access
"""

from .memgraph_labels import (
    LABEL_CONCEPT,
    LABEL_DIRECTORY,
    LABEL_DOMAIN,
    LABEL_ENTITY,
    LABEL_FILE,
    LABEL_ONEX_TYPE,
    LABEL_PROJECT,
    LABEL_THEME,
    MemgraphLabels,
    MemgraphRelationships,
    validate_label,
)

__all__ = [
    # Enums
    "MemgraphLabels",
    "MemgraphRelationships",
    # Individual label constants
    "LABEL_FILE",
    "LABEL_PROJECT",
    "LABEL_DIRECTORY",
    "LABEL_ENTITY",
    "LABEL_CONCEPT",
    "LABEL_THEME",
    "LABEL_ONEX_TYPE",
    "LABEL_DOMAIN",
    # Utilities
    "validate_label",
]
