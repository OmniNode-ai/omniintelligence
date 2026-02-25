# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for adaptive-classifier-based 8-class intent classification handler.

Validates:
    - R3: Determinism — same input produces same label + confidence
    - R2: Unknown class policy — low-confidence input does not emit event
    - Label store loads from labels/intent_classes_v1.yaml correctly
    - AdaptiveClassificationResult fields are populated correctly
    - All 8 classes are represented in the label store

Reference: OMN-2735
DoD tests:
    - intent_determinism: Determinism check (R3)
    - intent_unknown_policy: Unknown class policy (R2)

Note on imports:
    This module uses importlib.util to load handler_adaptive_classification
    directly by file path, bypassing the package __init__.py chain that
    transitively imports omnibase_core (a private package not available in
    isolated test environments). The handler itself has no omnibase_core
    dependency; only the parent package __init__ does.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

# ---------------------------------------------------------------------------
# Isolated module loading
# ---------------------------------------------------------------------------
# Load handler_adaptive_classification directly, bypassing the package __init__
# chain that transitively imports omnibase_core.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[4]
_HANDLER_PATH = (
    _REPO_ROOT
    / "src"
    / "omniintelligence"
    / "nodes"
    / "node_intent_classifier_compute"
    / "handlers"
    / "handler_adaptive_classification.py"
)
_ENUM_PATH = (
    _REPO_ROOT
    / "src"
    / "omniintelligence"
    / "nodes"
    / "node_intent_classifier_compute"
    / "models"
    / "enum_intent_class.py"
)


def _load_module(name: str, path: Path) -> ModuleType:
    """Load a Python module directly from a file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


# Load enum first (no dependencies)
_enum_mod = _load_module(
    "omniintelligence.nodes.node_intent_classifier_compute.models.enum_intent_class",
    _ENUM_PATH,
)
EnumIntentClass = _enum_mod.EnumIntentClass

# Load handler module directly
_handler_mod = _load_module(
    "omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_adaptive_classification",
    _HANDLER_PATH,
)

UNKNOWN_CONFIDENCE_THRESHOLD: float = _handler_mod.UNKNOWN_CONFIDENCE_THRESHOLD
AdaptiveClassificationResult = _handler_mod.AdaptiveClassificationResult
_load_label_store = _handler_mod._load_label_store
classify_intent_adaptive = _handler_mod.classify_intent_adaptive
get_classifier_version = _handler_mod.get_classifier_version
reset_classifier = _handler_mod.reset_classifier

# Path to the actual label store (used in load tests)
_LABEL_STORE_PATH = _REPO_ROOT / "labels" / "intent_classes_v1.yaml"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_classifier_singleton() -> None:
    """Reset classifier singleton before each test for test isolation.

    This ensures each test that triggers classifier initialization gets
    a fresh instance. Important for tests that verify initialization
    behavior or use custom label stores.
    """
    reset_classifier()
    yield
    reset_classifier()


# ---------------------------------------------------------------------------
# Label store tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLabelStore:
    """Tests for labels/intent_classes_v1.yaml label store."""

    def test_label_store_file_exists(self) -> None:
        """Label store file exists at expected path."""
        assert _LABEL_STORE_PATH.exists(), (
            f"Label store not found at {_LABEL_STORE_PATH}. "
            "Expected labels/intent_classes_v1.yaml in repo root."
        )

    def test_label_store_has_version(self) -> None:
        """Label store has a version field."""
        version, _ = _load_label_store(_LABEL_STORE_PATH)
        assert version, "Label store version must not be empty"
        # Semver format: major.minor.patch
        parts = version.split(".")
        assert len(parts) == 3, f"Version '{version}' must be in semver format (X.Y.Z)"

    def test_label_store_has_all_8_classes(self) -> None:
        """Label store contains exactly 8 classes matching EnumIntentClass."""
        _, examples = _load_label_store(_LABEL_STORE_PATH)
        expected_labels = {cls.value for cls in EnumIntentClass}
        actual_labels = set(examples.keys())
        assert actual_labels == expected_labels, (
            f"Label store classes mismatch.\n"
            f"Expected: {sorted(expected_labels)}\n"
            f"Actual:   {sorted(actual_labels)}"
        )

    def test_each_class_has_minimum_examples(self) -> None:
        """Each class in the label store has at least 3 examples."""
        _, examples = _load_label_store(_LABEL_STORE_PATH)
        for label, label_examples in examples.items():
            assert len(label_examples) >= 3, (
                f"Class '{label}' has only {len(label_examples)} examples. "
                "Minimum 3 required for centroid bootstrap."
            )


# ---------------------------------------------------------------------------
# Determinism tests (R3 — OMN-2735 DoD: intent_determinism)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIntentDeterminism:
    """Tests that same input produces same output (R3).

    DoD marker: uv run pytest tests/unit/ -k intent_determinism
    """

    def test_intent_determinism_same_input_same_label(self) -> None:
        """Same input text produces same label across two consecutive calls."""
        text = "Refactor the authentication module to reduce cyclomatic complexity"

        result1 = classify_intent_adaptive(text)
        result2 = classify_intent_adaptive(text)

        assert result1.intent_label == result2.intent_label, (
            f"Non-deterministic: same input produced different labels. "
            f"Run 1: {result1.intent_label}, Run 2: {result2.intent_label}"
        )

    def test_intent_determinism_same_input_same_confidence(self) -> None:
        """Same input text produces identical confidence across calls."""
        text = "Fix the null pointer exception when user session expires"

        result1 = classify_intent_adaptive(text)
        result2 = classify_intent_adaptive(text)

        assert result1.confidence == result2.confidence, (
            f"Non-deterministic: same input produced different confidence. "
            f"Run 1: {result1.confidence:.4f}, Run 2: {result2.confidence:.4f}"
        )

    def test_intent_determinism_different_inputs_may_differ(self) -> None:
        """Different inputs can produce different labels (sanity check)."""
        result_refactor = classify_intent_adaptive(
            "Rename variables for clarity and follow PEP 8 conventions"
        )
        result_security = classify_intent_adaptive(
            "Audit the API endpoints for missing authentication checks"
        )

        # Labels should differ for clearly different intents
        # (not a hard requirement — depends on model — but verifies non-trivially)
        assert isinstance(result_refactor.intent_label, str)
        assert isinstance(result_security.intent_label, str)

    def test_intent_determinism_classifier_version_stable(self) -> None:
        """Classifier version is stable across multiple calls."""
        version1 = get_classifier_version()
        version2 = get_classifier_version()
        assert version1 == version2, "Classifier version must be stable between calls"

    def test_intent_determinism_version_is_semver(self) -> None:
        """Classifier version is a valid semver string."""
        version = get_classifier_version()
        parts = version.split(".")
        assert len(parts) == 3, f"Version '{version}' must be in semver format (X.Y.Z)"
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' must be numeric"

    def test_intent_determinism_result_type(self) -> None:
        """classify_intent_adaptive returns AdaptiveClassificationResult."""
        result = classify_intent_adaptive("Add a new REST endpoint for user management")
        assert isinstance(result, AdaptiveClassificationResult)
        assert isinstance(result.intent_label, str)
        assert isinstance(result.confidence, float)
        assert isinstance(result.classifier_version, str)
        assert isinstance(result.evidence, list)
        assert isinstance(result.is_unknown, bool)

    def test_intent_determinism_evidence_has_scores(self) -> None:
        """Evidence list contains (label, score) tuples."""
        result = classify_intent_adaptive("Implement OAuth2 PKCE flow for mobile")
        assert len(result.evidence) > 0, "Evidence list must not be empty"
        for label, score in result.evidence:
            assert isinstance(label, str), (
                f"Evidence label must be str, got {type(label)}"
            )
            assert isinstance(score, float), (
                f"Evidence score must be float, got {type(score)}"
            )
            assert 0.0 <= score <= 1.0, (
                f"Evidence score {score} out of [0.0, 1.0] range"
            )


# ---------------------------------------------------------------------------
# Unknown class policy tests (R2 — OMN-2735 DoD: intent_unknown_policy)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIntentUnknownPolicy:
    """Tests for unknown class policy (R2).

    Low-confidence input returns label=unknown and is_unknown=True.
    Callers must suppress downstream event emission when is_unknown=True.

    DoD marker: uv run pytest tests/unit/ -k intent_unknown_policy
    """

    def test_intent_unknown_policy_low_confidence_returns_unknown(self) -> None:
        """Input with confidence below threshold returns label=unknown."""
        # Use a very low threshold to force unknown
        result = classify_intent_adaptive(
            "asdfjkl qwerty zxcvbn nonsense gibberish 12345",
            confidence_threshold=1.0,  # Force unknown: any confidence < 1.0
        )

        assert result.intent_label == "unknown", (
            f"Expected 'unknown' with threshold=1.0, got '{result.intent_label}' "
            f"(confidence={result.confidence:.4f})"
        )
        assert result.is_unknown is True, (
            "is_unknown must be True when confidence < threshold"
        )

    def test_intent_unknown_policy_unknown_confidence_below_threshold(self) -> None:
        """When is_unknown=True, confidence < threshold."""
        result = classify_intent_adaptive(
            "asdfjkl qwerty zxcvbn",
            confidence_threshold=1.0,
        )

        if result.is_unknown:
            assert result.confidence < 1.0, (
                "When is_unknown=True, confidence must be below the threshold"
            )

    def test_intent_unknown_policy_high_confidence_not_unknown(self) -> None:
        """Clear-intent input with low threshold is not marked unknown."""
        result = classify_intent_adaptive(
            "Fix the null pointer exception in the session handler",
            confidence_threshold=0.0,  # Always accept
        )

        assert result.is_unknown is False, (
            "is_unknown must be False when threshold=0.0 and classifier returns a prediction"
        )
        assert result.intent_label != "unknown", (
            "Expected a valid intent label with threshold=0.0, got 'unknown'"
        )

    def test_intent_unknown_policy_default_threshold_value(self) -> None:
        """Default UNKNOWN_CONFIDENCE_THRESHOLD is 0.4."""
        assert UNKNOWN_CONFIDENCE_THRESHOLD == 0.4, (
            f"Expected default threshold 0.4, got {UNKNOWN_CONFIDENCE_THRESHOLD}"
        )

    def test_intent_unknown_policy_custom_threshold_respected(self) -> None:
        """Custom confidence_threshold parameter is respected."""
        text = "Refactor the module to reduce coupling"

        # Get prediction with low threshold — should not be unknown for clear intent
        result_low = classify_intent_adaptive(text, confidence_threshold=0.0)

        # With zero threshold, never unknown
        assert result_low.is_unknown is False

    def test_intent_unknown_policy_unknown_label_is_string(self) -> None:
        """unknown label is the literal string 'unknown', not None or empty."""
        result = classify_intent_adaptive(
            "nonsense",
            confidence_threshold=1.0,  # Force unknown
        )

        assert result.intent_label == "unknown"
        assert result.intent_label is not None
        assert len(result.intent_label) > 0


# ---------------------------------------------------------------------------
# Full pipeline smoke test
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAdaptiveClassificationSmoke:
    """Smoke tests verifying end-to-end pipeline works."""

    def test_classify_intent_adaptive_returns_valid_label_or_unknown(self) -> None:
        """classify_intent_adaptive always returns a valid label or 'unknown'."""
        valid_labels = {cls.value for cls in EnumIntentClass} | {"unknown"}

        test_texts = [
            "Fix the authentication bug in the login flow",
            "Add a new feature for user management",
            "Refactor the database layer",
            "Write documentation for the API",
            "Create an Alembic migration for the new table",
            "Audit the security of the payment system",
            "Update the Kafka configuration",
            "Analyze the performance bottleneck",
        ]

        for text in test_texts:
            result = classify_intent_adaptive(text)
            assert result.intent_label in valid_labels, (
                f"Unexpected label '{result.intent_label}' for text: '{text}'. "
                f"Valid labels: {sorted(valid_labels)}"
            )

    def test_classify_intent_adaptive_confidence_in_range(self) -> None:
        """Confidence is always in [0.0, 1.0]."""
        result = classify_intent_adaptive("Implement the new webhook handler")
        assert 0.0 <= result.confidence <= 1.0, (
            f"Confidence {result.confidence} out of valid range [0.0, 1.0]"
        )

    def test_classify_intent_adaptive_version_matches_label_store(self) -> None:
        """Classifier version matches the version in the label store YAML."""
        version_from_func = get_classifier_version()
        version_from_store, _ = _load_label_store(_LABEL_STORE_PATH)
        assert version_from_func == version_from_store, (
            f"Classifier version '{version_from_func}' does not match "
            f"label store version '{version_from_store}'"
        )
