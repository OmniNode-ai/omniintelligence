"""Intelligence Orchestrator - Declarative workflow orchestrator.

This orchestrator follows the ONEX declarative pattern:
    - DECLARATIVE orchestrator driven by contract.yaml
    - Zero custom routing logic - all behavior from workflow_coordination
    - Lightweight shell that delegates to NodeOrchestrator base class
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, workflow routing"

Extends NodeOrchestrator from omnibase_core for workflow management.
All workflow routing and execution is 100% driven by contract.yaml.

Workflow Routing:
    - DOCUMENT_INGESTION: Vectorize, extract entities, store in Qdrant/Memgraph
    - PATTERN_LEARNING: 4-phase pattern learning (Foundation -> Matching -> Validation -> Traceability)
    - QUALITY_ASSESSMENT: Score code quality, check ONEX compliance
    - SEMANTIC_ANALYSIS: Generate embeddings, compute similarity
    - RELATIONSHIP_DETECTION: Detect and classify relationships

Design Decisions:
    - 100% Contract-Driven: All workflow logic in YAML, not Python
    - Zero Custom Methods: Base class handles everything
    - Declarative Execution: Workflows defined in workflow_coordination
    - Llama Index Integration: Uses Llama Index for workflow orchestration
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

    All workflow routing and node coordination are driven entirely by the
    contract.yaml workflow_coordination configuration.
    """

    # No custom __init__ needed - uses NodeOrchestrator's default initialization


__all__ = ["NodeIntelligenceOrchestrator"]
