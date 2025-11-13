"""
Phase 1 Foundation - Task Characteristics Extraction

Core components for extracting and analyzing task characteristics
for autonomous agent selection and pattern matching.
"""

from uuid import UUID, uuid4

from src.archon_services.pattern_learning.phase1_foundation.models.model_task_characteristics import (
    EnumChangeScope,
    EnumComplexity,
    EnumTaskType,
    ModelTaskCharacteristics,
    ModelTaskCharacteristicsInput,
    ModelTaskCharacteristicsOutput,
)
from src.archon_services.pattern_learning.phase1_foundation.node_task_characteristics_extractor_compute import (
    NodeTaskCharacteristicsExtractorCompute,
)

__all__ = [
    "EnumTaskType",
    "EnumComplexity",
    "EnumChangeScope",
    "ModelTaskCharacteristics",
    "ModelTaskCharacteristicsInput",
    "ModelTaskCharacteristicsOutput",
    "NodeTaskCharacteristicsExtractorCompute",
]
