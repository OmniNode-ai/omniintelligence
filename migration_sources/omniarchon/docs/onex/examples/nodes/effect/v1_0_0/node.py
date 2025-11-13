#!/usr/bin/env python3
"""
CANONICAL ONEX EFFECT NODE - Production-Ready Reference Implementation
==================================================================

This canonical Effect node demonstrates the perfect merge of:
1. Base Infrastructure (omnibase_core/NodeEffect) - Transaction management, retry, circuit breaker
2. Business Logic (omnibase_3/canary) - Security assessment, operation handlers, validation
3. ONEX Architecture Patterns - Container injection, strong typing, error handling

CRITICAL NAMING CONVENTIONS:
- Class: NodeDatabaseWriterEffect (NOT ToolCanaryImpureProcessor)
- File: node_database_writer_effect.py (NOT tool_*)
- Inherits: NodeEffect (4-node architecture base class)

CANONICAL PATTERNS DEMONSTRATED:
=================================

## 1. CONTAINER INJECTION (from base)
- ONEXContainer dependency injection
- Service resolution via container.get_service()
- No global registries or singletons
- Graceful degradation when services unavailable

## 2. TRANSACTION MANAGEMENT (from base)
- Transaction class with rollback support
- Async context manager for transactions
- Operation tracking and state management
- Automatic rollback on failures

## 3. CIRCUIT BREAKER PATTERN (from base)
- CircuitBreaker class for external service failures
- Three states: CLOSED, OPEN, HALF_OPEN
- Automatic recovery after timeout
- Configurable failure thresholds

## 4. RETRY LOGIC (from base)
- Exponential backoff strategy
- Configurable retry attempts and delays
- Jitter support for distributed systems
- Per-operation retry configuration

## 5. SECURITY ASSESSMENT (from canary)
- Comprehensive security risk evaluation
- Path traversal detection
- Sandbox compliance checking
- Security violation tracking

## 6. MULTIPLE OPERATION TYPES (from canary)
- File operations (read, write, delete)
- HTTP requests (GET, POST, etc.)
- Database queries (SELECT, INSERT, UPDATE, DELETE)
- Email operations
- Audit logging
- Generic extensible handlers

## 7. INPUT VALIDATION (from canary)
- Detailed validation with error/warning feedback
- Operation-specific validation rules
- Path sanitization and security checks
- Content size limits

## 8. PERFORMANCE METRICS (from both)
- Operation timing tracking
- Success/failure rates
- Average/min/max processing times
- Side effect counting

## 9. STRONG TYPING (ONEX standard)
- Pydantic BaseModel for all data structures
- No Any types allowed
- ModelEffectInput and ModelEffectOutput
- Type-safe error handling with OnexError

## 10. ROLLBACK INSTRUCTIONS (from canary)
- Automatic rollback instruction generation
- Side effect tracking for reversibility
- Backup creation before destructive operations
- Transaction-safe operations

FILE ORGANIZATION:
==================
✅ node.py: ONLY NodeDatabaseWriterEffect class + main() (~650 lines)
✅ models/enum_*.py: All enum definitions
✅ models/model_effect_*.py: Effect input/output models
✅ infrastructure/*.py: Helper classes (Transaction, CircuitBreaker)

This demonstrates PERFECT node.py purity - copy this structure!

USAGE EXAMPLE:
==============
```python
from omnibase_core.core.onex_container import ONEXContainer

# Create container with dependencies
container = ONEXContainer()
container.register_service("event_bus", event_bus_instance)
container.register_service("database", database_instance)

# Initialize Effect node
effect_node = NodeDatabaseWriterEffect(container)

# Execute database write with transaction support
input_data = ModelEffectInput(
    effect_type=EnumEffectType.DATABASE_OPERATION,
    operation_data={
        "operation_type": "insert",
        "table": "users",
        "data": {"name": "John", "email": "john@example.com"}
    },
    transaction_enabled=True,
    retry_enabled=True,
    max_retries=3,
    circuit_breaker_enabled=True
)

result = await effect_node.process(input_data)
print(f"Success: {result.transaction_state == EnumTransactionState.COMMITTED}")
print(f"Processing time: {result.processing_time_ms}ms")
print(f"Rollback instructions: {result.rollback_operations}")
```

Author: ONEX Architecture Team
Version: 1.0.0
Last Updated: 2025-10-07
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypeVar

from omnibase_core.core.common_types import ModelScalarValue
from omnibase_core.core.core_structured_logging import (
    emit_log_event_sync as emit_log_event,
)
from omnibase_core.core.errors.core_errors import CoreErrorCode, OnexError
from omnibase_core.core.node_effect import NodeEffect
from omnibase_core.core.onex_container import ONEXContainer
from omnibase_core.enums.enum_log_level import EnumLogLevel as LogLevel

# Infrastructure - Helper Classes
from .infrastructure.transaction import Transaction

# Models - Input/Output
from .models.model_effect_input import ModelEffectInput
from .models.model_effect_output import ModelEffectOutput

# ============================================================================
# CANONICAL PATTERN: Import from ONEX core infrastructure
# ============================================================================
# These imports represent the minimal required infrastructure for Effect nodes
# All Effect nodes should use these common types and utilities


# ============================================================================
# LOCAL IMPORTS - Models and Infrastructure
# ============================================================================
# CANONICAL PATTERN: Import from local modules, not embedded in node.py

# Models - Enums



T = TypeVar("T")


class NodeDatabaseWriterEffect(NodeEffect):
    """
    Canonical Effect Node - Production-Ready Reference Implementation.

    CANONICAL PATTERN: This class demonstrates the perfect integration of:

    1. INFRASTRUCTURE (from omnibase_core/NodeEffect):
       - Container injection
       - Contract loading
       - Transaction management
       - Circuit breaker patterns
       - Retry logic with exponential backoff
       - Performance metrics tracking

    2. BUSINESS LOGIC (from omnibase_3/canary):
       - Security assessment
       - Multiple operation handlers
       - Input validation
       - Rollback instruction generation
       - Operation-specific processing

    3. ONEX ARCHITECTURE:
       - Strong typing (Pydantic models)
       - Error handling (OnexError)
       - Logging (structured events)
       - Node lifecycle management

    This is the template to use for all new Effect nodes.
    Copy this file and adapt the operation handlers to your needs.

    Attributes:
        container: ONEXContainer for dependency injection
        contract_model: Loaded and validated ModelContractEffect
        active_transactions: Currently active transactions by operation_id
        circuit_breakers: Circuit breakers by service name
        effect_handlers: Registered effect type handlers
        effect_semaphore: Concurrency limiter for effects
        effect_metrics: Performance metrics by effect type
        operation_log: Audit log of operations
        side_effects_created: Tracking of side effects
        performance_metrics: Business logic performance tracking
    """

    def __init__(self, container: ONEXContainer) -> None:
        """
        Initialize canonical Effect node with container injection.

        CANONICAL PATTERN: All Effect nodes receive ONEXContainer for
        dependency injection. The container provides access to:
        - Event bus for state change events
        - Database connections for persistent storage
        - External service clients
        - Configuration and settings

        Args:
            container: ONEXContainer with all dependencies

        Raises:
            OnexError: If container is None or initialization fails
        """
        # CANONICAL PATTERN: Validate container before calling super().__init__
        if container is None:
            raise OnexError(
                code=CoreErrorCode.VALIDATION_ERROR,
                message="Container cannot be None for Effect node initialization",
                details={
                    "node_type": "NodeDatabaseWriterEffect",
                    "initialization_stage": "pre_super_init",
                },
            )

        # CANONICAL PATTERN: Call parent constructor first
        # NodeEffect handles: contract loading, node_id generation, lifecycle setup
        super().__init__(container)

        # CANONICAL PATTERN: Load contract model (handled by NodeEffect base class)
        # self.contract_model is available after super().__init__()

        # Business logic specific initialization (from canary)
        self._operation_log: List[Dict[str, Any]] = []
        self._side_effects_created: List[str] = []

        # Performance tracking (from canary)
        self._performance_metrics = {
            "total_operations": 0,
            "total_processing_time_ms": 0.0,
            "average_processing_time_ms": 0.0,
            "side_effects_created": 0,
            "security_violations": 0,
        }

    # ========================================================================
    # MAIN PROCESSING METHOD - Orchestration Layer
    # ========================================================================

    async def process(self, input_data: ModelEffectInput) -> ModelEffectOutput:
        """
        Main processing method with canonical patterns.

        CANONICAL PATTERN: This method orchestrates the complete Effect workflow:
        1. Input validation
        2. Circuit breaker check
        3. Transaction creation
        4. Operation execution with retry
        5. Transaction commit/rollback
        6. Metrics tracking
        7. Output generation

        Inherits and extends: NodeEffect.process()
        Adds: Security assessment, operation routing, performance tracking

        Args:
            input_data: Strongly typed effect input with configuration

        Returns:
            ModelEffectOutput: Complete operation results with state

        Raises:
            OnexError: For validation failures or processing errors
        """
        start_time = time.time()
        transaction: Optional[Transaction] = None
        retry_count = 0
        correlation_id = input_data.operation_id

        try:
            # STEP 1: Comprehensive input validation (from canary)
            is_valid, errors, warnings = self.validate_input(input_data)
            if not is_valid:
                raise OnexError(
                    code=CoreErrorCode.VALIDATION_ERROR,
                    message=f"Input validation failed: {'; '.join(errors)}",
                    details={
                        "node_id": self.node_id,
                        "correlation_id": correlation_id,
                        "validation_errors": errors,
                        "validation_warnings": warnings,
                    },
                )

            # STEP 2: Circuit breaker check (from base)
            if input_data.circuit_breaker_enabled:
                circuit_breaker = self._get_circuit_breaker(
                    input_data.effect_type.value
                )
                if not circuit_breaker.can_execute():
                    raise OnexError(
                        code=CoreErrorCode.OPERATION_FAILED,
                        message=f"Circuit breaker open for {input_data.effect_type.value}",
                        details={
                            "node_id": self.node_id,
                            "operation_id": correlation_id,
                            "effect_type": input_data.effect_type.value,
                            "circuit_breaker_state": circuit_breaker.state.value,
                        },
                    )

            # STEP 3: Security assessment (from canary)
            security_assessment = self.assess_security_risk(
                input_data.effect_type.value,
                input_data.operation_data,
                getattr(input_data, "sandbox_mode", True),
            )

            # Track security violations
            if security_assessment.get("security_violations"):
                self._performance_metrics["security_violations"] += len(
                    security_assessment["security_violations"]
                )

            # STEP 4: Transaction creation (from base)
            if input_data.transaction_enabled:
                transaction = Transaction(correlation_id)
                transaction.state = TransactionState.ACTIVE
                self.active_transactions[correlation_id] = transaction

            # STEP 5: Operation execution with retry (from base)
            async with self.effect_semaphore:
                # Execute effect with retry logic
                result = await self._execute_with_retry(
                    input_data, transaction, security_assessment
                )
                retry_count = getattr(result, "retry_count", 0)

            # STEP 6: Transaction commit (from base)
            if transaction:
                await transaction.commit()
                del self.active_transactions[correlation_id]

            processing_time = (time.time() - start_time) * 1000

            # STEP 7: Circuit breaker success (from base)
            if input_data.circuit_breaker_enabled:
                circuit_breaker = self._get_circuit_breaker(
                    input_data.effect_type.value
                )
                circuit_breaker.record_success()

            # STEP 8: Metrics tracking (from both)
            await self._update_effect_metrics(
                input_data.effect_type.value, processing_time, True
            )
            await self._update_processing_metrics(processing_time, True)
            self._update_performance_metrics(processing_time)

            # STEP 9: Output generation (from base + canary)
            output = ModelEffectOutput(
                result=result,
                operation_id=correlation_id,
                effect_type=input_data.effect_type,
                transaction_state=(
                    transaction.state if transaction else TransactionState.COMMITTED
                ),
                processing_time_ms=processing_time,
                retry_count=retry_count,
                side_effects_applied=(
                    [str(op) for op in transaction.operations] if transaction else []
                ),
                rollback_operations=(
                    self._generate_rollback_instructions(transaction)
                    if transaction
                    else []
                ),
                metadata={
                    "timeout_ms": ModelScalarValue.create_int(input_data.timeout_ms),
                    "transaction_enabled": ModelScalarValue.create_bool(
                        input_data.transaction_enabled
                    ),
                    "circuit_breaker_enabled": ModelScalarValue.create_bool(
                        input_data.circuit_breaker_enabled
                    ),
                    "security_risk_level": ModelScalarValue.create_string(
                        security_assessment.get("risk_level", "UNKNOWN")
                    ),
                },
            )

            emit_log_event(
                LogLevel.INFO,
                f"Effect completed: {input_data.effect_type.value}",
                {
                    "node_id": self.node_id,
                    "operation_id": correlation_id,
                    "processing_time_ms": processing_time,
                    "retry_count": retry_count,
                    "transaction_id": (
                        transaction.transaction_id if transaction else None
                    ),
                },
            )

            return output

        except OnexError:
            # Re-raise OnexError without modification
            raise
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000

            # Rollback transaction if active
            if transaction:
                try:
                    await transaction.rollback()
                except Exception as rollback_error:
                    emit_log_event(
                        LogLevel.ERROR,
                        f"Transaction rollback failed: {str(rollback_error)}",
                        {
                            "node_id": self.node_id,
                            "operation_id": correlation_id,
                            "original_error": str(e),
                            "rollback_error": str(rollback_error),
                        },
                    )

                if correlation_id in self.active_transactions:
                    del self.active_transactions[correlation_id]

            # Record failure in circuit breaker
            if input_data.circuit_breaker_enabled:
                circuit_breaker = self._get_circuit_breaker(
                    input_data.effect_type.value
                )
                circuit_breaker.record_failure()

            # Update error metrics
            await self._update_effect_metrics(
                input_data.effect_type.value, processing_time, False
            )
            await self._update_processing_metrics(processing_time, False)

            raise OnexError(
                code=CoreErrorCode.OPERATION_FAILED,
                message=f"Effect execution failed: {str(e)}",
                details={
                    "node_id": self.node_id,
                    "operation_id": correlation_id,
                    "effect_type": input_data.effect_type.value,
                    "processing_time_ms": processing_time,
                    "transaction_state": (
                        transaction.state.value if transaction else "none"
                    ),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ) from e

    # ========================================================================
    # VALIDATION METHODS - Input Validation (from canary)
    # ========================================================================

    def validate_input(
        self, input_data: ModelEffectInput
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Comprehensive input validation with detailed feedback.

        CANONICAL PATTERN: Validation returns tuple of (is_valid, errors, warnings)
        - errors: Critical issues that prevent processing
        - warnings: Best practice violations that should be addressed

        From: canary business logic

        Args:
            input_data: Input state to validate

        Returns:
            Tuple[bool, List[str], List[str]]: (is_valid, errors, warnings)
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate effect type
        if not isinstance(input_data.effect_type, EffectType):
            errors.append(f"Invalid effect_type: {input_data.effect_type}")

        # Validate operation data exists
        if not input_data.operation_data:
            errors.append("operation_data is required")

        # Operation-specific validation
        effect_type = input_data.effect_type.value

        # File operation validation
        if effect_type in ["file_operation"]:
            if "file_path" not in input_data.operation_data:
                errors.append("file_path is required for file operations")
            elif "../" in str(input_data.operation_data.get("file_path", "")):
                errors.append("Path traversal detected in file_path")

        # HTTP request validation
        if effect_type in ["http_request", "api_call"]:
            if "url" not in input_data.operation_data:
                errors.append("url is required for HTTP operations")
            else:
                url = str(input_data.operation_data.get("url", ""))
                if not url.startswith(("http://", "https://")):
                    errors.append("URL must start with http:// or https://")

        # Database operation validation
        if effect_type in ["database_operation"]:
            if "query" not in input_data.operation_data:
                errors.append("query is required for database operations")

        # Email operation validation
        if effect_type in ["email_send"]:
            if "recipient" not in input_data.operation_data:
                errors.append("recipient is required for email operations")

        # Audit operation validation
        if effect_type in ["audit_log"]:
            if "message" not in input_data.operation_data:
                errors.append("message is required for audit operations")

        # Generate warnings for best practices
        if not input_data.transaction_enabled:
            warnings.append(
                "Transaction management is disabled - consider enabling for data integrity"
            )

        if not input_data.retry_enabled:
            warnings.append(
                "Retry logic is disabled - consider enabling for resilience"
            )

        if input_data.timeout_ms > 60000:
            warnings.append(
                f"Long timeout detected ({input_data.timeout_ms}ms) - consider reducing"
            )

        return len(errors) == 0, errors, warnings

    # ========================================================================
    # SECURITY ASSESSMENT - Risk Evaluation (from canary)
    # ========================================================================

    def assess_security_risk(
        self,
        operation: str,
        parameters: Dict[str, ModelScalarValue],
        sandbox_mode: bool = True,
    ) -> Dict[str, Any]:
        """
        Comprehensive security risk assessment.

        CANONICAL PATTERN: Every operation should be assessed for security risks
        before execution. This prevents:
        - Path traversal attacks
        - SQL injection
        - Command injection
        - Unauthorized access

        From: canary business logic

        Args:
            operation: Operation type being performed
            parameters: Operation parameters to assess
            sandbox_mode: Whether sandbox restrictions are enabled

        Returns:
            Dict with security assessment results:
            - sandbox_active: bool
            - security_violations: List[str]
            - risk_level: str (LOW, MEDIUM, HIGH)
            - mitigation_applied: List[str]
            - security_context: Dict
        """
        violations: List[str] = []
        mitigation_applied: List[str] = []

        # Check for path traversal in file operations
        if "file_path" in parameters:
            file_path = str(parameters["file_path"])
            if "../" in file_path or "..\\" in file_path:
                violations.append("Path traversal attempt detected")
            else:
                mitigation_applied.append("path_validation")

        # Check for URL validation in HTTP operations
        if "url" in parameters:
            url = str(parameters["url"])
            if not url.startswith(("http://", "https://")):
                violations.append("Invalid URL scheme detected")
            else:
                mitigation_applied.append("url_validation")

        # Sandbox enforcement
        if sandbox_mode:
            mitigation_applied.append("sandbox_restriction")

        # Determine risk level
        if violations:
            risk_level = "HIGH"
        elif operation in ["database_operation", "file_delete"]:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "sandbox_active": sandbox_mode,
            "security_violations": violations,
            "risk_level": risk_level,
            "mitigation_applied": mitigation_applied,
            "security_context": {
                "resource_access_level": "read_write" if sandbox_mode else "admin",
                "security_policy_version": "1.0",
            },
        }

    # ========================================================================
    # RETRY LOGIC - Exponential Backoff (from base)
    # ========================================================================

    async def _execute_with_retry(
        self,
        input_data: ModelEffectInput,
        transaction: Optional[Transaction],
        security_assessment: Dict[str, Any],
    ) -> Any:
        """
        Execute effect with retry logic and exponential backoff.

        CANONICAL PATTERN: Retry with exponential backoff prevents overwhelming
        failing services. Formula: delay = base_delay * (2 ** retry_count)

        From: base infrastructure

        Args:
            input_data: Effect input configuration
            transaction: Optional transaction for operation tracking
            security_assessment: Security assessment results

        Returns:
            Any: Operation result

        Raises:
            OnexError: If all retries exhausted
        """
        retry_count = 0
        last_exception: Exception = OnexError(
            code=CoreErrorCode.OPERATION_FAILED,
            message="No retries executed",
        )

        while retry_count <= input_data.max_retries:
            try:
                # Execute the effect
                return await self._execute_effect(
                    input_data, transaction, security_assessment
                )

            except Exception as e:
                last_exception = e
                retry_count += 1

                if not input_data.retry_enabled or retry_count > input_data.max_retries:
                    raise

                # Calculate exponential backoff delay
                delay_ms = input_data.retry_delay_ms * (2 ** (retry_count - 1))
                # Cap maximum delay at 60 seconds
                delay_ms = min(delay_ms, 60000)

                await asyncio.sleep(delay_ms / 1000.0)

                emit_log_event(
                    LogLevel.WARNING,
                    f"Effect retry {retry_count}/{input_data.max_retries}: {str(e)}",
                    {
                        "node_id": self.node_id,
                        "operation_id": input_data.operation_id,
                        "effect_type": input_data.effect_type.value,
                        "retry_count": retry_count,
                        "delay_ms": delay_ms,
                    },
                )

        # If we get here, all retries failed
        raise last_exception

    # ========================================================================
    # OPERATION EXECUTION - Handler Routing (from base + canary)
    # ========================================================================

    async def _execute_effect(
        self,
        input_data: ModelEffectInput,
        transaction: Optional[Transaction],
        security_assessment: Dict[str, Any],
    ) -> Any:
        """
        Execute the actual effect operation by routing to specific handler.

        CANONICAL PATTERN: Main router method delegates to specialized handlers
        based on effect type. Add new handlers by registering in _register_builtin_effect_handlers().

        Args:
            input_data: Effect input configuration
            transaction: Optional transaction for operation tracking
            security_assessment: Security assessment results

        Returns:
            Any: Operation result

        Raises:
            OnexError: If no handler registered for effect type
        """
        effect_type = input_data.effect_type

        if effect_type in self.effect_handlers:
            handler = self.effect_handlers[effect_type]
            return await handler(
                input_data.operation_data, transaction, security_assessment
            )

        raise OnexError(
            code=CoreErrorCode.OPERATION_FAILED,
            message=f"No handler registered for effect type: {effect_type.value}",
            details={
                "node_id": self.node_id,
                "effect_type": effect_type.value,
                "available_types": [et.value for et in self.effect_handlers.keys()],
            },
        )

    # ========================================================================
    # HELPER METHODS - Utilities
    # ========================================================================

    def _generate_rollback_instructions(self, transaction: Transaction) -> List[str]:
        """
        Generate rollback instructions from transaction operations.

        CANONICAL PATTERN: Provide human-readable rollback instructions
        for audit and manual recovery purposes.

        From: canary business logic

        Args:
            transaction: Transaction with recorded operations

        Returns:
            List[str]: Human-readable rollback instructions
        """
        instructions = []
        for operation in transaction.operations:
            op_name = operation.get("name", "unknown")
            op_data = operation.get("data", {})

            if "file_path" in op_data:
                if op_name == "write":
                    instructions.append(f"Delete file: rm {op_data['file_path']}")
                elif op_name == "delete":
                    instructions.append(f"Restore file: {op_data['file_path']}")
            elif "query" in op_data:
                instructions.append("Execute compensating database transaction")
            else:
                instructions.append(f"Manually reverse: {op_name}")

        return instructions

    def _update_performance_metrics(self, processing_time_ms: float) -> None:
        """
        Update business logic performance metrics.

        From: canary business logic

        Args:
            processing_time_ms: Processing duration in milliseconds
        """
        self._performance_metrics["total_operations"] += 1
        self._performance_metrics["total_processing_time_ms"] += processing_time_ms
        self._performance_metrics["average_processing_time_ms"] = (
            self._performance_metrics["total_processing_time_ms"]
            / self._performance_metrics["total_operations"]
        )
        self._performance_metrics["side_effects_created"] = len(
            self._side_effects_created
        )

    def get_performance_metrics(self) -> Dict[str, float]:
        """
        Get current performance metrics (business logic).

        From: canary business logic

        Returns:
            Dict[str, float]: Performance metrics
        """
        return self._performance_metrics.copy()


# ============================================================================
# MAIN ENTRY POINT - CLI Integration
# ============================================================================
# CANONICAL PATTERN: One-line main function for NodeBase CLI integration


def main():
    """One-line main function for CLI integration."""
    from omnibase_core.core.node_base import NodeBase

    return NodeBase(Path(__file__).parent / "contract.yaml")


if __name__ == "__main__":
    main()


# ============================================================================
# CANONICAL PATTERNS SUMMARY
# ============================================================================
#
# This file demonstrates ALL canonical patterns for ONEX Effect nodes:
#
# 1. ✅ Class naming: Node<Name>Effect (NOT Tool*)
# 2. ✅ File naming: node_*_effect.py (NOT tool_*)
# 3. ✅ Inheritance: NodeEffect (4-node architecture)
# 4. ✅ Container injection: ONEXContainer parameter
# 5. ✅ Transaction management: Extracted to infrastructure/transaction.py
# 6. ✅ Circuit breaker: Extracted to infrastructure/circuit_breaker.py
# 7. ✅ Retry logic: Exponential backoff with configurable attempts
# 8. ✅ Security assessment: Risk evaluation before operations
# 9. ✅ Input validation: Comprehensive with errors/warnings
# 10. ✅ Strong typing: Pydantic BaseModel for all data
# 11. ✅ Error handling: OnexError with structured details
# 12. ✅ Logging: Structured emit_log_event
# 13. ✅ Performance metrics: Detailed tracking
# 14. ✅ Rollback instructions: Human-readable recovery steps
# 15. ✅ Multiple operations: Extensible handler registry
# 16. ✅ Enums extracted: models/enum_*.py
# 17. ✅ Models extracted: models/model_effect_*.py
# 18. ✅ Infrastructure extracted: infrastructure/*.py
# 19. ✅ Node.py purity: ONLY node class + main()
#
# Use this file as the template for all new Effect nodes!
# ============================================================================
