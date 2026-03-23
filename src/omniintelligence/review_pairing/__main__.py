# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Entry point for ``python -m omniintelligence.review_pairing``.

Delegates to the calibration CLI (cli_calibration.main).
"""

from __future__ import annotations

import sys

from omniintelligence.review_pairing.cli_calibration import main

sys.exit(main())
