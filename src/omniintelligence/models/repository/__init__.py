"""Repository models for contract-driven database access.

These models are used by the PostgresRepositoryRuntime to map database rows
to typed Python objects. They are referenced by repository contract YAML files.
"""

from omniintelligence.models.repository.model_domain_candidate import (
    ModelDomainCandidate,
)
from omniintelligence.models.repository.model_exists_result import ModelExistsResult
from omniintelligence.models.repository.model_id_result import ModelIdResult
from omniintelligence.models.repository.model_learned_pattern_row import (
    ModelLearnedPatternRow,
)
from omniintelligence.models.repository.model_pattern_for_injection import (
    ModelPatternForInjection,
)
from omniintelligence.models.repository.model_pattern_summary import (
    ModelPatternSummary,
)
from omniintelligence.models.repository.model_timestamp_result import (
    ModelTimestampResult,
)
from omniintelligence.models.repository.model_version_result import ModelVersionResult

__all__ = [
    "ModelDomainCandidate",
    "ModelExistsResult",
    "ModelIdResult",
    "ModelLearnedPatternRow",
    "ModelPatternForInjection",
    "ModelPatternSummary",
    "ModelTimestampResult",
    "ModelVersionResult",
]
