# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Off-CI receipt issuing with the findings recorded beside it (OMN-20981).

COMPUTE node: ``handle(ModelIssueReceiptRequest) -> ModelIssuedReceipt`` signs
the unchanged review receipt and returns the ``ModelReviewRecorded`` that holds
the findings the receipt counts. Pure: the findings, the key and the clock are
inputs.
"""
