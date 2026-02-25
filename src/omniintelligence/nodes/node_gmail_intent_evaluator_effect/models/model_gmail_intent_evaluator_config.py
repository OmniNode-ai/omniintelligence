# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Input configuration model for the Gmail Intent Evaluator.

Populated from the onex.evt.omnibase_infra.gmail-intent-received.v1 Kafka event payload.

Reference:
    - OMN-2788: Add ModelGmailIntentEvaluatorConfig + ModelGmailIntentEvaluationResult
    - OMN-2787: Gmail Intent Evaluator — Email-to-Initial-Plan Pipeline
"""

from pydantic import BaseModel, ConfigDict


class ModelGmailIntentEvaluatorConfig(BaseModel):
    """Input model populated from gmail-intent-received.v1 event payload.

    Attributes:
        message_id: Unique Gmail message identifier.
        subject: Email subject line.
        body_text: Email body text, already truncated to 4096 chars by the poller.
        urls: List of URLs extracted from the email body.
        source_label: Gmail label that triggered the event (e.g. "To Read").
        sender: Sender email address.
        received_at: ISO-8601 timestamp when the email was received.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    message_id: str
    subject: str
    body_text: str  # Already truncated to 4096 chars by poller
    urls: list[str]
    source_label: str
    sender: str
    received_at: str  # ISO-8601
