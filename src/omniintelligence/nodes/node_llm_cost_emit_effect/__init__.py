# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""LLM cost telemetry emit node (OMN-6801).

EFFECT node: ``HandlerLlmCostEmitter.handle(ModelLlmCostEmitRequest) -> ModelLlmCostEmitResult``
publishes one LLM call cost event, fail-open, through an injected Kafka producer.
"""
