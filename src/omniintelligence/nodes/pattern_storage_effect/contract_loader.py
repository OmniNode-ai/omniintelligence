# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Contract loader for declarative effect nodes.

Loads contract.yaml and provides runtime dispatch based on handler_routing.
This enables fully declarative effect nodes where the contract drives execution.

The ContractLoader provides:
    - YAML contract loading with caching
    - Handler resolution from module.function paths
    - Entry point discovery for main execution
    - Event bus topic discovery (subscribe/publish)
    - Handler caching for performance

Usage:
    from omniintelligence.nodes.pattern_storage_effect.contract_loader import (
        ContractLoader,
        get_contract_loader,
    )

    # Get loader for this node
    loader = get_contract_loader()

    # Resolve handler for operation
    handler = loader.resolve_handler("store_pattern")
    if handler:
        result = await handler(input_data)

    # Get entry point
    entry = loader.get_entry_point()

    # Get topics
    subscribe = loader.subscribe_topics
    publish = loader.publish_topics

Reference:
    - OMN-1668: Pattern storage effect node implementation
"""

from __future__ import annotations

import importlib
from pathlib import Path
from collections.abc import Callable
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class HandlerConfig(BaseModel):
    """Handler configuration from contract.

    Attributes:
        function: Function name to import and call.
        module: Module path containing the function.
        type: Handler type (async or sync). Defaults to async.
        description: Optional human-readable description.
    """

    function: str
    module: str
    type: str = "async"
    description: str | None = None


class OperationHandler(BaseModel):
    """Operation-to-handler mapping from contract.

    Attributes:
        operation: Operation name that triggers this handler.
        handler: Handler configuration for this operation.
        description: Human-readable description of the operation.
        actions: List of actions performed by this handler.
    """

    operation: str
    handler: HandlerConfig
    description: str | None = None
    actions: list[str] = Field(default_factory=list)


class HandlerRouting(BaseModel):
    """Handler routing configuration from contract.

    Attributes:
        routing_strategy: Strategy for routing operations (e.g., operation_match).
        entry_point: Main entry point handler configuration.
        handlers: List of operation-to-handler mappings.
        default_handler: Fallback handler for unrecognized operations.
    """

    routing_strategy: str = "operation_match"
    entry_point: HandlerConfig | None = None
    handlers: list[OperationHandler] = Field(default_factory=list)
    default_handler: HandlerConfig | None = None


class EventBusConfig(BaseModel):
    """Event bus configuration from contract.

    Attributes:
        version: Event bus configuration version.
        event_bus_enabled: Whether event bus is enabled.
        subscribe_topics: Topics this node subscribes to.
        publish_topics: Topics this node publishes to.
        subscribe_topic_metadata: Metadata for subscribed topics.
        publish_topic_metadata: Metadata for published topics.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    version: dict[str, int] = Field(default_factory=lambda: {"major": 1, "minor": 0, "patch": 0})
    event_bus_enabled: bool = True
    subscribe_topics: list[str] = Field(default_factory=list)
    publish_topics: list[str] = Field(default_factory=list)
    subscribe_topic_metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)
    publish_topic_metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ContractLoader:
    """Loads and resolves contract.yaml for declarative dispatch.

    The ContractLoader parses a YAML contract file and provides runtime
    resolution of handlers based on operation types. This enables fully
    declarative effect nodes where behavior is driven by the contract.

    Attributes:
        contract_path: Path to the contract.yaml file.

    Example:
        loader = ContractLoader(Path("contract.yaml"))

        # Get handler for operation
        handler = loader.resolve_handler("store_pattern")
        result = await handler(input_data)

        # Get entry point
        entry = loader.get_entry_point()

        # Get topics
        subscribe = loader.subscribe_topics
        publish = loader.publish_topics
    """

    def __init__(self, contract_path: Path | str) -> None:
        """Initialize the contract loader.

        Args:
            contract_path: Path to the contract.yaml file.
        """
        self._contract_path = Path(contract_path)
        self._contract: dict[str, Any] = {}
        self._handler_cache: dict[str, Callable[..., Any]] = {}
        self._entry_point_cache: Callable[..., Any] | None = None
        self._load_contract()

    def _load_contract(self) -> None:
        """Load contract YAML from file."""
        with open(self._contract_path) as f:
            self._contract = yaml.safe_load(f)

    def reload_contract(self) -> None:
        """Reload contract from file and clear caches.

        Useful for hot-reloading configuration changes during development.
        """
        self._handler_cache.clear()
        self._entry_point_cache = None
        self._load_contract()

    @property
    def contract(self) -> dict[str, Any]:
        """Get the raw contract dictionary.

        Returns:
            Full contract dictionary as loaded from YAML.
        """
        return self._contract

    @property
    def node_name(self) -> str:
        """Get the node name from contract.

        Returns:
            Node name string.
        """
        return self._contract.get("node_name", self._contract.get("name", "unknown"))

    @property
    def node_type(self) -> str:
        """Get the node type from contract.

        Returns:
            Node type string (e.g., EFFECT_GENERIC).
        """
        return self._contract.get("node_type", "unknown")

    @property
    def handler_routing(self) -> HandlerRouting:
        """Get handler routing configuration.

        Returns:
            HandlerRouting model with routing configuration.
        """
        routing_data = self._contract.get("handler_routing", {})

        # Convert raw handler dicts to OperationHandler models
        handlers_raw = routing_data.get("handlers", [])
        handlers = []
        for h in handlers_raw:
            handlers.append(
                OperationHandler(
                    operation=h.get("operation", ""),
                    handler=HandlerConfig(**h.get("handler", {})),
                    description=h.get("description"),
                    actions=h.get("actions", []),
                )
            )

        # Build entry_point if present
        entry_point = None
        if "entry_point" in routing_data:
            entry_point = HandlerConfig(**routing_data["entry_point"])

        # Build default_handler if present
        default_handler = None
        if "default_handler" in routing_data:
            default_handler = HandlerConfig(**routing_data["default_handler"])

        return HandlerRouting(
            routing_strategy=routing_data.get("routing_strategy", "operation_match"),
            entry_point=entry_point,
            handlers=handlers,
            default_handler=default_handler,
        )

    @property
    def event_bus(self) -> EventBusConfig:
        """Get event bus configuration.

        Returns:
            EventBusConfig model with event bus settings.
        """
        event_bus_data = self._contract.get("event_bus", {})
        return EventBusConfig(**event_bus_data)

    def _import_function(self, config: HandlerConfig) -> Callable[..., Any]:
        """Import a function from module path.

        Args:
            config: Handler configuration with module and function.

        Returns:
            Imported callable function.

        Raises:
            ImportError: If module cannot be imported.
            AttributeError: If function not found in module.
        """
        module = importlib.import_module(config.module)
        return getattr(module, config.function)

    def resolve_handler(self, operation: str) -> Callable[..., Any] | None:
        """Resolve handler function for operation.

        Looks up the handler configuration for the given operation and
        dynamically imports the handler function. Results are cached.

        Args:
            operation: Operation name to resolve handler for.

        Returns:
            Handler callable or None if not found.

        Example:
            handler = loader.resolve_handler("store_pattern")
            if handler:
                result = await handler(input_data)
        """
        # Check cache first
        if operation in self._handler_cache:
            return self._handler_cache[operation]

        routing = self.handler_routing

        # Find handler config for operation
        handler_config: HandlerConfig | None = None
        for handler in routing.handlers:
            if handler.operation == operation:
                handler_config = handler.handler
                break

        # Fall back to default handler
        if handler_config is None and routing.default_handler:
            handler_config = routing.default_handler

        if handler_config is None:
            return None

        # Import and cache
        func = self._import_function(handler_config)
        self._handler_cache[operation] = func
        return func

    def get_entry_point(self) -> Callable[..., Any] | None:
        """Get the main entry point function.

        Returns the entry point handler that routes to operation-specific
        handlers. This is the main function to call when processing events.

        Returns:
            Entry point callable or None if not configured.

        Example:
            entry = loader.get_entry_point()
            if entry:
                result = await entry(input_data)
        """
        if self._entry_point_cache is not None:
            return self._entry_point_cache

        routing = self.handler_routing
        if routing.entry_point is None:
            return None

        self._entry_point_cache = self._import_function(routing.entry_point)
        return self._entry_point_cache

    def get_handler_for_default(self) -> Callable[..., Any] | None:
        """Get the default handler function.

        Returns:
            Default handler callable or None if not configured.
        """
        routing = self.handler_routing
        if routing.default_handler is None:
            return None

        cache_key = "__default__"
        if cache_key in self._handler_cache:
            return self._handler_cache[cache_key]

        func = self._import_function(routing.default_handler)
        self._handler_cache[cache_key] = func
        return func

    def list_operations(self) -> list[str]:
        """List all configured operations.

        Returns:
            List of operation names that have handlers.
        """
        return [h.operation for h in self.handler_routing.handlers]

    def get_operation_metadata(self, operation: str) -> OperationHandler | None:
        """Get metadata for an operation.

        Args:
            operation: Operation name to get metadata for.

        Returns:
            OperationHandler with description and actions, or None.
        """
        for handler in self.handler_routing.handlers:
            if handler.operation == operation:
                return handler
        return None

    @property
    def subscribe_topics(self) -> list[str]:
        """Get Kafka subscribe topics.

        Returns:
            List of topic names this node subscribes to.
        """
        return self.event_bus.subscribe_topics

    @property
    def publish_topics(self) -> list[str]:
        """Get Kafka publish topics.

        Returns:
            List of topic names this node publishes to.
        """
        return self.event_bus.publish_topics

    @property
    def event_bus_enabled(self) -> bool:
        """Check if event bus is enabled.

        Returns:
            True if event bus integration is enabled.
        """
        return self.event_bus.event_bus_enabled

    def get_topic_schema(self, topic: str, is_subscribe: bool = True) -> str | None:
        """Get schema reference for a topic.

        Args:
            topic: Topic name to get schema for.
            is_subscribe: Whether this is a subscribe topic (else publish).

        Returns:
            Schema reference string or None if not found.
        """
        event_bus = self.event_bus
        metadata = (
            event_bus.subscribe_topic_metadata
            if is_subscribe
            else event_bus.publish_topic_metadata
        )
        topic_meta = metadata.get(topic, {})
        return topic_meta.get("schema_ref")


# Module-level cached loader instance
_cached_loader: ContractLoader | None = None


def get_contract_loader(
    node_dir: Path | str | None = None,
    use_cache: bool = True,
) -> ContractLoader:
    """Get contract loader for pattern_storage_effect node.

    Factory function that creates or returns a cached ContractLoader
    instance for this node's contract.yaml.

    Args:
        node_dir: Directory containing contract.yaml. Defaults to this
            module's directory.
        use_cache: Whether to use/update the module-level cache.

    Returns:
        ContractLoader instance for this node.

    Example:
        # Use cached loader
        loader = get_contract_loader()

        # Force new loader
        loader = get_contract_loader(use_cache=False)

        # Custom directory
        loader = get_contract_loader("/path/to/node")
    """
    global _cached_loader

    if use_cache and _cached_loader is not None:
        return _cached_loader

    if node_dir is None:
        node_dir = Path(__file__).parent

    contract_path = Path(node_dir) / "contract.yaml"
    loader = ContractLoader(contract_path)

    if use_cache:
        _cached_loader = loader

    return loader


def clear_loader_cache() -> None:
    """Clear the module-level loader cache.

    Useful for testing or hot-reloading scenarios.
    """
    global _cached_loader
    _cached_loader = None


# Rebuild models to resolve forward references from __future__ annotations
# This is required for Pydantic 2.x when using PEP 563 deferred annotations
HandlerConfig.model_rebuild()
OperationHandler.model_rebuild()
HandlerRouting.model_rebuild()
EventBusConfig.model_rebuild()
