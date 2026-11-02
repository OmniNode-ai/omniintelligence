# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Committed harness baselines: the golden query set and the baseline scorecard.

Named ``baselines`` rather than ``artifacts`` deliberately: the repository
.gitignore carries a blanket ``artifacts/`` rule for build output, which would
silently exclude these committed files from the tree.
"""

from __future__ import annotations

from pathlib import Path

_ARTIFACT_ROOT = Path(__file__).resolve().parent

#: The judged golden query set, sized to the corpus ceiling.
GOLDEN_QUERY_SET_PATH = _ARTIFACT_ROOT / "golden_query_set_v1.json"

#: The reference every future harness run is compared against.
BASELINE_SCORECARD_PATH = _ARTIFACT_ROOT / "baseline_scorecard.json"

__all__ = [
    "BASELINE_SCORECARD_PATH",
    "GOLDEN_QUERY_SET_PATH",
]
