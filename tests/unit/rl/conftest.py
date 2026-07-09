# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Collection guard for the RL unit tests.

The RL training modules (``src/omniintelligence/rl/``) and these tests import
``torch``, which lives in the opt-in, non-default ``rl`` dependency group
(OMN-14176). The default install and the review path are deliberately torch-free,
so when ``torch`` is not importable we skip collecting this directory entirely —
otherwise pytest would error on import at collection time. Run the RL suite with
``uv sync --group rl`` to install CUDA torch and exercise these tests.
"""

from __future__ import annotations

import importlib.util

if importlib.util.find_spec("torch") is None:
    # Ignore every test module in this directory when torch is not installed.
    collect_ignore_glob = ["*"]
