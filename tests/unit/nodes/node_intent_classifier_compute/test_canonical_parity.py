# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Canonical dispatch parity against outputs recorded from base 978c2645196d.

The legacy function was run from a git archive with its source residency checked.
Only time.perf_counter was fixed to 100.0, making both elapsed-time fields zero.
All expected model_dump(mode="json") outputs below are recorded literal data.
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
    handler_intent_classification as canonical_handler,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
    handler_typed_classification as typed_handler,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.exceptions import (
    IntentClassificationComputeError,
)
from omniintelligence.nodes.node_intent_classifier_compute.models import (
    ModelClassificationConfig,
    ModelIntentClassificationInput,
)

# Shared with the receipt recorder; each input is a complete JSON request payload.
CANONICAL_PARITY_CASES = [
    {
        "case": "code_generation",
        "expected": {
            "classifier_version": "1.0.0",
            "confidence": 1.0,
            "intent_category": "code_generation",
            "keywords": ["function", "generate", "a"],
            "metadata": {
                "classification_time_ms": 0.0,
                "classifier_version": "1.0.0",
                "raw_scores": {
                    "analysis": 0.08771929824561403,
                    "api_design": 0.08771929824561403,
                    "architecture": 0.08771929824561403,
                    "code_generation": 1.0,
                    "database": 0.08771929824561403,
                    "debugging": 0.08771929824561403,
                    "devops": 0.08771929824561403,
                    "documentation": 0.08771929824561403,
                    "pattern_learning": 0.08771929824561403,
                    "quality_assessment": 0.08771929824561403,
                    "refactoring": 0.08771929824561403,
                    "security": 0.08771929824561403,
                    "semantic_analysis": 0.08771929824561403,
                    "testing": 0.08771929824561403,
                },
                "status": "completed",
                "threshold_used": 0.5,
            },
            "processing_time_ms": 0.0,
            "secondary_intents": [],
            "success": True,
            "typed_intent": {
                "confidence": 1.0,
                "config": {
                    "intent_class": "FEATURE",
                    "model_hint": "opus",
                    "sandbox": False,
                    "temperature": 0.5,
                    "validator_set": ["design_review", "test_coverage"],
                },
                "fallback": False,
                "intent_class": "FEATURE",
            },
        },
        "input": {
            "content": "Generate a Python function",
            "context": {},
            "correlation_id": None,
        },
    },
    {
        "case": "mixed_intents",
        "expected": {
            "classifier_version": "1.0.0",
            "confidence": 1.0,
            "intent_category": "debugging",
            "keywords": ["authentication", "bug", "fix", "the"],
            "metadata": {
                "classification_time_ms": 0.0,
                "classifier_version": "1.0.0",
                "raw_scores": {
                    "analysis": 0.0,
                    "api_design": 0.033690476190476194,
                    "architecture": 0.0,
                    "code_generation": 0.33130952380952383,
                    "database": 0.0,
                    "debugging": 1.0,
                    "devops": 0.0,
                    "documentation": 0.0,
                    "pattern_learning": 0.0,
                    "quality_assessment": 0.05952380952380953,
                    "refactoring": 0.0,
                    "security": 0.033690476190476194,
                    "semantic_analysis": 0.11904761904761905,
                    "testing": 0.39083333333333337,
                },
                "status": "completed",
                "threshold_used": 0.25,
            },
            "processing_time_ms": 0.0,
            "secondary_intents": [
                {
                    "confidence": 0.39083333333333337,
                    "intent_category": "testing",
                    "keywords": ["unit", "tests"],
                }
            ],
            "success": True,
            "typed_intent": {
                "confidence": 1.0,
                "config": {
                    "intent_class": "BUGFIX",
                    "model_hint": "sonnet",
                    "sandbox": False,
                    "temperature": 0.2,
                    "validator_set": ["correctness", "regression"],
                },
                "fallback": False,
                "intent_class": "BUGFIX",
            },
        },
        "input": {
            "content": "Fix the authentication bug and write unit tests",
            "context": {"confidence_threshold": 0.25, "max_intents": 1},
            "correlation_id": "11111111-1111-1111-1111-111111111111",
        },
    },
    {
        "case": "unmatched",
        "expected": {
            "classifier_version": "1.0.0",
            "confidence": 0.0,
            "intent_category": "unknown",
            "keywords": [],
            "metadata": {
                "classification_time_ms": 0.0,
                "classifier_version": "1.0.0",
                "raw_scores": {
                    "analysis": 0.0,
                    "api_design": 0.0,
                    "architecture": 0.0,
                    "code_generation": 0.0,
                    "database": 0.0,
                    "debugging": 0.0,
                    "devops": 0.0,
                    "documentation": 0.0,
                    "pattern_learning": 0.0,
                    "quality_assessment": 0.0,
                    "refactoring": 0.0,
                    "security": 0.0,
                    "semantic_analysis": 0.0,
                    "testing": 0.0,
                },
                "status": "completed",
                "threshold_used": 0.5,
            },
            "processing_time_ms": 0.0,
            "secondary_intents": [],
            "success": True,
            "typed_intent": {
                "confidence": 0.0,
                "config": {
                    "intent_class": "ANALYSIS",
                    "model_hint": "haiku",
                    "sandbox": False,
                    "temperature": 0.4,
                    "validator_set": [],
                },
                "fallback": True,
                "intent_class": "ANALYSIS",
            },
        },
        "input": {"content": "zzzzzz qqqqqq", "context": {}, "correlation_id": None},
    },
    {
        "case": "no_tokens",
        "expected": {
            "classifier_version": "1.0.0",
            "confidence": 0.0,
            "intent_category": "unknown",
            "keywords": [],
            "metadata": {
                "classification_time_ms": 0.0,
                "classifier_version": "1.0.0",
                "raw_scores": {},
                "status": "completed",
                "threshold_used": 0.5,
            },
            "processing_time_ms": 0.0,
            "secondary_intents": [],
            "success": True,
            "typed_intent": {
                "confidence": 0.0,
                "config": {
                    "intent_class": "ANALYSIS",
                    "model_hint": "haiku",
                    "sandbox": False,
                    "temperature": 0.4,
                    "validator_set": [],
                },
                "fallback": True,
                "intent_class": "ANALYSIS",
            },
        },
        "input": {"content": "!!! ???", "context": {}, "correlation_id": None},
    },
    {
        "case": "whitespace_validation",
        "expected": {
            "classifier_version": "unknown",
            "confidence": 0.0,
            "intent_category": "unknown",
            "keywords": [],
            "metadata": {
                "classification_time_ms": 0.0,
                "error_code": "INTENT_001",
                "error_type": "IntentClassificationValidationError",
                "message": "Content cannot be empty",
                "status": "validation_error",
            },
            "processing_time_ms": 0.0,
            "secondary_intents": [],
            "success": False,
            "typed_intent": None,
        },
        "input": {"content": " \n\t ", "context": {}, "correlation_id": None},
    },
    {
        "case": "empty_validation",
        "expected": {
            "classifier_version": "unknown",
            "confidence": 0.0,
            "intent_category": "unknown",
            "keywords": [],
            "metadata": {
                "classification_time_ms": 0.0,
                "error_code": "INTENT_001",
                "error_type": "IntentClassificationValidationError",
                "message": "Content cannot be empty",
                "status": "validation_error",
            },
            "processing_time_ms": 0.0,
            "secondary_intents": [],
            "success": False,
            "typed_intent": None,
        },
        "input": {"content": "", "context": {}, "correlation_id": None},
    },
    {
        "case": "compute_error",
        "expected": {
            "classifier_version": "unknown",
            "confidence": 0.0,
            "intent_category": "unknown",
            "keywords": [],
            "metadata": {
                "classification_time_ms": 0.0,
                "error_code": "INTENT_002",
                "error_type": "IntentClassificationComputeError",
                "message": "Parity config lookup failure",
                "status": "compute_error",
            },
            "processing_time_ms": 0.0,
            "secondary_intents": [],
            "success": False,
            "typed_intent": None,
        },
        "input": {
            "content": "Build a component",
            "context": {},
            "correlation_id": None,
        },
    },
    {
        "case": "unexpected_error",
        "expected": {
            "classifier_version": "unknown",
            "confidence": 0.0,
            "intent_category": "unknown",
            "keywords": [],
            "metadata": {
                "classification_time_ms": 0.0,
                "error_code": None,
                "error_type": "ValueError",
                "message": "Unexpected error: ValueError: Parity config lookup failure",
                "status": "unexpected_error",
            },
            "processing_time_ms": 0.0,
            "secondary_intents": [],
            "success": False,
            "typed_intent": None,
        },
        "input": {
            "content": "Refactor and simplify the module",
            "context": {},
            "correlation_id": None,
        },
    },
]


@pytest.mark.unit
@pytest.mark.parametrize("payload", CANONICAL_PARITY_CASES, ids=lambda p: p["case"])
def test_canonical_dispatch_matches_preserved_core(payload, monkeypatch):
    """Compare canonical handle(request) with the recorded legacy behavior."""
    handler_class = getattr(canonical_handler, "HandlerIntentClassification", None)
    assert handler_class is not None, "canonical handle(request) class is required"

    # Empty strings fail the model's min_length constraint. Construct that one
    # request directly to exercise the handler's defensive empty-content guard.
    request = (
        ModelIntentClassificationInput.model_construct(**payload["input"])
        if payload["case"] == "empty_validation"
        else ModelIntentClassificationInput.model_validate(payload["input"])
    )
    monkeypatch.setattr("time.perf_counter", lambda: 100.0)

    # The same downstream seam exists on the legacy tree. These failures exercise
    # the orchestrator's error outputs without replacing classification/scoring.
    if payload["case"] in ("compute_error", "unexpected_error"):
        error = (
            IntentClassificationComputeError("Parity config lookup failure")
            if payload["case"] == "compute_error"
            else ValueError("Parity config lookup failure")
        )

        def fail_config_lookup(*args, **kwargs):
            raise error

        monkeypatch.setattr(
            typed_handler, "get_intent_class_config", fail_config_lookup
        )

    actual = handler_class(ModelClassificationConfig()).handle(request)
    assert actual.model_dump(mode="json") == payload["expected"]
