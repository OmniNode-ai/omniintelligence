# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Baseline scorecard: the reference future PRs are compared against.

Two properties are in tension and are resolved by separating them.  The
scorecard must be **deterministic** -- two runs produce byte-identical output --
while per-stage latency is inherently variable.  So the committed scorecard
carries only deterministic content, and latency is emitted alongside it as a
sibling report that is explicitly excluded from the content digest.  A timing
that changed the baseline digest on every run would make the baseline useless
as a regression reference.

The scorecard also carries the five-part embedding-compatibility key.  Dimension
alone does not identify an embedding space: two models emitting 1024-dimensional
vectors produce two *different* spaces, and mixing them degrades retrieval with
no error and no shape mismatch.  Recording the key is what lets a future
scorecard diff distinguish "retrieval got worse" from "the embedding space
changed" -- the second is a reason to re-baseline, not a regression to report.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.code_projection._canonical import canonical_json_bytes
from omniintelligence.code_projection.retrieval_eval.metrics import ModelRankingMetrics
from omniintelligence.code_projection.retrieval_eval.replay import (
    ModelStageLatencySample,
)

#: Recorded in place of a value that cannot be sourced.  Never invent one: an
#: invented digest is worse than an absent one, because it reads as verified.
UNKNOWN = "unknown"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)


class ModelEmbeddingCompatibilityKey(_FrozenModel):
    """The five-part identity of an embedding space.

    Only ``dimension`` fails loudly on a mismatch; the other four drift
    silently, which is exactly why they are recorded rather than assumed.
    """

    model_name: str
    model_artifact_digest: str
    model_revision: str
    tokenizer_preprocessing_version: str
    normalization: str
    distance_metric: str
    dimension: int = Field(ge=1)

    @property
    def unknown_components(self) -> tuple[str, ...]:
        """Return which components could not be sourced from the platform."""

        candidates = {
            "model_artifact_digest": self.model_artifact_digest,
            "model_revision": self.model_revision,
            "tokenizer_preprocessing_version": self.tokenizer_preprocessing_version,
            "normalization": self.normalization,
            "distance_metric": self.distance_metric,
        }
        return tuple(
            sorted(name for name, value in candidates.items() if value == UNKNOWN)
        )


class ModelScenarioOutcome(_FrozenModel):
    """One replay-scenario assertion and whether it held."""

    scenario_id: str
    lane_id: str
    description: str
    passed: bool
    detail: str


class ModelScorecard(_FrozenModel):
    """The deterministic, committed baseline."""

    scorecard_version: str
    ticket: str
    corpus_manifest_id: str
    golden_set_version: str
    corpus_fixture_count: int = Field(ge=0)
    distinct_chunk_keys: tuple[str, ...]
    golden_query_ids: tuple[str, ...]
    assertion_count: int = Field(ge=0)
    metrics: ModelRankingMetrics
    embedding_compatibility_key: ModelEmbeddingCompatibilityKey
    unknown_embedding_components: tuple[str, ...]
    scenarios: tuple[ModelScenarioOutcome, ...]

    def to_canonical_bytes(self) -> bytes:
        """Return the byte-exact committed form: sorted keys, compact, one LF."""

        return canonical_json_bytes(self.model_dump(mode="json")) + b"\n"


class ModelLatencyReport(_FrozenModel):
    """Per-stage latency, deliberately NOT part of the scorecard digest.

    Only the embed call is separable from outside ``search()``.  Vector search,
    policy/provenance checks and pack assembly happen inside that one call with
    no instrumentation, so they are reported together rather than split by
    guesswork -- an invented per-stage split would be exactly the kind of
    fabricated number this harness exists to catch.
    """

    sample_count: int = Field(ge=0)
    embed_ms_total: float = Field(ge=0.0)
    total_ms_total: float = Field(ge=0.0)
    unseparated_remainder_ms_total: float = Field(ge=0.0)
    separable_stages: tuple[str, ...] = ("embed",)
    unseparable_stages: tuple[str, ...] = (
        "vector_search",
        "policy_provenance_checks",
        "pack_assembly",
    )
    note: str = (
        "Latency is excluded from the scorecard content digest because it is "
        "not reproducible byte-for-byte. The three unseparable stages are not "
        "individually instrumented inside CodeProjectionQdrantStore.search(); "
        "their combined cost is unseparated_remainder_ms_total."
    )

    @classmethod
    def from_samples(
        cls, samples: tuple[ModelStageLatencySample, ...]
    ) -> ModelLatencyReport:
        """Aggregate raw per-search samples into one report."""

        return cls(
            sample_count=len(samples),
            embed_ms_total=round(sum(s.embed_ms for s in samples), 3),
            total_ms_total=round(sum(s.total_ms for s in samples), 3),
            unseparated_remainder_ms_total=round(
                sum(s.unseparated_remainder_ms for s in samples), 3
            ),
        )


def render_scorecard(scorecard: ModelScorecard) -> str:
    """Return the scorecard as canonical JSON text."""

    return scorecard.to_canonical_bytes().decode("utf-8")


def load_scorecard(payload: bytes) -> ModelScorecard:
    """Parse a committed scorecard artifact."""

    return ModelScorecard.model_validate(json.loads(payload.decode("utf-8")))


MetricStatusLiteral = Literal["degenerate", "armed"]

__all__ = [
    "UNKNOWN",
    "ModelEmbeddingCompatibilityKey",
    "ModelLatencyReport",
    "ModelScenarioOutcome",
    "ModelScorecard",
    "load_scorecard",
    "render_scorecard",
]
