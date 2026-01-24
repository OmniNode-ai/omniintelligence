# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Intelligence Adapter Effect Node - Declarative effect node for code analysis.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for event-driven I/O operations.
All handler routing is 100% driven by contract.yaml, not Python code.

Handler Routing Pattern:
    1. Runtime subscribes to consumed_events topics (from contract)
    2. Runtime routes events to handlers based on handler_routing section
    3. Handlers process events and return ModelHandlerOutput.for_effect()
    4. Runtime publishes returned events to published_events topics

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Zero Custom Routing: Base class handles handler dispatch via contract
    - Declarative Handlers: handler_routing section defines dispatch rules
    - External Wiring: Handlers resolved via container dependency injection

Node Responsibilities:
    - Define I/O model contract (ModelIntelligenceInput -> ModelIntelligenceOutput)
    - Provide dependency injection points for intelligence service client
    - Delegate all execution to handlers via base class

The actual handler execution and routing is performed by:
    - RuntimeHostProcess (for event-driven execution)
    - Or direct handler invocation by callers

Related Modules:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/: Event handlers (HandlerCodeAnalysisRequested, etc.)
    - models/events/: Event payload models

Migration Notes (OMN-1437):
    This declarative node replaces the imperative 2397-line implementation.
    All routing logic has been moved to contract.yaml handler_routing.
    Event payload models extracted to omniintelligence.models.events.
    Enums extracted to omniintelligence.enums.enum_code_analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

if TYPE_CHECKING:
    from typing import Any, Protocol

    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

    class ProtocolIntelligenceClient(Protocol):
        """Protocol for intelligence service client.

        TODO: Move to omnibase_spi when standardized across nodes.
        """

        async def analyze_code(
            self, content: str, operation_type: str, options: dict[str, Any]
        ) -> dict[str, Any]:
            """Analyze code and return results."""
            ...


class NodeIntelligenceAdapterEffect(NodeEffect):
    """Declarative effect node for code analysis via Kafka events.

    This effect node is a lightweight shell that defines the I/O contract
    for code analysis operations. All routing and execution logic is driven
    by contract.yaml - this class contains no custom routing code.

    Handler coordination is performed by:
        - RuntimeHostProcess for event-driven execution
        - Direct handler invocation for testing

    Supported Operations (defined in contract.yaml handler_routing):
        - CODE_ANALYSIS_REQUESTED: Analyze code quality, patterns, performance

    Published Events:
        - CODE_ANALYSIS_COMPLETED: Successful analysis with results
        - CODE_ANALYSIS_FAILED: Analysis failure with error details

    Dependency Injection:
        The intelligence service client is injected via setter method.
        Handlers access the client through the container.

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.intelligence_adapter import NodeIntelligenceAdapterEffect
        from omniintelligence.nodes.intelligence_adapter.handlers import (
            HandlerCodeAnalysisRequested,
        )

        # Create effect node
        container = ModelONEXContainer()
        effect = NodeIntelligenceAdapterEffect(container)

        # Wire intelligence client
        effect.set_intelligence_client(intelligence_client)

        # Execute via handlers directly (for testing)
        handler = HandlerCodeAnalysisRequested()
        result = await handler.handle(envelope)

        # Or use RuntimeHostProcess for event-driven execution
        # (runtime reads contract, subscribes to Kafka, routes to handlers)
        ```
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the effect node.

        Args:
            container: ONEX dependency injection container providing:
                - Intelligence service client
                - Handler instances
                - Configuration
        """
        super().__init__(container)

        # Intelligence service client (injected via setter)
        self._intelligence_client: ProtocolIntelligenceClient | None = None

    def set_intelligence_client(self, client: ProtocolIntelligenceClient) -> None:
        """Set the intelligence service client.

        Args:
            client: Protocol-compliant intelligence client implementation.
        """
        self._intelligence_client = client

    @property
    def intelligence_client(self) -> ProtocolIntelligenceClient | None:
        """Get the intelligence client if configured."""
        return self._intelligence_client

    @property
    def has_intelligence_client(self) -> bool:
        """Check if intelligence client is configured."""
        return self._intelligence_client is not None


__all__ = ["NodeIntelligenceAdapterEffect"]
