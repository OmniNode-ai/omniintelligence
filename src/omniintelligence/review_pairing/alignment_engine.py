# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Finding Alignment Engine for calibration.

Uses the Hungarian algorithm (scipy.optimize.linear_sum_assignment) to find
optimal one-to-one matching between ground-truth and challenger findings.

Reference: OMN-6167 (epic OMN-6164)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import linear_sum_assignment

from omniintelligence.review_pairing.models_calibration import (
    CalibrationFindingTuple,
    FindingAlignment,
)

if TYPE_CHECKING:
    from omniintelligence.clients.embedding_client_local_openai import (
        EmbeddingClientLocalOpenAI,
    )

logger = logging.getLogger(__name__)


class FindingAlignmentEngine:
    """Aligns ground-truth findings with challenger findings using composite similarity."""

    def __init__(
        self,
        similarity_threshold: float = 0.7,
        embedding_client: EmbeddingClientLocalOpenAI | None = None,
        category_families: dict[str, list[str]] | None = None,
    ) -> None:
        self._threshold = similarity_threshold
        self._embedding_client = embedding_client
        self._category_families = category_families or {}
        self._category_to_family: dict[str, str] = {}
        for family, members in self._category_families.items():
            for member in members:
                self._category_to_family[member.lower()] = family
        self._embedding_model_version: str | None = None

    async def align(
        self,
        ground_truth: list[CalibrationFindingTuple],
        challenger: list[CalibrationFindingTuple],
    ) -> list[FindingAlignment]:
        """Align ground-truth findings against challenger findings.

        Returns a list of FindingAlignment records covering all findings
        from both sides (true positives, false negatives, false positives).
        """
        if not ground_truth and not challenger:
            return []

        if not ground_truth:
            return [
                FindingAlignment(
                    ground_truth=None,
                    challenger=c,
                    similarity_score=0.0,
                    aligned=False,
                    alignment_type="false_positive",
                    embedding_model_version=self._embedding_model_version,
                )
                for c in challenger
            ]

        if not challenger:
            return [
                FindingAlignment(
                    ground_truth=g,
                    challenger=None,
                    similarity_score=0.0,
                    aligned=False,
                    alignment_type="false_negative",
                    embedding_model_version=self._embedding_model_version,
                )
                for g in ground_truth
            ]

        sim_matrix = await self._build_similarity_matrix(ground_truth, challenger)

        cost_matrix = 1.0 - sim_matrix
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        matched_gt: set[int] = set()
        matched_ch: set[int] = set()
        alignments: list[FindingAlignment] = []

        for gi, ci in zip(row_ind, col_ind, strict=True):
            score = float(sim_matrix[gi, ci])
            if score >= self._threshold:
                alignments.append(
                    FindingAlignment(
                        ground_truth=ground_truth[gi],
                        challenger=challenger[ci],
                        similarity_score=score,
                        aligned=True,
                        alignment_type="true_positive",
                        embedding_model_version=self._embedding_model_version,
                    )
                )
                matched_gt.add(gi)
                matched_ch.add(ci)

        for gi, g in enumerate(ground_truth):
            if gi not in matched_gt:
                alignments.append(
                    FindingAlignment(
                        ground_truth=g,
                        challenger=None,
                        similarity_score=0.0,
                        aligned=False,
                        alignment_type="false_negative",
                        embedding_model_version=self._embedding_model_version,
                    )
                )

        for ci, c in enumerate(challenger):
            if ci not in matched_ch:
                alignments.append(
                    FindingAlignment(
                        ground_truth=None,
                        challenger=c,
                        similarity_score=0.0,
                        aligned=False,
                        alignment_type="false_positive",
                        embedding_model_version=self._embedding_model_version,
                    )
                )

        return alignments

    async def _build_similarity_matrix(
        self,
        ground_truth: list[CalibrationFindingTuple],
        challenger: list[CalibrationFindingTuple],
    ) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
        """Build composite similarity matrix between all finding pairs."""
        gt_descriptions = [g.description for g in ground_truth]
        ch_descriptions = [c.description for c in challenger]

        desc_sim = await self._description_similarity_matrix(
            gt_descriptions, ch_descriptions
        )

        n_gt = len(ground_truth)
        n_ch = len(challenger)
        matrix = np.zeros((n_gt, n_ch), dtype=np.float64)

        for gi in range(n_gt):
            for ci in range(n_ch):
                cat_sim = self._category_similarity(
                    ground_truth[gi].category, challenger[ci].category
                )
                loc_sim = self._location_similarity(
                    ground_truth[gi].location, challenger[ci].location
                )
                d_sim = float(desc_sim[gi, ci])
                matrix[gi, ci] = 0.2 * cat_sim + 0.1 * loc_sim + 0.7 * d_sim

        return matrix

    def _category_similarity(self, a: str, b: str) -> float:
        """Compute category similarity: 1.0 exact, 0.5 same family, 0.0 otherwise."""
        if a.lower() == b.lower():
            return 1.0
        family_a = self._category_to_family.get(a.lower())
        family_b = self._category_to_family.get(b.lower())
        if family_a is not None and family_a == family_b:
            return 0.5
        return 0.0

    def _location_similarity(self, a: str | None, b: str | None) -> float:
        """Compute location similarity: 1.0 if match or both None, 0.0 otherwise."""
        if a is None and b is None:
            return 1.0
        if a is None or b is None:
            return 0.0
        a_lower = a.lower()
        b_lower = b.lower()
        if a_lower == b_lower:
            return 1.0
        if a_lower in b_lower or b_lower in a_lower:
            return 1.0
        return 0.0

    async def _description_similarity_matrix(
        self,
        gt_descriptions: list[str],
        ch_descriptions: list[str],
    ) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
        """Compute description similarity using embeddings or Jaccard fallback."""
        if self._embedding_client is not None:
            try:
                return await self._embedding_similarity_matrix(
                    gt_descriptions, ch_descriptions
                )
            except Exception:
                logger.warning(
                    "Embedding endpoint unavailable, falling back to Jaccard similarity"
                )

        self._embedding_model_version = "jaccard-v1"
        n_gt = len(gt_descriptions)
        n_ch = len(ch_descriptions)
        matrix = np.zeros((n_gt, n_ch), dtype=np.float64)
        for gi in range(n_gt):
            for ci in range(n_ch):
                matrix[gi, ci] = _jaccard_similarity(
                    gt_descriptions[gi], ch_descriptions[ci]
                )
        return matrix

    async def _embedding_similarity_matrix(
        self,
        gt_descriptions: list[str],
        ch_descriptions: list[str],
    ) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
        """Compute cosine similarity via embedding client."""
        assert self._embedding_client is not None
        all_texts = gt_descriptions + ch_descriptions
        batch_size = 32
        all_embeddings: list[list[float]] = []
        for i in range(0, len(all_texts), batch_size):
            batch = all_texts[i : i + batch_size]
            embeddings = await self._embedding_client.embed(batch)
            all_embeddings.extend(embeddings)

        self._embedding_model_version = "embedding-v1"

        gt_emb = np.array(all_embeddings[: len(gt_descriptions)], dtype=np.float64)
        ch_emb = np.array(all_embeddings[len(gt_descriptions) :], dtype=np.float64)

        gt_norm = gt_emb / (np.linalg.norm(gt_emb, axis=1, keepdims=True) + 1e-10)
        ch_norm = ch_emb / (np.linalg.norm(ch_emb, axis=1, keepdims=True) + 1e-10)

        return np.clip(gt_norm @ ch_norm.T, 0.0, 1.0)


def _jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity on whitespace-tokenized lowercase words."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)
