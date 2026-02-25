# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Adaptive-classifier-based 8-class intent classification handler.

Replaces TF-IDF classification with embedding similarity + centroid per class
using the adaptive-classifier library. Labels are versioned in
labels/intent_classes_v1.yaml and adapt to new classes without full retraining.

Design:
    - Deterministic: same input + same classifier_version → same label + confidence
    - Label store: loaded from labels/intent_classes_v1.yaml at module import time
    - Unknown class policy: confidence < UNKNOWN_CONFIDENCE_THRESHOLD → label=unknown,
      event not emitted downstream (R2 policy)
    - Thin functional wrapper: pure function delegates to AdaptiveClassifier instance
    - classifier_version reflects label file version

ONEX Compliance:
    - No try/except at this level — errors propagate to orchestrating handler
    - No I/O after module initialization (label loading happens once at import)
    - Pure functional interface
    - Deterministic outputs for identical inputs (seed fixed at 42 in classifier)

Reference: OMN-2735
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from adaptive_classifier import AdaptiveClassifier

from omniintelligence.nodes.node_intent_classifier_compute.models.enum_intent_class import (
    EnumIntentClass,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Label store path — versioned, PR-reviewed
_LABEL_STORE_PATH: Path = (
    Path(__file__).parents[5] / "labels" / "intent_classes_v1.yaml"
)

# Confidence threshold below which classification returns "unknown" and
# downstream event emission is suppressed (R2: Unknown class policy)
UNKNOWN_CONFIDENCE_THRESHOLD: float = 0.4

# Embedding model used for adaptive-classifier (lightweight, sentence-level)
_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

# Valid 8-class labels (must match EnumIntentClass values exactly)
_VALID_LABELS: frozenset[str] = frozenset(cls.value for cls in EnumIntentClass)


# =============================================================================
# Label store loading
# =============================================================================


def _load_label_store(path: Path) -> tuple[str, dict[str, list[str]]]:
    """Load versioned label store from YAML file.

    Args:
        path: Path to the intent_classes_v1.yaml label store.

    Returns:
        Tuple of (version_string, class_examples_dict).
        class_examples_dict maps label names to lists of example texts.

    Raises:
        FileNotFoundError: If the label store YAML does not exist.
        KeyError: If required YAML keys are missing.
        ValueError: If any label is not a valid EnumIntentClass value.
    """
    # io-audit: ignore-next-line file-io
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    version: str = data["version"]
    classes: dict[str, Any] = data["classes"]

    # Validate all labels match EnumIntentClass
    for label in classes:
        if label not in _VALID_LABELS:
            raise ValueError(
                f"Label store contains unknown label '{label}'. "
                f"Valid labels: {sorted(_VALID_LABELS)}"
            )

    examples: dict[str, list[str]] = {
        label: list(class_data["examples"]) for label, class_data in classes.items()
    }

    return version, examples


# =============================================================================
# Module-level classifier singleton (initialized once)
# =============================================================================

_classifier: AdaptiveClassifier | None = None
_classifier_version: str = "uninitialized"


def _get_classifier() -> tuple[AdaptiveClassifier, str]:
    """Get or initialize the module-level adaptive classifier singleton.

    Loads label store, initializes AdaptiveClassifier with fixed seed for
    determinism, and trains on all labeled examples from the label store.

    Returns:
        Tuple of (initialized_classifier, classifier_version).

    Raises:
        FileNotFoundError: If label store YAML is missing.
        RuntimeError: If classifier initialization fails.
    """
    global _classifier, _classifier_version

    if _classifier is not None:
        return _classifier, _classifier_version

    version, examples = _load_label_store(_LABEL_STORE_PATH)

    clf = AdaptiveClassifier(
        model_name=_EMBEDDING_MODEL,
        seed=42,  # Fixed seed ensures determinism (R3)
    )

    # Batch all examples for initial training
    all_texts: list[str] = []
    all_labels: list[str] = []
    for label, label_examples in examples.items():
        all_texts.extend(label_examples)
        all_labels.extend([label] * len(label_examples))

    clf.add_examples(all_texts, all_labels)

    _classifier = clf
    _classifier_version = version

    logger.info(
        "AdaptiveClassifier initialized: version=%s, classes=%d, examples=%d",
        version,
        len(examples),
        len(all_texts),
    )

    return _classifier, _classifier_version


def reset_classifier() -> None:
    """Reset classifier singleton (for testing only).

    Clears the module-level singleton so the next call to _get_classifier()
    will reinitialize from the label store. Not for production use.
    """
    global _classifier, _classifier_version
    _classifier = None
    _classifier_version = "uninitialized"


# =============================================================================
# Public classification interface
# =============================================================================


class AdaptiveClassificationResult:
    """Result from adaptive classification.

    Attributes:
        intent_label: Resolved EnumIntentClass value, or "unknown" if
            confidence is below UNKNOWN_CONFIDENCE_THRESHOLD.
        confidence: Top class confidence score (0.0 to 1.0).
        classifier_version: Semantic version string from label store.
        evidence: Top-k (label, score) pairs for transparency.
        is_unknown: True when confidence < UNKNOWN_CONFIDENCE_THRESHOLD.
    """

    __slots__ = (
        "classifier_version",
        "confidence",
        "evidence",
        "intent_label",
        "is_unknown",
    )

    def __init__(
        self,
        intent_label: str,
        confidence: float,
        classifier_version: str,
        evidence: list[tuple[str, float]],
        is_unknown: bool,
    ) -> None:
        self.intent_label = intent_label
        self.confidence = confidence
        self.classifier_version = classifier_version
        self.evidence = evidence
        self.is_unknown = is_unknown


def classify_intent_adaptive(
    text: str,
    *,
    confidence_threshold: float = UNKNOWN_CONFIDENCE_THRESHOLD,
    top_k: int = 3,
) -> AdaptiveClassificationResult:
    """Classify intent using adaptive-classifier (embedding similarity + centroid).

    Same input text + same classifier_version always produces the same output
    (R3: determinism via fixed seed=42 and no stochastic sampling).

    Unknown class policy (R2): if the top confidence is below
    confidence_threshold, returns intent_label="unknown" and is_unknown=True.
    Callers must check is_unknown and suppress downstream event emission.

    Args:
        text: The text to classify (e.g., user prompt, hook event content).
        confidence_threshold: Minimum confidence to emit a class label.
            Defaults to UNKNOWN_CONFIDENCE_THRESHOLD (0.4).
        top_k: Number of top predictions to include in evidence list.

    Returns:
        AdaptiveClassificationResult with resolved label, confidence,
        version, evidence list, and unknown flag.

    Raises:
        FileNotFoundError: If label store YAML is missing (init only).
        RuntimeError: If adaptive-classifier fails to predict.
    """
    clf, version = _get_classifier()

    # predict() returns List[Tuple[str, float]] sorted by score descending
    predictions: list[tuple[str, float]] = clf.predict(text, k=top_k)

    if not predictions:
        return AdaptiveClassificationResult(
            intent_label="unknown",
            confidence=0.0,
            classifier_version=version,
            evidence=[],
            is_unknown=True,
        )

    top_label, top_confidence = predictions[0]

    # Unknown class policy: confidence < threshold → label=unknown (R2)
    is_unknown = top_confidence < confidence_threshold
    resolved_label = "unknown" if is_unknown else top_label

    return AdaptiveClassificationResult(
        intent_label=resolved_label,
        confidence=top_confidence,
        classifier_version=version,
        evidence=predictions,
        is_unknown=is_unknown,
    )


def get_classifier_version() -> str:
    """Return the current label store version string.

    Forces classifier initialization if not yet done. Useful for
    embedding classifier_version in event payloads.

    Returns:
        Semantic version string from labels/intent_classes_v1.yaml.
    """
    _, version = _get_classifier()
    return version


__all__ = [
    "UNKNOWN_CONFIDENCE_THRESHOLD",
    "AdaptiveClassificationResult",
    "classify_intent_adaptive",
    "get_classifier_version",
    "reset_classifier",
]
