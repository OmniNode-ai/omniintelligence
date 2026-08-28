# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OmniIntelligence - ONEX-compliant intelligence nodes.

This package provides code quality analysis and intelligence operations
as first-class ONEX nodes.

Quick Start - Quality Scoring:
    >>> from omniintelligence import score_code_quality, OnexStrictnessLevel
    >>> result = score_code_quality(
    ...     content="class Model(BaseModel): x: int",
    ...     language="python",
    ...     preset=OnexStrictnessLevel.STRICT,
    ... )
    >>> result["success"]
    True
    >>> result["quality_score"]  # 0.0 to 1.0
    0.65

The quality-scoring symbols above are resolved on first access rather than at
import time (PEP 562). They pull in `omnibase_core`'s full model tree, measured
at 1.888 s of a 2.420 s import; because this module is the package root, every
consumer of every submodule used to pay that cost whether or not they touched
quality scoring. Context serving -- which never uses any of it -- was paying
78% of its import budget for symbols it does not reference. See OMN-16764.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Import-time only: gives type checkers and IDEs the real signatures while
    # costing nothing at runtime. The runtime path is __getattr__ below.
    from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
        DEFAULT_WEIGHTS as DEFAULT_WEIGHTS,
    )
    from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
        DimensionScores as DimensionScores,
    )
    from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
        OnexStrictnessLevel as OnexStrictnessLevel,
    )
    from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
        QualityScoringComputeError as QualityScoringComputeError,
    )
    from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
        QualityScoringResult as QualityScoringResult,
    )
    from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
        QualityScoringValidationError as QualityScoringValidationError,
    )
    from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
        score_code_quality as score_code_quality,
    )

# Do not hardcode versions here; version is sourced from distribution metadata.
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("omninode-intelligence")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

#: Re-exported from `node_quality_scoring_compute.handlers` on first access.
_LAZY_EXPORTS = frozenset(
    {
        "DEFAULT_WEIGHTS",
        "DimensionScores",
        "OnexStrictnessLevel",
        "QualityScoringComputeError",
        "QualityScoringResult",
        "QualityScoringValidationError",
        "score_code_quality",
    }
)


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """Resolve a quality-scoring export on first access, then cache it.

    `omnibase_core` is a required runtime dependency for full functionality, but
    the previous eager import was wrapped in `contextlib.suppress(ImportError)`
    so the package would still import in environments without it (pre-commit
    isolated venvs, CI without editable installs) -- the symbols were simply
    absent. That behaviour is preserved here: a missing dependency surfaces as
    `AttributeError`, exactly as before, with the underlying ImportError chained
    so the real cause is still visible.
    """

    if name not in _LAZY_EXPORTS:
        message = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(message)

    try:
        from omniintelligence.nodes.node_quality_scoring_compute import handlers
    except ImportError as exc:  # pragma: no cover - requires omnibase_core absent
        message = (
            f"{name!r} requires omnibase_core, which is not installed. "
            "Install it to use the quality-scoring API."
        )
        raise AttributeError(message) from exc

    value = getattr(handlers, name)
    # Cache on the module so subsequent lookups skip __getattr__ entirely.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Advertise the deferred exports to `dir()` and tab-completion."""

    return sorted(set(globals()) | _LAZY_EXPORTS)


__all__ = [
    # Configuration
    "DEFAULT_WEIGHTS",
    "DimensionScores",
    "OnexStrictnessLevel",
    "QualityScoringComputeError",
    # Types
    "QualityScoringResult",
    # Exceptions
    "QualityScoringValidationError",
    # Main API
    "score_code_quality",
]
