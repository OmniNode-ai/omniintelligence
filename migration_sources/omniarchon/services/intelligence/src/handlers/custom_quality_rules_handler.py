"""
Custom Quality Rules Event Handler

Handles custom quality rules request events and publishes completed/failed responses.
Implements event-driven interface for rule evaluation, registration, and management.

Handles 8 event types:
1. EVALUATE_REQUESTED → EVALUATE_COMPLETED/FAILED
2. GET_RULES_REQUESTED → GET_RULES_COMPLETED/FAILED
3. LOAD_CONFIG_REQUESTED → LOAD_CONFIG_COMPLETED/FAILED
4. REGISTER_REQUESTED → REGISTER_COMPLETED/FAILED
5. ENABLE_REQUESTED → ENABLE_COMPLETED/FAILED
6. DISABLE_REQUESTED → DISABLE_COMPLETED/FAILED
7. CLEAR_REQUESTED → CLEAR_COMPLETED/FAILED
8. HEALTH_REQUESTED → HEALTH_COMPLETED/FAILED

Created: 2025-10-22
Purpose: Event-driven custom quality rules integration for Phase 3
"""

import logging
import os
import time
from typing import Any, Dict
from uuid import UUID

from src.events.models.custom_quality_rules_events import (
    CustomRulesEventHelpers,
    EnumCustomRulesErrorCode,
    EnumCustomRulesEventType,
    ModelCustomRulesClearCompletedPayload,
    ModelCustomRulesClearFailedPayload,
    ModelCustomRulesClearRequestPayload,
    ModelCustomRulesDisableCompletedPayload,
    ModelCustomRulesDisableFailedPayload,
    ModelCustomRulesDisableRequestPayload,
    ModelCustomRulesEnableCompletedPayload,
    ModelCustomRulesEnableFailedPayload,
    ModelCustomRulesEnableRequestPayload,
    ModelCustomRulesEvaluateCompletedPayload,
    ModelCustomRulesEvaluateFailedPayload,
    ModelCustomRulesEvaluateRequestPayload,
    ModelCustomRulesGetRulesCompletedPayload,
    ModelCustomRulesGetRulesFailedPayload,
    ModelCustomRulesGetRulesRequestPayload,
    ModelCustomRulesHealthCompletedPayload,
    ModelCustomRulesHealthFailedPayload,
    ModelCustomRulesLoadConfigCompletedPayload,
    ModelCustomRulesLoadConfigFailedPayload,
    ModelCustomRulesLoadConfigRequestPayload,
    ModelCustomRulesRegisterCompletedPayload,
    ModelCustomRulesRegisterFailedPayload,
    ModelCustomRulesRegisterRequestPayload,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)

# Intelligence service URL - configurable via environment variable
INTELLIGENCE_SERVICE_URL = os.getenv(
    "INTELLIGENCE_SERVICE_URL", "http://localhost:8053"  # Fallback for local dev only
)


class CustomQualityRulesHandler(BaseResponsePublisher):
    """Handle custom quality rules request events and publish results."""

    def __init__(self):
        super().__init__()
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "operations_by_type": {},
        }

    def can_handle(self, event_type: str) -> bool:
        try:
            EnumCustomRulesEventType(event_type)
            return "REQUESTED" in event_type
        except ValueError:
            return any(
                k in event_type.lower()
                for k in [
                    "evaluate",
                    "get_rules",
                    "load_config",
                    "register",
                    "enable",
                    "disable",
                    "clear",
                    "health",
                ]
            )

    async def handle_event(self, event: Any) -> bool:
        start_time = time.perf_counter()
        correlation_id = None
        try:
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)
            # Extract event_type from direct attribute or metadata (supports both test mocks and omnibase_core pattern)
            if isinstance(event, dict):
                metadata = event.get("metadata", {})
                event_type_str = metadata.get("event_type", event.get("event_type", ""))
            else:
                # First try direct attribute (for test mocks), then metadata (for omnibase_core)
                event_type_str = getattr(event, "event_type", "")
                if not event_type_str:
                    metadata = getattr(event, "metadata", {})
                    if isinstance(metadata, dict):
                        event_type_str = metadata.get("event_type", "")

            if "evaluate" in event_type_str.lower():
                return await self._handle_evaluate(correlation_id, payload, start_time)
            elif (
                "get_rules" in event_type_str.lower()
                or "get-rules" in event_type_str.lower()
            ):
                return await self._handle_get_rules(correlation_id, payload, start_time)
            elif (
                "load_config" in event_type_str.lower()
                or "load-config" in event_type_str.lower()
            ):
                return await self._handle_load_config(
                    correlation_id, payload, start_time
                )
            elif "register" in event_type_str.lower():
                return await self._handle_register(correlation_id, payload, start_time)
            elif "enable" in event_type_str.lower():
                return await self._handle_enable(correlation_id, payload, start_time)
            elif "disable" in event_type_str.lower():
                return await self._handle_disable(correlation_id, payload, start_time)
            elif "clear" in event_type_str.lower():
                return await self._handle_clear(correlation_id, payload, start_time)
            elif "health" in event_type_str.lower():
                return await self._handle_health(correlation_id, payload, start_time)
            else:
                logger.error(f"Unknown custom rules operation: {event_type_str}")
                return False
        except Exception as e:
            logger.error(
                f"Custom rules handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_evaluate(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            req = ModelCustomRulesEvaluateRequestPayload(**payload)
            logger.info(
                f"Processing EVALUATE_REQUESTED | cid={cid} | project_id={req.project_id}"
            )
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{INTELLIGENCE_SERVICE_URL}/api/custom-rules/evaluate",
                    json=payload,
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesEvaluateCompletedPayload(**res, processing_time_ms=dur)
            e = CustomRulesEventHelpers.create_event_envelope(
                "evaluate_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.EVALUATE_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("evaluate")
            return True
        except Exception as e:
            logger.error(f"Evaluate failed: {e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesEvaluateFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                error_message=str(e),
                error_code=EnumCustomRulesErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = CustomRulesEventHelpers.create_event_envelope(
                "evaluate_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.EVALUATE_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_get_rules(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            req = ModelCustomRulesGetRulesRequestPayload(**payload)
            logger.info(
                f"Processing GET_RULES_REQUESTED | cid={cid} | project_id={req.project_id}"
            )
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{INTELLIGENCE_SERVICE_URL}/api/custom-rules/project/{req.project_id}/rules"
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesGetRulesCompletedPayload(**res, processing_time_ms=dur)
            e = CustomRulesEventHelpers.create_event_envelope(
                "get_rules_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.GET_RULES_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("get_rules")
            return True
        except Exception as e:
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesGetRulesFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                error_message=str(e),
                error_code=EnumCustomRulesErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = CustomRulesEventHelpers.create_event_envelope(
                "get_rules_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.GET_RULES_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_load_config(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            req = ModelCustomRulesLoadConfigRequestPayload(**payload)
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{INTELLIGENCE_SERVICE_URL}/api/custom-rules/project/{req.project_id}/load-config",
                    json=payload,
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesLoadConfigCompletedPayload(
                **res, processing_time_ms=dur
            )
            e = CustomRulesEventHelpers.create_event_envelope(
                "load_config_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.LOAD_CONFIG_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("load_config")
            return True
        except Exception as e:
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesLoadConfigFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                config_path=payload.get("config_path", "unknown"),
                error_message=str(e),
                error_code=EnumCustomRulesErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = CustomRulesEventHelpers.create_event_envelope(
                "load_config_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.LOAD_CONFIG_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_register(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            req = ModelCustomRulesRegisterRequestPayload(**payload)
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{INTELLIGENCE_SERVICE_URL}/api/custom-rules/project/{req.project_id}/rule",
                    json=payload,
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesRegisterCompletedPayload(**res, processing_time_ms=dur)
            e = CustomRulesEventHelpers.create_event_envelope(
                "register_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.REGISTER_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("register")
            return True
        except Exception as e:
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesRegisterFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                rule_id=payload.get("rule_id", "unknown"),
                error_message=str(e),
                error_code=EnumCustomRulesErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = CustomRulesEventHelpers.create_event_envelope(
                "register_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.REGISTER_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_enable(self, cid: str, payload: dict, start_time: float) -> bool:
        try:
            req = ModelCustomRulesEnableRequestPayload(**payload)
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{INTELLIGENCE_SERVICE_URL}/api/custom-rules/project/{req.project_id}/rule/{req.rule_id}/enable"
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesEnableCompletedPayload(**res, processing_time_ms=dur)
            e = CustomRulesEventHelpers.create_event_envelope(
                "enable_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.ENABLE_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("enable")
            return True
        except Exception as e:
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesEnableFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                rule_id=payload.get("rule_id", "unknown"),
                error_message=str(e),
                error_code=EnumCustomRulesErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = CustomRulesEventHelpers.create_event_envelope(
                "enable_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.ENABLE_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_disable(self, cid: str, payload: dict, start_time: float) -> bool:
        try:
            req = ModelCustomRulesDisableRequestPayload(**payload)
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{INTELLIGENCE_SERVICE_URL}/api/custom-rules/project/{req.project_id}/rule/{req.rule_id}/disable"
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesDisableCompletedPayload(**res, processing_time_ms=dur)
            e = CustomRulesEventHelpers.create_event_envelope(
                "disable_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.DISABLE_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("disable")
            return True
        except Exception as e:
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesDisableFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                rule_id=payload.get("rule_id", "unknown"),
                error_message=str(e),
                error_code=EnumCustomRulesErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = CustomRulesEventHelpers.create_event_envelope(
                "disable_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.DISABLE_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_clear(self, cid: str, payload: dict, start_time: float) -> bool:
        try:
            req = ModelCustomRulesClearRequestPayload(**payload)
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{INTELLIGENCE_SERVICE_URL}/api/custom-rules/project/{req.project_id}/rules"
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesClearCompletedPayload(**res, processing_time_ms=dur)
            e = CustomRulesEventHelpers.create_event_envelope(
                "clear_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.CLEAR_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("clear")
            return True
        except Exception as e:
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesClearFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                error_message=str(e),
                error_code=EnumCustomRulesErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = CustomRulesEventHelpers.create_event_envelope(
                "clear_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.CLEAR_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_health(self, cid: str, payload: dict, start_time: float) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{INTELLIGENCE_SERVICE_URL}/api/custom-rules/health"
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesHealthCompletedPayload(**res, processing_time_ms=dur)
            e = CustomRulesEventHelpers.create_event_envelope(
                "health_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.HEALTH_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("health")
            return True
        except Exception as e:
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelCustomRulesHealthFailedPayload(
                error_message=str(e),
                error_code=EnumCustomRulesErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = CustomRulesEventHelpers.create_event_envelope(
                "health_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                CustomRulesEventHelpers.get_kafka_topic(
                    EnumCustomRulesEventType.HEALTH_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    def _increment_operation_metric(self, op: str) -> None:
        if op not in self.metrics["operations_by_type"]:
            self.metrics["operations_by_type"][op] = 0
        self.metrics["operations_by_type"][op] += 1

    def get_handler_name(self) -> str:
        return "CustomQualityRulesHandler"

    def get_metrics(self) -> Dict[str, Any]:
        total = self.metrics["events_handled"] + self.metrics["events_failed"]
        return {
            **self.metrics,
            "success_rate": (
                self.metrics["events_handled"] / total if total > 0 else 1.0
            ),
            "avg_processing_time_ms": (
                self.metrics["total_processing_time_ms"]
                / self.metrics["events_handled"]
                if self.metrics["events_handled"] > 0
                else 0.0
            ),
            "handler_name": self.get_handler_name(),
        }
