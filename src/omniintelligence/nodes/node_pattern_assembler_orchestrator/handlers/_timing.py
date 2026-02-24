# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Shared timing utilities for pattern assembler orchestrator handlers."""

from __future__ import annotations

import time

__all__ = [
    "elapsed_time_ms",
    "elapsed_time_seconds",
    "safe_elapsed_time_ms",
]


def elapsed_time_ms(start_time: float) -> float:
    """Calculate elapsed time in milliseconds."""
    return (time.perf_counter() - start_time) * 1000


def elapsed_time_seconds(start_time: float) -> float:
    """Calculate elapsed time in seconds."""
    return time.perf_counter() - start_time


def safe_elapsed_time_ms(start_time: float) -> float:
    """Safely calculate elapsed time, returning 0 on error."""
    try:
        return elapsed_time_ms(start_time)
    except Exception:
        return 0.0
