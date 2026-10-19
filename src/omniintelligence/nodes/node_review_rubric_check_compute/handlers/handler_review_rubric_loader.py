# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Load a review rubric file under a token budget (OMN-21186).

Pure: text in, a rubric or a named refusal out. The checks run in a fixed
order -- yaml, mapping, schema version, field shape, content hash, token
budget -- and the first failure is the refusal, so a file is always refused for
one stable reason.

The token budget counts what a reviewer prompt would carry: each rule's
category and instruction, then each hint. Support counts, ``created_from`` and
repositories are evidence for the distiller and cost the reviewer nothing, so
they do not count. Tokens are counted with the repository's shared tokenizer
(``util_token_counter``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

import yaml
from pydantic import ValidationError

from omniintelligence.nodes.node_review_rubric_check_compute.models.enum_review_rubric_refusal import (
    EnumReviewRubricRefusal,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rubric import (
    REVIEW_RUBRIC_SCHEMA_VERSION,
    ModelReviewRubric,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rubric_load import (
    ModelReviewRubricLoad,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rubric_refusal import (
    ModelReviewRubricRefusal,
)
from omniintelligence.utils.util_token_counter import count_tokens

_HASH_KEY = "content_hash"


def compute_content_hash(mapping: Mapping[str, Any]) -> str:
    """``sha256:`` over the canonical json of every key but ``content_hash``."""
    body = {key: value for key, value in mapping.items() if key != _HASH_KEY}
    canonical = json.dumps(
        body, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def rubric_prompt_text(rubric: ModelReviewRubric) -> str:
    """The rubric text a reviewer prompt would carry; the budget counts this."""
    lines = [f"{rule.category}: {rule.instruction}" for rule in rubric.rules]
    lines.extend(rubric.hints)
    return "\n".join(lines)


def _refuse(
    code: EnumReviewRubricRefusal,
    source: str,
    detail: str,
    *,
    field: str = "",
    token_count: int = 0,
) -> ModelReviewRubricLoad:
    return ModelReviewRubricLoad(
        refusal=ModelReviewRubricRefusal(
            code=code, field=field, message=f"review rubric {source}: {detail}"
        ),
        token_count=token_count,
    )


def _field_path(location: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in location)


def load_review_rubric(
    text: str, *, token_budget: int, source: str = "<rubric>"
) -> ModelReviewRubricLoad:
    """Read ``text`` as a ``review_rubric.v1`` file within ``token_budget``."""
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return _refuse(
            EnumReviewRubricRefusal.NOT_YAML, source, f"not valid yaml ({exc})"
        )
    if not isinstance(raw, dict):
        return _refuse(
            EnumReviewRubricRefusal.NOT_A_MAPPING,
            source,
            f"top level must be a mapping, got {type(raw).__name__}",
        )
    if raw.get("schema_version") != REVIEW_RUBRIC_SCHEMA_VERSION:
        return _refuse(
            EnumReviewRubricRefusal.UNSUPPORTED_SCHEMA_VERSION,
            source,
            f"schema_version must be {REVIEW_RUBRIC_SCHEMA_VERSION!r}, "
            f"got {raw.get('schema_version')!r}",
            field="schema_version",
        )
    try:
        rubric = ModelReviewRubric.model_validate(raw)
    except ValidationError as exc:
        problems = [(_field_path(error["loc"]), error["msg"]) for error in exc.errors()]
        detail = "; ".join(f"{path}: {msg}" if path else msg for path, msg in problems)
        return _refuse(
            EnumReviewRubricRefusal.MALFORMED, source, detail, field=problems[0][0]
        )
    expected = compute_content_hash(raw)
    if rubric.content_hash != expected:
        return _refuse(
            EnumReviewRubricRefusal.CONTENT_HASH_MISMATCH,
            source,
            f"content_hash {rubric.content_hash} does not match the content ({expected})",
            field=_HASH_KEY,
        )
    token_count = count_tokens(rubric_prompt_text(rubric))
    if token_count > token_budget:
        return _refuse(
            EnumReviewRubricRefusal.OVER_BUDGET,
            source,
            f"{token_count} tokens, over the budget of {token_budget}",
            token_count=token_count,
        )
    return ModelReviewRubricLoad(rubric=rubric, token_count=token_count)


__all__ = ["compute_content_hash", "load_review_rubric", "rubric_prompt_text"]
