"""Pattern Compliance Effect Node - Thin shell delegating to handler.

Evaluates code against applicable patterns using Coder-14B (via ProtocolLlmClient).
This node follows the ONEX declarative pattern where the node class is a thin
shell that delegates all logic to handler functions.

Classified as EFFECT (not COMPUTE) because it performs external I/O via
ProtocolLlmClient.chat_completion(). COMPUTE nodes must be pure (no side effects).

Callers invoke the handler directly with their dependencies:
    result = await handle_pattern_compliance_compute(
        request, llm_client=client, model="Qwen/Qwen2.5-Coder-14B-Instruct"
    )

Or use RuntimeHostProcess for event-driven execution, which reads
handler_routing from contract.yaml.

Ticket: OMN-2256
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodePatternComplianceEffect(NodeEffect):
    """Effect node for evaluating code compliance against patterns.

    This node is a pure declarative shell following the ONEX pattern.
    All logic is delegated to handle_pattern_compliance_compute.

    Classified as EFFECT because the handler performs external LLM I/O
    via ProtocolLlmClient. COMPUTE nodes must be pure (no side effects).

    Handlers are invoked directly by callers with their dependencies
    (llm_client, model). This node contains NO instance variables
    for handlers or registries.

    Example::

        from omniintelligence.nodes.node_pattern_compliance_effect.handlers import (
            handle_pattern_compliance_compute,
        )

        result = await handle_pattern_compliance_compute(
            request,
            llm_client=my_llm_client,
            model="Qwen/Qwen2.5-Coder-14B-Instruct",
        )
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodePatternComplianceEffect"]
