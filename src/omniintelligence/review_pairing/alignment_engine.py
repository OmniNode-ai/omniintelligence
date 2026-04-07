# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Finding Alignment Engine for calibration.

Aligns ground-truth findings with challenger findings using composite
similarity scoring and Hungarian algorithm for optimal matching.

Reference: OMN-6167
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

import numpy as np
from scipy.optimize import linear_sum_assignment

from omniintelligence.review_pairing.models_calibration import (
    ModelCalibrationFindingTuple,
    ModelFindingAlignment,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class EmbeddingClientProtocol(Protocol):
    """Protocol for embedding clients used by the alignment engine."""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts and return embedding vectors."""
        ...


class FindingAlignmentEngine:
    """Aligns ground-truth findings with challenger findings.

    Uses composite similarity scoring:
    - 0.2 * category_sim
    - 0.1 * location_sim
    - 0.7 * description_sim

    Optimal matching via Hungarian algorithm (scipy.optimize.linear_sum_assignment).

    Args:
        similarity_threshold: Minimum composite score for a match.
        embedding_client: Optional embedding client for description similarity.
            Falls back to Jaccard similarity when None.
        category_families: Maps family names to related category lists
            for fuzzy category matching.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.7,
        embedding_client: EmbeddingClientProtocol | None = None,
        category_families: dict[str, list[str]] | None = None,
    ) -> None:
        self._threshold = similarity_threshold
        self._embedding_client = embedding_client
        self._category_families = category_families or {}
        self._category_to_family: dict[str, str] = {}
        for family, categories in self._category_families.items():
            for cat in categories:
                self._category_to_family[cat] = family

    async def align(
        self,
        ground_truth: list[ModelCalibrationFindingTuple],
        challenger: list[ModelCalibrationFindingTuple],
    ) -> list[ModelFindingAlignment]:
        """Align ground-truth findings with challenger findings.

        Args:
            ground_truth: Findings from the reference model.
            challenger: Findings from the challenger model.

        Returns:
            List of ModelFindingAlignment records covering all findings.
        """
        if not ground_truth and not challenger:
            return []

        if not ground_truth:
            return [
                ModelFindingAlignment(
                    ground_truth=None,
                    challenger=ch,
                    similarity_score=0.0,
                    aligned=False,
                    alignment_type="false_positive",
                    embedding_model_version=self._get_model_version(),
                )
                for ch in challenger
            ]

        if not challenger:
            return [
                ModelFindingAlignment(
                    ground_truth=gt,
                    challenger=None,
                    similarity_score=0.0,
                    aligned=False,
                    alignment_type="false_negative",
                    embedding_model_version=self._get_model_version(),
                )
                for gt in ground_truth
            ]

        sim_matrix = await self._build_similarity_matrix(ground_truth, challenger)

        cost_matrix = 1.0 - sim_matrix
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        matched_gt: set[int] = set()
        matched_ch: set[int] = set()
        alignments: list[ModelFindingAlignment] = []

        for r, c in zip(row_ind, col_ind, strict=True):
            score = float(sim_matrix[r, c])
            if score >= self._threshold:
                alignments.append(
                    ModelFindingAlignment(
                        ground_truth=ground_truth[r],
                        challenger=challenger[c],
                        similarity_score=score,
                        aligned=True,
                        alignment_type="true_positive",
                        embedding_model_version=self._get_model_version(),
                    )
                )
                matched_gt.add(r)
                matched_ch.add(c)

        for i, gt in enumerate(ground_truth):
            if i not in matched_gt:
                alignments.append(
                    ModelFindingAlignment(
                        ground_truth=gt,
                        challenger=None,
                        similarity_score=0.0,
                        aligned=False,
                        alignment_type="false_negative",
                        embedding_model_version=self._get_model_version(),
                    )
                )

        for j, ch in enumerate(challenger):
            if j not in matched_ch:
                alignments.append(
                    ModelFindingAlignment(
                        ground_truth=None,
                        challenger=ch,
                        similarity_score=0.0,
                        aligned=False,
                        alignment_type="false_positive",
                        embedding_model_version=self._get_model_version(),
                    )
                )

        return alignments

    async def _build_similarity_matrix(
        self,
        ground_truth: list[ModelCalibrationFindingTuple],
        challenger: list[ModelCalibrationFindingTuple],
    ) -> np.ndarray:
        """Build NxM composite similarity matrix."""
        n = len(ground_truth)
        m = len(challenger)

        desc_sims = await self._description_similarities(
            [gt.description for gt in ground_truth],
            [ch.description for ch in challenger],
        )

        matrix = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                cat_sim = self._category_similarity(
                    ground_truth[i].category, challenger[j].category
                )
                loc_sim = self._location_similarity(
                    ground_truth[i].location, challenger[j].location
                )
                desc_sim = desc_sims[i][j]
                matrix[i, j] = 0.2 * cat_sim + 0.1 * loc_sim + 0.7 * desc_sim

        return matrix

    def _category_similarity(self, a: str, b: str) -> float:
        """Compute category similarity: 1.0 exact, 0.5 same family, 0.0 otherwise."""
        if a == b:
            return 1.0
        family_a = self._category_to_family.get(a)
        family_b = self._category_to_family.get(b)
        if family_a is not None and family_a == family_b:
            return 0.5
        return 0.0

    def _location_similarity(self, a: str | None, b: str | None) -> float:
        """Compute location similarity: 1.0 if match/substring, 0.0 otherwise."""
        if a is None and b is None:
            return 1.0
        if a is None or b is None:
            return 0.0
        if a == b:
            return 1.0
        if a in b or b in a:
            return 1.0
        return 0.0

    async def _description_similarities(
        self,
        gt_descs: list[str],
        ch_descs: list[str],
    ) -> list[list[float]]:
        """Compute description similarity matrix.

        Uses embedding client if available, falls back to Jaccard.
        """
        if self._embedding_client is not None:
            return await self._embedding_description_similarities(gt_descs, ch_descs)
        return self._jaccard_description_similarities(gt_descs, ch_descs)

    async def _embedding_description_similarities(
        self,
        gt_descs: list[str],
        ch_descs: list[str],
    ) -> list[list[float]]:
        """Compute cosine similarity using embeddings."""
        assert self._embedding_client is not None
        all_texts = gt_descs + ch_descs
        embeddings = await self._embedding_client.embed_batch(all_texts)

        gt_embs = embeddings[: len(gt_descs)]
        ch_embs = embeddings[len(gt_descs) :]

        result: list[list[float]] = []
        for gt_emb in gt_embs:
            row: list[float] = []
            for ch_emb in ch_embs:
                row.append(_cosine_similarity(gt_emb, ch_emb))
            result.append(row)
        return result

    def _jaccard_description_similarities(
        self,
        gt_descs: list[str],
        ch_descs: list[str],
    ) -> list[list[float]]:
        """Compute Jaccard similarity for all pairs."""
        result: list[list[float]] = []
        for gt in gt_descs:
            row: list[float] = []
            for ch in ch_descs:
                row.append(_jaccard_similarity(gt, ch))
            result.append(row)
        return result

    def _get_model_version(self) -> str:
        """Return the embedding model version identifier."""
        if self._embedding_client is not None:
            return "embedding-client"
        return "jaccard-v1"


def _jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity on word tokens."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    arr_a = np.array(a)
    arr_b = np.array(b)
    dot = float(np.dot(arr_a, arr_b))
    norm_a = float(np.linalg.norm(arr_a))
    norm_b = float(np.linalg.norm(arr_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
