# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""One finding of a compact review verdict (OMN-20910)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.models.review.model_review_standing_rule import RULE_ID_PATTERN

NOTE_MAX_LENGTH: int = 120
"""Longest note a finding carries."""

CODE_PATTERN: str = r"^[A-Z][0-9]{2}$"
"""A catalog code: a family letter and two digits."""

UNCODED: str = "X"
"""The code of a finding no catalog code fits; it requires a family and a note."""

RULE_PREFIX: str = "R:"
"""Prefix of a code that cites one of the reviewed repository's standing rules."""

_CODE = re.compile(CODE_PATTERN)
_RULE_ID = re.compile(RULE_ID_PATTERN)


class ModelReviewFindingCompact(BaseModel):
    """``{"c":"T01","p":"src/x.py","l":42,"s":"M"}``, plus ``y`` and ``n`` when needed.

    Attributes:
        c: A catalog code, ``R:<standing rule id>`` or ``X``.
        p: Repository-relative path.
        line: Line number, 0 for a file-level finding (wire key ``l``).
        s: Severity: ``C`` critical, ``M`` major, ``m`` minor, ``n`` nit.
        y: Family. Required for ``X`` and ``R:`` codes, forbidden otherwise
            because the catalog fixes it.
        n: Short note. Required for ``X``.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, populate_by_name=False
    )

    c: str = Field(min_length=1, description="Catalog code, 'R:<rule id>' or 'X'.")
    p: str = Field(min_length=1, description="Repository-relative path.")
    line: int = Field(alias="l", ge=0, description="Line number; 0 for file-level.")
    s: Literal["C", "M", "m", "n"] = Field(description="Severity.")
    y: (
        Literal[
            "architecture",
            "security",
            "performance",
            "correctness",
            "completeness",
            "feasibility",
            "testing",
            "style",
        ]
        | None
    ) = Field(default=None, description="Family; for X and R: codes only.")
    n: str | None = Field(
        default=None, max_length=NOTE_MAX_LENGTH, description="Note; required for X."
    )

    @model_validator(mode="after")
    def _code_shape_and_family(self) -> ModelReviewFindingCompact:
        if self.c == UNCODED:
            if self.y is None or not self.n:
                raise ValueError("an X finding requires a family and a note")
        elif self.c.startswith(RULE_PREFIX):
            if not _RULE_ID.fullmatch(self.c[len(RULE_PREFIX) :]):
                raise ValueError("an R: code names a standing rule id")
            if self.y is None:
                raise ValueError("an R: finding requires a family")
        else:
            if not _CODE.fullmatch(self.c):
                raise ValueError("a code is a family letter and two digits")
            if self.y is not None:
                raise ValueError(
                    "a catalog finding carries no family; the catalog fixes it"
                )
        return self


__all__ = [
    "CODE_PATTERN",
    "NOTE_MAX_LENGTH",
    "RULE_PREFIX",
    "UNCODED",
    "ModelReviewFindingCompact",
]
