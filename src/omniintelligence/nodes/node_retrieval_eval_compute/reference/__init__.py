# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Committed harness reference data: the golden query set and the reference scorecard.

Named ``reference`` rather than ``artifacts`` deliberately: the repository
.gitignore carries a blanket ``artifacts/`` rule for build output, which would
silently exclude these committed files from the tree.
"""

from __future__ import annotations

from pathlib import Path

_REFERENCE_ROOT = Path(__file__).resolve().parent

#: The judged golden query set, sized to the corpus ceiling.
GOLDEN_QUERY_SET_PATH = _REFERENCE_ROOT / "golden_query_set_v1.json"

#: The reference scorecard every future harness run is compared against.
REFERENCE_SCORECARD_PATH = _REFERENCE_ROOT / "reference_scorecard.json"

__all__ = [
    "GOLDEN_QUERY_SET_PATH",
    "REFERENCE_SCORECARD_PATH",
]
