"""
Intelligence Service Clients Package.

Provides HTTP clients for communication with Archon Intelligence Service.

Exports:
    - IntelligenceServiceClient: Async HTTP client with circuit breaker
    - IntelligenceServiceError: Base exception for client errors
    - IntelligenceServiceUnavailable: Service unavailable exception
    - IntelligenceServiceTimeout: Request timeout exception
    - IntelligenceServiceValidation: Validation error exception
    - IntelligenceServiceRateLimit: Rate limit exceeded exception
    - CircuitBreakerState: Circuit breaker state management
"""

from omniintelligence._legacy.clients.client_intelligence_service import (
    CircuitBreakerState,
    IntelligenceServiceClient,
    IntelligenceServiceError,
    IntelligenceServiceRateLimit,
    IntelligenceServiceTimeout,
    IntelligenceServiceUnavailable,
    IntelligenceServiceValidation,
)

__all__ = [
    "CircuitBreakerState",
    "IntelligenceServiceClient",
    "IntelligenceServiceError",
    "IntelligenceServiceRateLimit",
    "IntelligenceServiceTimeout",
    "IntelligenceServiceUnavailable",
    "IntelligenceServiceValidation",
]
