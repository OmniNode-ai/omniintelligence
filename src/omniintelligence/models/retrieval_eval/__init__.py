# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Models of the offline retrieval-quality eval harness (OMN-16522).

The golden query set, the ranking metrics, the baseline scorecard and the
per-stage latency sample, with the two committed JSON baselines they describe
under ``baselines/``.  The replay state and the runner that produce them stay in
``omniintelligence.code_projection.retrieval_eval``.
"""

from omniintelligence.models.retrieval_eval.model_golden_query_set import (
    GOLDEN_QUERY_SET_PATH,
    ModelGoldenQuerySet,
    load_golden_query_set,
)
from omniintelligence.models.retrieval_eval.model_ranking_metrics import (
    ModelRankingMetrics,
    summarize_metrics,
)
from omniintelligence.models.retrieval_eval.model_scorecard import (
    BASELINE_SCORECARD_PATH,
    UNKNOWN,
    ModelEmbeddingCompatibilityKey,
    ModelLatencyReport,
    ModelScenarioOutcome,
    ModelScorecard,
)
from omniintelligence.models.retrieval_eval.model_stage_latency_sample import (
    ModelStageLatencySample,
)

__all__ = [
    "BASELINE_SCORECARD_PATH",
    "GOLDEN_QUERY_SET_PATH",
    "UNKNOWN",
    "ModelEmbeddingCompatibilityKey",
    "ModelGoldenQuerySet",
    "ModelLatencyReport",
    "ModelRankingMetrics",
    "ModelScenarioOutcome",
    "ModelScorecard",
    "ModelStageLatencySample",
    "load_golden_query_set",
    "summarize_metrics",
]
