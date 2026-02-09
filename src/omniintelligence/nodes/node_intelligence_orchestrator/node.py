"""Intelligence Orchestrator - Declarative workflow orchestrator.

This orchestrator follows the ONEX declarative pattern:
    - DECLARATIVE orchestrator driven by contract.yaml
    - Lightweight shell that delegates to NodeOrchestrator base class
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, workflow routing"

Extends NodeOrchestrator from omnibase_core for workflow management.
All workflow routing and execution is driven by contract.yaml.

Workflow Routing:
    - DOCUMENT_INGESTION: Vectorize, extract entities, store in Qdrant/Memgraph
    - PATTERN_LEARNING: 4-phase pattern learning (Foundation -> Matching -> Validation -> Traceability)
    - QUALITY_ASSESSMENT: Score code quality, check ONEX compliance
    - SEMANTIC_ANALYSIS: Generate embeddings, compute similarity
    - RELATIONSHIP_DETECTION: Detect and classify relationships

Intent Reception (OMN-2034):
    The orchestrator receives ModelIntent events emitted by the intelligence
    reducer. Intent reception handlers are defined in the handlers package
    and wired via contract.yaml handler_routing. The node class itself remains
    a pure shell with no custom methods.

    Handlers:
        - handle_receive_intent: Receive and log a single intent
        - handle_receive_intents: Receive and log a batch of intents

    See: handlers/handler_receive_intent.py

Design Decisions:
    - Contract-Driven: All workflow logic in YAML, not Python
    - Pure Shell: Node has zero custom methods (ONEX purity invariant)
    - Declarative Execution: Workflows defined in workflow_coordination
    - Handler-Based Intent Channel: Handlers routed by RuntimeHostProcess

Ticket: OMN-2034
"""

from __future__ import annotations

from omnibase_core.nodes.node_orchestrator import NodeOrchestrator


class NodeIntelligenceOrchestrator(NodeOrchestrator):
    """Intelligence orchestrator - workflow routing driven by contract.yaml.

    This orchestrator coordinates intelligence workflows by:
    1. Receiving operation requests (via process() method)
    2. Routing to appropriate workflow defined in contract.yaml
    3. Executing compute and effect nodes as defined in workflow_coordination
    4. Publishing outcome events

    Intent Reception (OMN-2034):
        Reducer intents are received by handler functions defined in
        handlers/handler_receive_intent.py and routed via contract.yaml
        handler_routing configuration. The node class remains a pure shell.

    All workflow routing and node coordination are driven entirely by the
    contract.yaml workflow_coordination configuration.
    """

    # No custom methods - pure shell.
    # Intent reception handlers are in handlers/handler_receive_intent.py
    # and wired via contract.yaml handler_routing.


__all__ = ["NodeIntelligenceOrchestrator"]
