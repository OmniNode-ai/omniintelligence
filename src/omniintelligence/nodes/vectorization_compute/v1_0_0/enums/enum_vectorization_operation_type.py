"""
Operation types for Vectorization Compute Node
"""

from enum import Enum


class EnumVectorizationOperationType(str, Enum):
    """Operation types supported by vectorization compute node."""

    VECTORIZE = "VECTORIZE"                    # Single content vectorization
    BATCH_VECTORIZE = "BATCH_VECTORIZE"        # Batch vectorization
    VALIDATE_MODEL = "VALIDATE_MODEL"          # Validate embedding model
    HEALTH_CHECK = "HEALTH_CHECK"              # Health check operation

    def is_computational(self) -> bool:
        """Check if operation is computational."""
        return self in {
            EnumVectorizationOperationType.VECTORIZE,
            EnumVectorizationOperationType.BATCH_VECTORIZE,
        }

    def is_system(self) -> bool:
        """Check if operation is a system operation."""
        return self in {
            EnumVectorizationOperationType.VALIDATE_MODEL,
            EnumVectorizationOperationType.HEALTH_CHECK,
        }
