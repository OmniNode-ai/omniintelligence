# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Canonical dispatch parity against outputs recorded from git base 978c2645196d.

Goldens were recorded by calling handle_quality_scoring_compute from the base
source extracted with git archive, with time.perf_counter fixed at 100.0.
Only compute_error injects an invariant failure in _compute_all_dimensions;
the same dependency failure was applied when recording that legacy output.
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    handler_compute as canonical_handler,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    handler_quality_scoring as scoring,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers.exceptions import (
    QualityScoringComputeError,
)
from omniintelligence.nodes.node_quality_scoring_compute.models import (
    ModelQualityScoringInput,
)

# Literal legacy model_dump(mode="json") results, never recomputed from HEAD.
CANONICAL_PARITY_CASES = [
    {
        "case": "python_success",
        "input": {
            "source_path": "sample.py",
            "content": '"""A sample module."""\n'
            "def double(value: int) -> int:\n"
            '    """Double a value."""\n'
            "    return value * 2\n",
        },
        "expected": {
            "success": True,
            "quality_score": 0.8425,
            "dimensions": {
                "complexity": 1.0,
                "maintainability": 1.0,
                "documentation": 0.7,
                "temporal_relevance": 1.0,
                "patterns": 0.3,
                "architectural": 0.95,
            },
            "onex_compliant": True,
            "recommendations": [
                "[patterns] Add ONEX patterns: use frozen=True on "
                "models, TypedDict for dicts, Protocol for "
                "interfaces, and extract pure handler functions"
            ],
            "metadata": {
                "status": "completed",
                "message": None,
                "tracking_url": None,
                "source_language": "python",
                "analysis_version": "1.2.0",
                "processing_time_ms": 0.0,
            },
        },
    },
    {
        "case": "below_threshold",
        "input": {
            "source_path": "sample.py",
            "content": "x = 1\n",
            "min_quality_threshold": 1.0,
        },
        "expected": {
            "success": False,
            "quality_score": 0.685,
            "dimensions": {
                "complexity": 1.0,
                "maintainability": 0.7,
                "documentation": 0.0,
                "temporal_relevance": 1.0,
                "patterns": 0.3,
                "architectural": 1.0,
            },
            "onex_compliant": False,
            "recommendations": [
                "[documentation] Add documentation: include "
                "docstrings for all public functions, classes, and "
                "modules",
                "[patterns] Add ONEX patterns: use frozen=True on "
                "models, TypedDict for dicts, Protocol for "
                "interfaces, and extract pure handler functions",
            ],
            "metadata": {
                "status": "below_threshold",
                "message": "Quality score 0.69 below threshold 1.0",
                "tracking_url": None,
                "source_language": "python",
                "analysis_version": "1.2.0",
                "processing_time_ms": 0.0,
            },
        },
    },
    {
        "case": "preset",
        "input": {
            "source_path": "sample.py",
            "content": "class Worker:\n    pass\n",
            "onex_preset": "lenient",
        },
        "expected": {
            "success": True,
            "quality_score": 0.8225,
            "dimensions": {
                "complexity": 1.0,
                "maintainability": 1.0,
                "documentation": 0.0,
                "temporal_relevance": 1.0,
                "patterns": 0.3,
                "architectural": 0.95,
            },
            "onex_compliant": True,
            "recommendations": [
                "[documentation] Add documentation: include "
                "docstrings for all public functions, classes, and "
                "modules",
                "[patterns] Add ONEX patterns: use frozen=True on "
                "models, TypedDict for dicts, Protocol for "
                "interfaces, and extract pure handler functions",
            ],
            "metadata": {
                "status": "completed",
                "message": None,
                "tracking_url": None,
                "source_language": "python",
                "analysis_version": "1.2.0",
                "processing_time_ms": 0.0,
            },
        },
    },
    {
        "case": "custom_weights",
        "input": {
            "source_path": "sample.py",
            "content": "def choose(x):\n    if x:\n        return 1\n    return 0\n",
            "dimension_weights": {
                "complexity": 0.4,
                "maintainability": 0.2,
                "documentation": 0.1,
                "temporal_relevance": 0.1,
                "patterns": 0.1,
                "architectural": 0.1,
            },
            "onex_compliance_threshold": 0.5,
        },
        "expected": {
            "success": True,
            "quality_score": 0.805,
            "dimensions": {
                "complexity": 0.95,
                "maintainability": 1.0,
                "documentation": 0.0,
                "temporal_relevance": 1.0,
                "patterns": 0.3,
                "architectural": 0.95,
            },
            "onex_compliant": True,
            "recommendations": [
                "[documentation] Add documentation: include "
                "docstrings for all public functions, classes, and "
                "modules",
                "[patterns] Add ONEX patterns: use frozen=True on "
                "models, TypedDict for dicts, Protocol for "
                "interfaces, and extract pure handler functions",
            ],
            "metadata": {
                "status": "completed",
                "message": None,
                "tracking_url": None,
                "source_language": "python",
                "analysis_version": "1.2.0",
                "processing_time_ms": 0.0,
            },
        },
    },
    {
        "case": "empty_content",
        "input": {"source_path": "empty.py", "content": " \n "},
        "expected": {
            "success": False,
            "quality_score": 0.0,
            "dimensions": {
                "complexity": 0.0,
                "maintainability": 0.0,
                "documentation": 0.0,
                "temporal_relevance": 0.0,
                "patterns": 0.0,
                "architectural": 0.0,
            },
            "onex_compliant": False,
            "recommendations": [],
            "metadata": {
                "status": "validation_error",
                "message": "[validation_error] Content cannot be empty",
                "tracking_url": None,
                "source_language": None,
                "analysis_version": None,
                "processing_time_ms": 0.0,
            },
        },
    },
    {
        "case": "syntax_error",
        "input": {"source_path": "broken.py", "content": "def broken(:"},
        "expected": {
            "success": True,
            "quality_score": 0.3,
            "dimensions": {
                "complexity": 0.3,
                "maintainability": 0.3,
                "documentation": 0.3,
                "temporal_relevance": 0.3,
                "patterns": 0.3,
                "architectural": 0.3,
            },
            "onex_compliant": False,
            "recommendations": [
                "[syntax_error] Code contains syntax errors and "
                "cannot be fully analyzed: invalid syntax "
                "(<unknown>, line 1)"
            ],
            "metadata": {
                "status": "completed",
                "message": None,
                "tracking_url": None,
                "source_language": "python",
                "analysis_version": "1.2.0",
                "processing_time_ms": 0.0,
            },
        },
    },
    {
        "case": "unsupported_language",
        "input": {
            "source_path": "sample.js",
            "content": "const x = 1;",
            "language": "javascript",
        },
        "expected": {
            "success": True,
            "quality_score": 0.5,
            "dimensions": {
                "complexity": 0.5,
                "maintainability": 0.5,
                "documentation": 0.5,
                "temporal_relevance": 0.5,
                "patterns": 0.5,
                "architectural": 0.5,
            },
            "onex_compliant": False,
            "recommendations": [
                "[unsupported_language] Full analysis not available "
                "for 'javascript'. Only Python is fully supported. "
                "Baseline scores applied."
            ],
            "metadata": {
                "status": "completed",
                "message": None,
                "tracking_url": None,
                "source_language": "javascript",
                "analysis_version": "1.2.0",
                "processing_time_ms": 0.0,
            },
        },
    },
    {
        "case": "compute_error",
        "input": {"source_path": "sample.py", "content": "x = 1\n"},
        "expected": {
            "success": False,
            "quality_score": 0.0,
            "dimensions": {
                "complexity": 0.0,
                "maintainability": 0.0,
                "documentation": 0.0,
                "temporal_relevance": 0.0,
                "patterns": 0.0,
                "architectural": 0.0,
            },
            "onex_compliant": False,
            "recommendations": [],
            "metadata": {
                "status": "compute_error",
                "message": "parity scoring failure",
                "tracking_url": None,
                "source_language": None,
                "analysis_version": None,
                "processing_time_ms": 0.0,
            },
        },
    },
]


@pytest.mark.unit
@pytest.mark.parametrize("payload", CANONICAL_PARITY_CASES, ids=lambda p: p["case"])
def test_canonical_dispatch_matches_preserved_core(payload, monkeypatch):
    """Require the canonical class and preserve the recorded legacy behavior."""
    handler_class = getattr(canonical_handler, "HandlerQualityScoringCompute", None)
    assert handler_class is not None, "canonical handle(request) class is required"

    request = ModelQualityScoringInput.model_validate(payload["input"])
    monkeypatch.setattr("time.perf_counter", lambda: 100.0)
    if payload["case"] == "compute_error":

        def fail_scoring(content):
            raise QualityScoringComputeError("parity scoring failure")

        monkeypatch.setattr(scoring, "_compute_all_dimensions", fail_scoring)

    actual = handler_class().handle(request).model_dump(mode="json")
    assert actual == payload["expected"]
