# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity: the contract-bound staleness wrapper matches the preserved function.

``HandlerStalenessDetection.handle`` forwards its request and injected
store/trigger dependencies to ``handle_staleness_detection``. Both are run
against identical requests and fresh in-memory fakes; the outputs (or raised
errors) and the ordered store/trigger call logs must be identical.

Ticket: OMN-23422
"""

import importlib
import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest

from omniintelligence.nodes.node_doc_staleness_detector_effect.handlers.handler_staleness_detector import (
    handle_staleness_detection,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.enum_staleness_case import (
    EnumStalenessCase,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.enum_staleness_transition_step import (
    EnumStalenessTransitionStep,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.model_staleness_detect_input import (
    ModelStalenessCandidate,
    ModelStalenessDetectInput,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.model_staleness_transition import (
    ModelStalenessTransition,
)

MODULE = (
    "omniintelligence.nodes.node_doc_staleness_detector_effect.handlers."
    "handler_staleness_detector"
)
CLASS_NAME = "HandlerStalenessDetection"

_ITEM_1 = UUID("00000000-0000-0000-0000-000000000001")
_ITEM_2 = UUID("00000000-0000-0000-0000-000000000002")
_ITEM_3 = UUID("00000000-0000-0000-0000-000000000003")
_NEW_ITEM = UUID("00000000-0000-0000-0000-0000000000aa")

_SIMILAR = ((1.0, 0.0, 0.0), (0.99, 0.05, 0.0))
_ORTHOGONAL = ((1.0, 0.0), (0.0, 1.0))


class FakeStalenessStore:
    """In-memory staleness store that records every call in order."""

    def __init__(
        self,
        existing: dict[UUID, ModelStalenessTransition] | None = None,
        *,
        verify_pg: bool = True,
        verify_qdrant: bool = True,
        fail_blacklist_for: frozenset[UUID] = frozenset(),
        fail_load: bool = False,
    ) -> None:
        self.transitions = dict(existing or {})
        self.verify_pg = verify_pg
        self.verify_qdrant = verify_qdrant
        self.fail_blacklist_for = fail_blacklist_for
        self.fail_load = fail_load
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def blacklist_item(self, *, item_id: UUID) -> None:
        self.calls.append(("blacklist_item", {"item_id": item_id}))
        if item_id in self.fail_blacklist_for:
            raise RuntimeError(f"blacklist failed for {item_id}")

    async def update_source_ref(self, *, item_id: UUID, new_source_ref: str) -> None:
        self.calls.append(
            (
                "update_source_ref",
                {"item_id": item_id, "new_source_ref": new_source_ref},
            )
        )

    async def verify_item_in_pg(self, *, item_id: UUID) -> bool:
        self.calls.append(("verify_item_in_pg", {"item_id": item_id}))
        return self.verify_pg

    async def verify_item_in_qdrant(self, *, item_id: UUID, collection: str) -> bool:
        self.calls.append(
            ("verify_item_in_qdrant", {"item_id": item_id, "collection": collection})
        )
        return self.verify_qdrant

    async def apply_stat_carry(
        self, *, old_item_id: UUID, new_item_id: UUID, carry_fraction: float
    ) -> None:
        self.calls.append(
            (
                "apply_stat_carry",
                {
                    "old_item_id": old_item_id,
                    "new_item_id": new_item_id,
                    "carry_fraction": carry_fraction,
                },
            )
        )

    async def save_transition(self, *, transition: ModelStalenessTransition) -> None:
        self.calls.append(("save_transition", {"transition": transition}))
        self.transitions[transition.transition_id] = transition

    async def load_transition(
        self, *, transition_id: UUID
    ) -> ModelStalenessTransition | None:
        self.calls.append(("load_transition", {"transition_id": transition_id}))
        if self.fail_load:
            raise RuntimeError("load failed")
        return self.transitions.get(transition_id)


class FakeReingestionTrigger:
    """Re-ingestion trigger fake that records calls and returns a fixed id."""

    def __init__(self, new_item_id: UUID | None = None) -> None:
        self.new_item_id = new_item_id
        self.calls: list[dict[str, Any]] = []

    async def trigger_reingestion(
        self,
        *,
        source_ref: str,
        is_static_standards: bool,
        correlation_id: str | None,
    ) -> UUID | None:
        self.calls.append(
            {
                "source_ref": source_ref,
                "is_static_standards": is_static_standards,
                "correlation_id": correlation_id,
            }
        )
        return self.new_item_id


def _candidate(
    item_id: UUID = _ITEM_1,
    *,
    file_exists: bool = True,
    new_version_hash: str | None = "hash-new",
    new_source_ref: str | None = None,
    is_static_standards: bool = False,
    embeddings: tuple[tuple[float, ...], tuple[float, ...]] | None = None,
) -> ModelStalenessCandidate:
    return ModelStalenessCandidate(
        item_id=item_id,
        source_ref="docs/README.md",
        current_version_hash="hash-old",
        new_version_hash=new_version_hash,
        new_source_ref=new_source_ref,
        file_exists=file_exists,
        current_embedding=embeddings[0] if embeddings else None,
        new_embedding=embeddings[1] if embeddings else None,
        is_static_standards=is_static_standards,
    )


def _input(
    *candidates: ModelStalenessCandidate,
    dry_run: bool = False,
    similarity_threshold: float = 0.85,
    stat_carry_fraction: float = 0.7,
) -> ModelStalenessDetectInput:
    return ModelStalenessDetectInput(
        candidates=tuple(candidates),
        similarity_threshold=similarity_threshold,
        stat_carry_fraction=stat_carry_fraction,
        dry_run=dry_run,
        correlation_id="corr-1",
    )


def _transition(
    item_id: UUID,
    case: EnumStalenessCase,
    step: EnumStalenessTransitionStep,
    *,
    new_item_id: UUID | None = None,
    stat_carry_applied: bool = False,
    similarity: float | None = None,
    new_source_ref: str | None = None,
) -> ModelStalenessTransition:
    return ModelStalenessTransition(
        transition_id=item_id,
        old_item_id=item_id,
        source_ref="docs/README.md",
        new_source_ref=new_source_ref,
        new_item_id=new_item_id,
        staleness_case=case,
        current_step=step,
        stat_carry_applied=stat_carry_applied,
        embedding_similarity=similarity,
        correlation_id="corr-1",
    )


def _deps(
    existing: Callable[[], dict[UUID, ModelStalenessTransition]] | None = None,
    *,
    new_item_id: UUID | None = _NEW_ITEM,
    verify_pg: bool = True,
    verify_qdrant: bool = True,
    fail_blacklist_for: frozenset[UUID] = frozenset(),
    fail_load: bool = False,
    qdrant_collection: str | None = None,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        deps: dict[str, Any] = {
            "staleness_store": FakeStalenessStore(
                existing() if existing else None,
                verify_pg=verify_pg,
                verify_qdrant=verify_qdrant,
                fail_blacklist_for=fail_blacklist_for,
                fail_load=fail_load,
            ),
            "reingestion_trigger": FakeReingestionTrigger(new_item_id),
        }
        if qdrant_collection is not None:
            deps["qdrant_collection"] = qdrant_collection
        return deps

    return build


_REPO = EnumStalenessCase.CONTENT_CHANGED_REPO
_STATIC = EnumStalenessCase.CONTENT_CHANGED_STATIC
_Step = EnumStalenessTransitionStep

PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], ModelStalenessDetectInput],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "file-deleted",
        CLASS_NAME,
        lambda: _input(_candidate(file_exists=False)),
        _deps(),
    ),
    (
        "file-moved",
        CLASS_NAME,
        lambda: _input(_candidate(new_source_ref="docs/NEW.md")),
        _deps(),
    ),
    (
        "static-content-changed",
        CLASS_NAME,
        lambda: _input(_candidate(is_static_standards=True)),
        _deps(),
    ),
    (
        "repo-content-stat-carry",
        CLASS_NAME,
        lambda: _input(_candidate(embeddings=_SIMILAR)),
        _deps(),
    ),
    (
        "repo-content-low-similarity",
        CLASS_NAME,
        lambda: _input(_candidate(embeddings=_ORTHOGONAL)),
        _deps(),
    ),
    (
        "repo-content-no-embeddings",
        CLASS_NAME,
        lambda: _input(_candidate()),
        _deps(),
    ),
    (
        "no-detectable-change-defaults-to-repo",
        CLASS_NAME,
        lambda: _input(_candidate(new_version_hash=None)),
        _deps(),
    ),
    (
        "custom-threshold-and-collection",
        CLASS_NAME,
        lambda: _input(
            _candidate(embeddings=_SIMILAR),
            similarity_threshold=0.999,
            stat_carry_fraction=0.5,
        ),
        _deps(qdrant_collection="custom_collection"),
    ),
    (
        "verify-pg-fails",
        CLASS_NAME,
        lambda: _input(_candidate()),
        _deps(verify_pg=False),
    ),
    (
        "verify-qdrant-fails",
        CLASS_NAME,
        lambda: _input(_candidate()),
        _deps(verify_qdrant=False),
    ),
    (
        "trigger-returns-no-id",
        CLASS_NAME,
        lambda: _input(_candidate()),
        _deps(new_item_id=None),
    ),
    (
        "resume-from-index-new",
        CLASS_NAME,
        lambda: _input(_candidate(embeddings=_SIMILAR)),
        _deps(
            lambda: {
                _ITEM_1: _transition(
                    _ITEM_1, _REPO, _Step.INDEX_NEW, new_item_id=_NEW_ITEM
                )
            }
        ),
    ),
    (
        "resume-from-verify-new",
        CLASS_NAME,
        lambda: _input(_candidate()),
        _deps(
            lambda: {
                _ITEM_1: _transition(
                    _ITEM_1,
                    _REPO,
                    _Step.VERIFY_NEW,
                    new_item_id=_NEW_ITEM,
                    stat_carry_applied=True,
                    similarity=0.95,
                )
            }
        ),
    ),
    (
        "resume-unexpected-step",
        CLASS_NAME,
        lambda: _input(_candidate()),
        _deps(
            lambda: {
                _ITEM_1: _transition(
                    _ITEM_1, _REPO, _Step.BLACKLIST_OLD, new_item_id=_NEW_ITEM
                )
            }
        ),
    ),
    (
        "already-complete-skipped",
        CLASS_NAME,
        lambda: _input(_candidate(file_exists=False)),
        _deps(lambda: {_ITEM_1: _transition(_ITEM_1, _REPO, _Step.COMPLETE)}),
    ),
    (
        "existing-file-moved-pending",
        CLASS_NAME,
        lambda: _input(_candidate(new_source_ref="docs/NEW.md")),
        _deps(
            lambda: {
                _ITEM_1: _transition(
                    _ITEM_1,
                    EnumStalenessCase.FILE_MOVED,
                    _Step.PENDING,
                    new_source_ref="docs/NEW.md",
                )
            }
        ),
    ),
    (
        "dry-run-mixed-batch",
        CLASS_NAME,
        lambda: _input(
            _candidate(_ITEM_1, file_exists=False),
            _candidate(_ITEM_2, new_source_ref="docs/NEW.md"),
            _candidate(_ITEM_3),
            dry_run=True,
        ),
        _deps(),
    ),
    (
        "mixed-batch-all-cases",
        CLASS_NAME,
        lambda: _input(
            _candidate(_ITEM_1, file_exists=False),
            _candidate(_ITEM_2, new_source_ref="docs/NEW.md"),
            _candidate(_ITEM_3, is_static_standards=True),
        ),
        _deps(),
    ),
    (
        "empty-candidates",
        CLASS_NAME,
        lambda: _input(),
        _deps(),
    ),
    (
        "partial-failure-blacklist-raises",
        CLASS_NAME,
        lambda: _input(
            _candidate(_ITEM_1, file_exists=False),
            _candidate(_ITEM_2, file_exists=False),
        ),
        _deps(fail_blacklist_for=frozenset({_ITEM_1})),
    ),
    (
        "load-transition-raises",
        CLASS_NAME,
        lambda: _input(_candidate(), _candidate(_ITEM_2, file_exists=False)),
        _deps(fail_load=True),
    ),
]


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(request_builder().model_dump(mode="json"), default=str)
            ),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], ModelStalenessDetectInput],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """The wrapper returns (or raises) exactly what the preserved function does."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = function_result = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = await handle_staleness_detection(request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
    assert deps_a["staleness_store"].calls == deps_b["staleness_store"].calls
    assert (
        deps_a["staleness_store"].transitions == deps_b["staleness_store"].transitions
    )
    assert deps_a["reingestion_trigger"].calls == deps_b["reingestion_trigger"].calls
