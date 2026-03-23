# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Review-Fix Pairing subsystem for OmniIntelligence.

This package provides the canonical event contracts, Pydantic models, and
Postgres schema migration for the Review-Fix Pairing and Pattern Reinforcement
system (OMN-2353).

Public API:
    models — All four canonical event contracts plus the pairing model.
    topics — Kafka topic registry for review-pairing events.
    models_calibration — Calibration config, metrics, and result models.
    alignment_engine — Finding alignment via embedding + lexical similarity.
    calibration_scorer — Precision/recall/F1/noise scoring.
    calibration_orchestrator — End-to-end calibration pipeline.
    calibration_persistence — EMA persistence for calibration runs.
    fewshot_extractor — Few-shot example extraction from alignments.
    prompt_writer — Prompt assembly from few-shot examples.
    serializer_r1r6 — Finding serializers for R1/R6 review formats.
"""

from omniintelligence.review_pairing.alignment_engine import FindingAlignmentEngine
from omniintelligence.review_pairing.calibration_orchestrator import (
    CalibrationOrchestrator,
)
from omniintelligence.review_pairing.calibration_persistence import (
    CalibrationPersistence,
)
from omniintelligence.review_pairing.calibration_scorer import CalibrationScorer
from omniintelligence.review_pairing.fewshot_extractor import FewShotExtractor
from omniintelligence.review_pairing.models import (
    FindingFixPair,
    ReviewFindingObserved,
    ReviewFindingResolved,
    ReviewFixApplied,
)
from omniintelligence.review_pairing.models_calibration import (
    CalibrationConfig,
    CalibrationFindingTuple,
    CalibrationMetrics,
    CalibrationOrchestrationResult,
    CalibrationRunCompletedEvent,
    CalibrationRunResult,
    FewShotExample,
    FindingAlignment,
)
from omniintelligence.review_pairing.prompt_writer import PromptWriter
from omniintelligence.review_pairing.serializer_r1r6 import (
    serialize_external_finding,
    serialize_merged_finding,
    serialize_plan_finding,
)

__all__ = [
    # Review-Fix Pairing models
    "FindingFixPair",
    "ReviewFindingObserved",
    "ReviewFindingResolved",
    "ReviewFixApplied",
    # Calibration models
    "CalibrationConfig",
    "CalibrationFindingTuple",
    "CalibrationMetrics",
    "CalibrationOrchestrationResult",
    "CalibrationRunCompletedEvent",
    "CalibrationRunResult",
    "FewShotExample",
    "FindingAlignment",
    # Calibration engines and services
    "CalibrationOrchestrator",
    "CalibrationPersistence",
    "CalibrationScorer",
    "FewShotExtractor",
    "FindingAlignmentEngine",
    "PromptWriter",
    # Serializers
    "serialize_external_finding",
    "serialize_merged_finding",
    "serialize_plan_finding",
]
