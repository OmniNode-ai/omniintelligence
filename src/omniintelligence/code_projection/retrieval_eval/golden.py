# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Golden query set for the OMN-16522 retrieval eval harness.

The set is deliberately small.  The published corpus exposes two retrievable
chunk keys, so six positives -- two documents times three genuinely distinct
intents -- exhausts the honest positive space; a fourth phrasing per document
would paraphrase one of those three rather than add a new correct answer.
Four non-redundant negatives complete the set at ten rows.

Volume comes from parameterizing each row over replay state rather than from
adding rows: a row is evaluated at every state where it has a deterministic
expected result.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Committed golden-set artifact shipped with the harness.
DEFAULT_GOLDEN_SET_PATH = (
    Path(__file__).resolve().parent / "baselines/golden_query_set_v1.json"
)

#: Honest sizing bounds derived from the corpus, not chosen.  A set larger than
#: the ceiling is paraphrase padding: it manufactures query volume without
#: adding a single new correct answer.
GOLDEN_SET_MINIMUM_ROWS = 8
GOLDEN_SET_MAXIMUM_ROWS = 10


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)


class ModelGoldenExpectation(_FrozenModel):
    """The judged-relevant document set for one query at one replay state."""

    lane_id: str
    expected_document_ids: tuple[str, ...]

    @property
    def expects_empty(self) -> bool:
        """Return whether no document in the corpus answers this query here."""

        return not self.expected_document_ids


class ModelGoldenQuery(_FrozenModel):
    """One developer question, with its expectation at each replay state."""

    query_id: str
    query_text: str = Field(min_length=1)
    intent: str
    polarity: Literal["positive", "negative"]
    rationale: str | None = None
    expectations: tuple[ModelGoldenExpectation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_duplicate_lanes(self) -> ModelGoldenQuery:
        lane_ids = [expectation.lane_id for expectation in self.expectations]
        if len(set(lane_ids)) != len(lane_ids):
            message = f"{self.query_id} expects two results at the same replay state"
            raise ValueError(message)
        return self


class ModelGoldenQuerySet(_FrozenModel):
    """The committed golden set, with its sizing ceiling enforced on load."""

    golden_set_version: str
    ticket: str
    corpus_manifest_id: str
    judged_by: str
    sizing_note: str
    queries: tuple[ModelGoldenQuery, ...]

    @model_validator(mode="after")
    def _enforce_honest_sizing(self) -> ModelGoldenQuerySet:
        if not (
            GOLDEN_SET_MINIMUM_ROWS <= len(self.queries) <= GOLDEN_SET_MAXIMUM_ROWS
        ):
            message = (
                f"golden set carries {len(self.queries)} rows; the honest range for "
                f"this corpus is {GOLDEN_SET_MINIMUM_ROWS}-{GOLDEN_SET_MAXIMUM_ROWS}"
            )
            raise ValueError(message)
        query_ids = [query.query_id for query in self.queries]
        if len(set(query_ids)) != len(query_ids):
            message = "golden set carries duplicate query_id values"
            raise ValueError(message)
        return self

    @property
    def labeled_query_count(self) -> int:
        """Return Q: the number of labeled golden queries, for the arming rule."""

        return len(self.queries)

    def assertion_count(self) -> int:
        """Return the number of ``(query, replay-state)`` pairs this set yields."""

        return sum(len(query.expectations) for query in self.queries)

    def expectations_by_lane(self) -> Mapping[str, tuple[ModelGoldenQuery, ...]]:
        """Group the queries by the replay state each is evaluated at."""

        grouped: dict[str, list[ModelGoldenQuery]] = {}
        for query in self.queries:
            for expectation in query.expectations:
                grouped.setdefault(expectation.lane_id, []).append(query)
        return {lane_id: tuple(queries) for lane_id, queries in grouped.items()}


def load_golden_query_set(path: Path | None = None) -> ModelGoldenQuerySet:
    """Load and validate the committed golden query set."""

    source = DEFAULT_GOLDEN_SET_PATH if path is None else path
    return ModelGoldenQuerySet.model_validate(
        json.loads(source.read_text(encoding="utf-8"))
    )


__all__ = [
    "DEFAULT_GOLDEN_SET_PATH",
    "GOLDEN_SET_MAXIMUM_ROWS",
    "GOLDEN_SET_MINIMUM_ROWS",
    "ModelGoldenExpectation",
    "ModelGoldenQuery",
    "ModelGoldenQuerySet",
    "load_golden_query_set",
]
