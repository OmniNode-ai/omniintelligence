# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Error taxonomy enum for CI failure classification.

Ticket: OMN-3556
"""

from __future__ import annotations

from enum import StrEnum


class EnumErrorTaxonomy(StrEnum):
    """Taxonomy of CI error classifications.

    Used by node_ci_error_classifier_compute to normalize LLM output
    to a controlled vocabulary.
    """

    UNKNOWN = "unknown"
    TEST_FAILURE = "test_failure"
    FLAKY_TEST = "flaky_test"
    INFRA_FAILURE = "infra_failure"
    BUILD_FAILURE = "build_failure"
    TIMEOUT = "timeout"
    DEPENDENCY_FAILURE = "dependency_failure"
    LINTING_FAILURE = "linting_failure"
    TYPE_ERROR = "type_error"


__all__ = ["EnumErrorTaxonomy"]
