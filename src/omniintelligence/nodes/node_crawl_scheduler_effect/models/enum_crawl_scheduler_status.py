# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Status enum for crawl scheduler handler results.

Reference: OMN-2384
"""

from enum import Enum


class EnumCrawlSchedulerStatus(str, Enum):
    """Outcome status for a single crawl scheduling operation.

    EMITTED:
        A crawl-tick.v1 command was successfully published to Kafka.
        The debounce window was set (or reset if this was the first trigger
        after a document-indexed.v1 reset event).

    DEBOUNCED:
        The trigger was silently dropped because an active debounce window
        exists for the ``(source_ref, crawler_type)`` key.  No Kafka message
        was published.

    ERROR:
        An unexpected error occurred.  The handler returned a structured
        result rather than raising.  The error_message field contains details.
    """

    EMITTED = "emitted"
    DEBOUNCED = "debounced"
    ERROR = "error"


__all__ = ["EnumCrawlSchedulerStatus"]
