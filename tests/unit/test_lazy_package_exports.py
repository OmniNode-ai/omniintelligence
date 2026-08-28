# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-16764: importing the package must not drag in the quality-scoring tree.

`omniintelligence/__init__.py` eagerly imported
`nodes.node_quality_scoring_compute.handlers`, which transitively builds the
whole `omnibase_core` Pydantic model tree. Measured with `-X importtime` against
the context-serving entrypoint, that single import was 1.888 s of a 2.420 s
total -- 78% -- and context serving never uses any of it.

Because the import sat at package level, *anything* importing *any*
`omniintelligence` submodule paid it. These tests pin the fix: the symbols stay
importable, but nothing loads until someone actually asks for one.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit

#: The public symbols `__init__.py` re-exports from the quality-scoring handlers.
LAZY_EXPORTS = (
    "DEFAULT_WEIGHTS",
    "DimensionScores",
    "OnexStrictnessLevel",
    "QualityScoringComputeError",
    "QualityScoringResult",
    "QualityScoringValidationError",
    "score_code_quality",
)

_QUALITY_SCORING_MODULE = "omniintelligence.nodes.node_quality_scoring_compute"


def _in_fresh_interpreter(code: str) -> str:
    """Run `code` in a clean interpreter and return its stdout.

    A subprocess is required: by the time this test runs, the pytest session has
    almost certainly imported the quality-scoring tree already, so checking
    `sys.modules` in-process would prove nothing.
    """

    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_importing_the_package_does_not_load_quality_scoring() -> None:
    """The 1.888 s import must not happen just because someone imported us."""

    loaded = _in_fresh_interpreter(
        "import sys, omniintelligence; "
        f"print({_QUALITY_SCORING_MODULE!r} in sys.modules)"
    )
    assert loaded == "False", (
        "importing omniintelligence pulled in the quality-scoring tree; "
        "the package-level import is no longer lazy"
    )


def test_importing_context_serving_does_not_load_quality_scoring() -> None:
    """The serving path is the reason this matters -- it uses none of it."""

    loaded = _in_fresh_interpreter(
        "import sys; "
        "from omniintelligence.code_projection.context_serving.service import "
        "CodeContextProcessor; "
        f"print({_QUALITY_SCORING_MODULE!r} in sys.modules)"
    )
    assert loaded == "False", (
        "importing the context-serving entrypoint pulled in the quality-scoring "
        "tree, which it never uses"
    )


@pytest.mark.parametrize("name", LAZY_EXPORTS)
def test_lazy_export_still_resolves(name: str) -> None:
    """Deferring the import must not remove the symbol from the public API."""

    import omniintelligence

    assert getattr(omniintelligence, name) is not None


def test_lazy_export_matches_the_handler_module() -> None:
    """The re-exported object is the same object, not a copy or a shim."""

    import omniintelligence
    from omniintelligence.nodes.node_quality_scoring_compute import handlers

    for name in LAZY_EXPORTS:
        assert getattr(omniintelligence, name) is getattr(handlers, name), name


def test_unknown_attribute_still_raises_attribute_error() -> None:
    """`__getattr__` must not swallow genuine typos into an import attempt."""

    import omniintelligence

    with pytest.raises(AttributeError, match="no attribute"):
        _ = omniintelligence.definitely_not_a_real_symbol


def test_dir_advertises_the_lazy_exports() -> None:
    """`dir()` and tab-completion should still show the deferred symbols."""

    import omniintelligence

    advertised = set(dir(omniintelligence))
    assert set(LAZY_EXPORTS) <= advertised
