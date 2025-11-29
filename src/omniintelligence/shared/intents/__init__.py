"""
Intent routing and handling utilities.

Provides utilities for creating, routing, and processing intents
in the omniintelligence system.
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..enums import EnumIntentType, EnumOperationType, EnumFSMType
from ..models import ModelIntent


class IntentFactory:
    """Factory for creating common intent types."""

    @staticmethod
    def create_state_update_intent(
        fsm_type: EnumFSMType,
        entity_id: str,
        new_state: str,
        correlation_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModelIntent:
        """Create a state update intent for the reducer."""
        return ModelIntent(
            intent_type=EnumIntentType.STATE_UPDATE,
            target="intelligence_reducer",
            payload={
                "fsm_type": fsm_type,
                "entity_id": entity_id,
                "new_state": new_state,
            },
            correlation_id=correlation_id,
            metadata=metadata,
        )

    @staticmethod
    def create_workflow_trigger_intent(
        operation_type: EnumOperationType,
        entity_id: str,
        payload: Dict[str, Any],
        correlation_id: str,
    ) -> ModelIntent:
        """Create a workflow trigger intent for the orchestrator."""
        return ModelIntent(
            intent_type=EnumIntentType.WORKFLOW_TRIGGER,
            target="intelligence_orchestrator",
            payload={
                "operation_type": operation_type,
                "entity_id": entity_id,
                **payload,
            },
            correlation_id=correlation_id,
        )

    @staticmethod
    def create_event_publish_intent(
        topic: str,
        event_type: str,
        event_payload: Dict[str, Any],
        correlation_id: str,
    ) -> ModelIntent:
        """Create an event publish intent for Kafka."""
        return ModelIntent(
            intent_type=EnumIntentType.EVENT_PUBLISH,
            target="kafka_event_effect",
            payload={
                "topic": topic,
                "event_type": event_type,
                "payload": event_payload,
            },
            correlation_id=correlation_id,
        )

    @staticmethod
    def create_cache_invalidate_intent(
        cache_scope: str,
        cache_key_pattern: str,
        correlation_id: str,
    ) -> ModelIntent:
        """Create a cache invalidation intent."""
        return ModelIntent(
            intent_type=EnumIntentType.CACHE_INVALIDATE,
            target="cache_service",
            payload={
                "scope": cache_scope,
                "key_pattern": cache_key_pattern,
            },
            correlation_id=correlation_id,
        )

    @staticmethod
    def create_error_notification_intent(
        error_message: str,
        error_context: Dict[str, Any],
        correlation_id: str,
    ) -> ModelIntent:
        """Create an error notification intent."""
        return ModelIntent(
            intent_type=EnumIntentType.ERROR_NOTIFICATION,
            target="error_handler",
            payload={
                "error": error_message,
                "context": error_context,
            },
            correlation_id=correlation_id,
        )


class IntentRouter:
    """Routes intents to appropriate handlers."""

    def __init__(self):
        self._handlers: Dict[str, List[callable]] = {}

    def register_handler(self, target: str, handler: callable):
        """Register a handler for a specific target."""
        if target not in self._handlers:
            self._handlers[target] = []
        self._handlers[target].append(handler)

    def route_intent(self, intent: ModelIntent) -> List[Any]:
        """Route an intent to registered handlers."""
        handlers = self._handlers.get(intent.target, [])
        results = []
        for handler in handlers:
            result = handler(intent)
            results.append(result)
        return results

    def route_batch(self, intents: List[ModelIntent]) -> Dict[str, List[Any]]:
        """Route multiple intents and return results by target."""
        results_by_target = {}
        for intent in intents:
            if intent.target not in results_by_target:
                results_by_target[intent.target] = []
            results = self.route_intent(intent)
            results_by_target[intent.target].extend(results)
        return results_by_target


def generate_correlation_id(prefix: str = "corr") -> str:
    """Generate a unique correlation ID."""
    return f"{prefix}_{uuid4().hex[:16]}"


__all__ = [
    "IntentFactory",
    "IntentRouter",
    "generate_correlation_id",
]
