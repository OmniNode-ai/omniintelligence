# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerDocPromotion (OMN-23422).

``HandlerDocPromotion.handle`` must return exactly what the preserved
``handle_doc_promotion`` returns for the same batch and the same threshold
override. Cases cover each gate of the reducer: Q->V promotion, the V->S gates
(runs, used rate, signal floor, all passed), demotion, the terminal
BLACKLISTED tier, the SHARED tier, attribution signal accumulation (including
the low-similarity skip), a source type without a threshold set, an empty
batch, and a custom threshold set.
"""

import importlib
import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_doc_promotion_reducer.handlers.handler_doc_promotion import (
    handle_doc_promotion,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_attribution_signal_type import (
    EnumAttributionSignalType,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_context_item_source_type import (
    EnumContextItemSourceType,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_promotion_tier import (
    EnumPromotionTier,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.model_attribution_signal import (
    ModelAttributionSignal,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.model_doc_promotion_input import (
    ModelDocPromotionInput,
    ModelPromotionCandidate,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.model_promotion_threshold_set import (
    ModelPromotionThresholdSet,
)

_MODULE = (
    "omniintelligence.nodes.node_doc_promotion_reducer.handlers.handler_doc_promotion"
)
_WRAPPER_CLASS = "HandlerDocPromotion"
_Source = EnumContextItemSourceType
_Tier = EnumPromotionTier
_Signal = EnumAttributionSignalType


def _item_id(n: int = 1) -> UUID:
    return UUID(int=n)


def _signal(
    signal_type: EnumAttributionSignalType, similarity: float | None = None
) -> ModelAttributionSignal:
    return ModelAttributionSignal(
        item_id=_item_id(),
        signal_type=signal_type,
        strength=1.0,
        similarity=similarity,
    )


def _candidate(
    *,
    item: int = 1,
    source_type: EnumContextItemSourceType = _Source.REPO_DERIVED,
    current_tier: EnumPromotionTier = _Tier.QUARANTINE,
    scored_runs: int = 0,
    positive_signals: int = 0,
    used_rate: float = 0.0,
    hurt_rate: float = 0.0,
    recent_signals: tuple[ModelAttributionSignal, ...] = (),
) -> ModelPromotionCandidate:
    return ModelPromotionCandidate(
        item_id=_item_id(item),
        source_type=source_type,
        current_tier=current_tier,
        scored_runs=scored_runs,
        positive_signals=positive_signals,
        used_rate=used_rate,
        hurt_rate=hurt_rate,
        recent_signals=recent_signals,
        correlation_id="corr-23422",
    )


def _batch(
    *candidates: ModelPromotionCandidate, dry_run: bool = False
) -> ModelDocPromotionInput:
    return ModelDocPromotionInput(
        candidates=candidates, dry_run=dry_run, correlation_id="batch-23422"
    )


def _no_deps() -> dict[str, Any]:
    return {}


def _only_static_standards() -> dict[str, Any]:
    """Threshold override with a single source type (others have no set)."""
    return {
        "threshold_sets": {
            _Source.STATIC_STANDARDS: ModelPromotionThresholdSet(
                source_type=_Source.STATIC_STANDARDS,
                quarantine_to_validated_runs=None,
                validated_to_shared_runs=10,
                validated_to_shared_used_rate=0.10,
                validated_to_shared_signal_floor=5,
                validated_to_quarantine_hurt_rate=0.40,
            )
        }
    }


def _lenient_repo_derived() -> dict[str, Any]:
    """Threshold override that promotes REPO_DERIVED almost immediately."""
    return {
        "threshold_sets": {
            _Source.REPO_DERIVED: ModelPromotionThresholdSet(
                source_type=_Source.REPO_DERIVED,
                quarantine_to_validated_runs=1,
                validated_to_shared_runs=2,
                validated_to_shared_used_rate=0.0,
                validated_to_shared_signal_floor=0,
                validated_to_quarantine_hurt_rate=0.9,
            )
        }
    }


_STATIC_V = {"source_type": _Source.STATIC_STANDARDS, "current_tier": _Tier.VALIDATED}
_REPO_V = {"source_type": _Source.REPO_DERIVED, "current_tier": _Tier.VALIDATED}

PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], ModelDocPromotionInput],
        Callable[[], dict[str, Any]],
    ]
] = [
    # Edge: empty batch yields zero counts.
    ("empty-batch", _WRAPPER_CLASS, lambda: _batch(), _no_deps),
    # Normal path: Q->V promotion at the REPO_DERIVED threshold.
    (
        "quarantine-promoted",
        _WRAPPER_CLASS,
        lambda: _batch(_candidate(scored_runs=5)),
        _no_deps,
    ),
    # Q->V blocked below the threshold.
    (
        "quarantine-blocked",
        _WRAPPER_CLASS,
        lambda: _batch(_candidate(scored_runs=4)),
        _no_deps,
    ),
    # Q->V then V->S in a single pass (no signal floor for hook items).
    (
        "quarantine-to-shared",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(source_type=_Source.MEMORY_HOOK, scored_runs=30, used_rate=0.5)
        ),
        _no_deps,
    ),
    # V->S gate: not enough scored runs.
    (
        "validated-blocked-runs",
        _WRAPPER_CLASS,
        lambda: _batch(_candidate(**_STATIC_V, scored_runs=9, used_rate=0.5)),
        _no_deps,
    ),
    # V->S gate: used rate too low.
    (
        "validated-blocked-used-rate",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(**_STATIC_V, scored_runs=10, used_rate=0.05, positive_signals=9)
        ),
        _no_deps,
    ),
    # V->S gate: positive signal floor not reached.
    (
        "validated-blocked-signal-floor",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(**_STATIC_V, scored_runs=10, used_rate=0.5, positive_signals=4)
        ),
        _no_deps,
    ),
    # All V->S gates passed.
    (
        "validated-to-shared",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(**_STATIC_V, scored_runs=10, used_rate=0.5, positive_signals=5)
        ),
        _no_deps,
    ),
    # Demotion by stored hurt rate.
    (
        "validated-demoted",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(**_REPO_V, scored_runs=20, used_rate=0.5, hurt_rate=0.5)
        ),
        _no_deps,
    ),
    # Terminal tier: no transitions evaluated.
    (
        "blacklisted-unchanged",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(current_tier=_Tier.BLACKLISTED, scored_runs=100, used_rate=1.0)
        ),
        _no_deps,
    ),
    # SHARED has no further gate.
    (
        "shared-no-gate",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(source_type=_Source.STATIC_STANDARDS, current_tier=_Tier.SHARED)
        ),
        _no_deps,
    ),
    # STATIC_STANDARDS in QUARANTINE has no Q->V gate.
    (
        "static-quarantine-no-gate",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(source_type=_Source.STATIC_STANDARDS, scored_runs=50)
        ),
        _no_deps,
    ),
    # Positive recent signals lift the item over the signal floor.
    (
        "signals-lift-over-floor",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(
                **_STATIC_V,
                scored_runs=10,
                used_rate=0.5,
                positive_signals=3,
                recent_signals=(
                    _signal(_Signal.RULE_FOLLOWED),
                    _signal(_Signal.STANDARD_CITED),
                ),
            )
        ),
        _no_deps,
    ),
    # DOC_SECTION_MATCHED: one valid match counts, one low-similarity and one
    # similarity-less match are skipped.
    (
        "doc-section-similarity-gate",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(
                **_STATIC_V,
                scored_runs=10,
                used_rate=0.5,
                positive_signals=4,
                recent_signals=(
                    _signal(_Signal.DOC_SECTION_MATCHED, similarity=0.9),
                    _signal(_Signal.DOC_SECTION_MATCHED, similarity=0.2),
                    _signal(_Signal.DOC_SECTION_MATCHED),
                ),
            )
        ),
        _no_deps,
    ),
    # Negative recent signals push the hurt rate over the demotion threshold.
    (
        "violations-trigger-demotion",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(
                **_REPO_V,
                scored_runs=4,
                recent_signals=(
                    _signal(_Signal.PATTERN_VIOLATED),
                    _signal(_Signal.HOOK_FAILED),
                    _signal(_Signal.HOOK_SKIPPED),
                ),
            )
        ),
        _no_deps,
    ),
    # Edge: a zero-run candidate with a negative signal (denominator floor).
    (
        "zero-runs-negative-signal",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(**_REPO_V, recent_signals=(_signal(_Signal.PATTERN_VIOLATED),))
        ),
        _no_deps,
    ),
    # Mixed batch in dry-run mode with every outcome counted.
    (
        "mixed-batch-dry-run",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(item=1, scored_runs=5),
            _candidate(item=2, **_REPO_V, scored_runs=20, hurt_rate=0.6),
            _candidate(item=3, current_tier=_Tier.BLACKLISTED),
            dry_run=True,
        ),
        _no_deps,
    ),
    # Error-ish edge: source types without a threshold set are skipped.
    (
        "unknown-source-type-skipped",
        _WRAPPER_CLASS,
        lambda: _batch(
            _candidate(item=1, scored_runs=5),
            _candidate(item=2, **_STATIC_V, scored_runs=10, used_rate=0.5),
        ),
        _only_static_standards,
    ),
    # Custom threshold sets are forwarded to the function.
    (
        "custom-threshold-sets",
        _WRAPPER_CLASS,
        lambda: _batch(_candidate(scored_runs=2)),
        _lenient_repo_derived,
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _cls, _req, _deps in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], ModelDocPromotionInput],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """Wrapper handle() and the preserved function return equal outputs."""
    wrapper_cls = getattr(importlib.import_module(_MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_result: Any = None
    wrapper_error: Exception | None = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:  # captured deliberately for parity comparison
        wrapper_error = exc

    function_result: Any = None
    function_error: Exception | None = None
    try:
        function_result = await handle_doc_promotion(request_b, **deps_b)
    except Exception as exc:  # captured deliberately for parity comparison
        function_error = exc

    if wrapper_error is not None or function_error is not None:
        assert wrapper_error is not None, (
            f"wrapper succeeded but function raised {function_error!r}"
        )
        assert function_error is not None, (
            f"function succeeded but wrapper raised {wrapper_error!r}"
        )
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_result == function_result


def corpus_inputs() -> list[dict[str, Any]]:
    """Return every PARITY_CASES request as a JSON-describable dict, in order."""
    rows: list[dict[str, Any]] = []
    for case_id, class_name, request_builder, _deps_builder in PARITY_CASES:
        request = request_builder()
        payload = (
            request.model_dump(mode="json")
            if isinstance(request, BaseModel)
            else request
        )
        rows.append(
            {
                "case": case_id,
                "wrapper": class_name,
                "request": json.loads(json.dumps(payload, default=str)),
            }
        )
    return rows
