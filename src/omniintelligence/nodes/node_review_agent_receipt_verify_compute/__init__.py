# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Agent review receipt verification (OMN-22175).

COMPUTE node: ``handle(ModelAgentReceiptVerifyRequest) -> ModelAgentReceiptVerdict``
checks a signed ``hostile_review_agent_receipt.v1`` against the exact pull request
head and returns ``accepted`` or one typed refusal. Pure: the receipt, the key, the
injected policy, the quorum size and the verification context are inputs; there is no
network and no clock.
"""
