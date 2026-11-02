# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""No class, provider, endpoint or host is a literal in the verifier node (OMN-22175)."""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.nodes import (
    node_review_agent_receipt_verify_compute as node_package,
)

pytestmark = pytest.mark.unit

_NODE_DIR = Path(node_package.__file__).parent
_LOADER = _NODE_DIR.parents[1] / "handlers" / "handler_review_agent_receipt_overlay.py"
_FORBIDDEN_LITERALS = ("anthropic", "gateway", "8140")


def test_handler_source_names_no_policy_literal() -> None:
    handlers = sorted((_NODE_DIR / "handlers").glob("*.py"))
    assert any(
        path.name == "handler_review_agent_receipt_verify.py" for path in handlers
    )
    for path in handlers:
        text = path.read_text(encoding="utf-8").lower()
        for literal in _FORBIDDEN_LITERALS:
            assert literal not in text, f"{literal!r} appears in {path.name}"


def test_models_and_loader_source_name_no_policy_literal() -> None:
    sources = sorted((_NODE_DIR / "models").glob("*.py")) + [_LOADER]
    assert len(sources) > 1
    for path in sources:
        text = path.read_text(encoding="utf-8").lower()
        for literal in _FORBIDDEN_LITERALS:
            assert literal not in text, f"{literal!r} appears in {path.name}"


def test_the_grep_finds_a_literal_when_there_is_one(tmp_path: Path) -> None:
    """Positive control: the same scan trips on a file that holds a literal."""
    planted = tmp_path / "planted.py"
    planted.write_text('PROVIDER = "Anthropic"\n', encoding="utf-8")
    text = planted.read_text(encoding="utf-8").lower()
    assert any(literal in text for literal in _FORBIDDEN_LITERALS)
