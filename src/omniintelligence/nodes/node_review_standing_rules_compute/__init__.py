# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Standing-rules validation and weakening guard (OMN-20784).

COMPUTE node: ``handle(ModelStandingRulesRequest) -> ModelStandingRulesResult`` validates
the reviewed repository's standing rules file and, when asked, compares the pull
request's copy against it. The caller reads the files; the node does no I/O.
"""
