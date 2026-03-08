# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""NodeBloomEvalEffect - EFFECT node for Bloom evaluation orchestration.

Subscribes to: onex.cmd.omniintelligence.bloom-eval-run.v1
Publishes to:  onex.evt.omniintelligence.bloom-eval-completed.v1

Orchestration flow:
    1. Receive bloom-eval-run command from Kafka.
    2. Route to the correct handler based on failure_mode.domain:
       - CONTRACT_CREATION -> handler_bloom_eval_effect (contract path)
       - AGENT_EXECUTION   -> handler_bloom_eval_effect (agent path)
       - MEMORY_SYSTEM     -> handler_bloom_eval_effect (memory path)
    3. Publish bloom-eval-completed event with ModelEvalSuiteResult via producer.

This node does NOT return a typed result - all output is published via Kafka.
All routing logic is driven by contract.yaml handler_routing.

Related Tickets:
    - OMN-4016: Bloom framework (parent epic)
    - OMN-4027: Task 11 - Build NodeBloomEvalEffect + Kafka topics
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeBloomEvalEffect(NodeEffect):
    """Declarative EFFECT node for Bloom evaluation orchestration.

    Lightweight shell that defines the I/O contract for bloom-eval processing.
    All routing and execution logic is driven by contract.yaml - this class
    contains NO custom routing code.

    Subscribes to: onex.cmd.omniintelligence.bloom-eval-run.v1
    Publishes to:  onex.evt.omniintelligence.bloom-eval-completed.v1

    Handler entry point: handler_bloom_eval_effect.run_bloom_eval

    This node does NOT return a typed result - it publishes via injected producer.

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.node_bloom_eval_orchestrator.node import (
            NodeBloomEvalEffect,
        )

        container = ModelONEXContainer()
        effect = NodeBloomEvalEffect(container)
        # RuntimeHostProcess reads handler_routing from contract.yaml and
        # dispatches bloom-eval-run commands to run_bloom_eval().
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml.


__all__ = ["NodeBloomEvalEffect"]
