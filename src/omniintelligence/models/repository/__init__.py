"""Repository models for contract-driven database access.

These models are used by the PostgresRepositoryRuntime to map database rows
to typed Python objects. They are referenced by repository contract YAML files.
"""

from omniintelligence.models.repository.model_learned_pattern_row import (
    ModelLearnedPatternRow,
)
from omniintelligence.models.repository.model_pattern_for_injection import (
    ModelPatternForInjection,
)
from omniintelligence.models.repository.model_pattern_summary import (
    ModelPatternSummary,
)
from omniintelligence.models.repository.model_scalar_results import (
    ModelExistsResult,
    ModelIdResult,
    ModelTimestampResult,
    ModelVersionResult,
)

__all__ = [
    "ModelExistsResult",
    "ModelIdResult",
    "ModelLearnedPatternRow",
    "ModelPatternForInjection",
    "ModelPatternSummary",
    "ModelTimestampResult",
    "ModelVersionResult",
]
