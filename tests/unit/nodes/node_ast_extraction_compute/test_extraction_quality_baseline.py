# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Document AST extraction quality baseline and known gaps [OMN-7180].

These tests read the real NodeCompute source from omnibase_core, run it
through ``extract_entities_from_source``, and assert on the **current**
extraction behaviour.  Each test documents a specific capability or known
gap so that future improvements can be validated against this baseline.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers import (
    extract_entities_from_source,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _omni_home() -> Path:
    """Locate the omni_home root directory.

    Strategy:
    1. If OMNI_HOME env var is set, use that.
    2. Walk up from this file's directory looking for a directory that
       contains both ``omnibase_core/`` and ``omniintelligence/`` subdirs.

    Raises:
        RuntimeError: If omni_home cannot be found.
    """
    env_val = os.environ.get("OMNI_HOME")
    if env_val:
        p = Path(env_val)
        if p.is_dir():
            return p

    current = Path(__file__).resolve()
    for ancestor in current.parents:
        if (ancestor / "omnibase_core").is_dir() and (
            ancestor / "omniintelligence"
        ).is_dir():
            return ancestor

    msg = (
        "Cannot locate omni_home. Set the OMNI_HOME environment variable "
        "or run tests from within the omni_home tree."
    )
    raise RuntimeError(msg)


def _read_node_compute_source() -> str:
    """Read the NodeCompute source file from omnibase_core."""
    path = (
        _omni_home()
        / "omnibase_core"
        / "src"
        / "omnibase_core"
        / "nodes"
        / "node_compute.py"
    )
    return path.read_text(encoding="utf-8")


def _get_node_compute_entity() -> ModelCodeEntity:
    """Extract entities from NodeCompute and return the class entity."""
    source = _read_node_compute_source()
    result = extract_entities_from_source(
        source,
        file_path="src/omnibase_core/nodes/node_compute.py",
        source_repo="omnibase_core",
    )
    entities_by_name = {e.entity_name: e for e in result.entities}
    assert "NodeCompute" in entities_by_name, "NodeCompute entity not found"
    return entities_by_name["NodeCompute"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractionQualityBaseline:
    """Document what the AST extractor currently captures and what it misses."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.entity = _get_node_compute_entity()

    def test_bases_are_unparsed_ast_strings(self) -> None:
        """Bases are plain strings produced by ast.unparse, not resolved types.

        The extractor captures base class names as raw AST string
        representations.  'NodeCoreBase' should appear as a plain name
        rather than a fully-qualified import path.
        """
        bases = self.entity.bases
        assert len(bases) > 0, "Expected at least one base class"

        # All bases should be plain strings
        for base in bases:
            assert isinstance(base, str), f"Base {base!r} is not a string"

        # NodeCoreBase must be present as a plain name
        assert "NodeCoreBase" in bases, f"Expected 'NodeCoreBase' in bases, got {bases}"

    def test_methods_are_name_only(self) -> None:
        """Methods list contains dicts with 'name' but no 'args' key.

        This documents a known gap: the extractor currently captures
        method names but NOT method signatures (argument lists, return
        types, etc.).
        """
        methods = self.entity.methods
        assert len(methods) > 0, "Expected at least one method"

        for method in methods:
            assert isinstance(method, dict), f"Method entry is not a dict: {method!r}"
            assert "name" in method, f"Method dict missing 'name' key: {method!r}"
            # Known gap: 'args' is absent (not even set to None)
            assert method.get("args") is None, (
                f"Expected 'args' to be absent or None, got {method.get('args')!r}"
            )

    def test_signature_field_is_none(self) -> None:
        """The signature field on extracted class entities is None.

        This documents a known gap: the extractor does not populate the
        ``signature`` field for class entities.  A future enhancement
        could fill this with the class constructor signature or the
        canonical class header.
        """
        assert self.entity.signature is None, (
            f"Expected signature to be None, got {self.entity.signature!r}"
        )
