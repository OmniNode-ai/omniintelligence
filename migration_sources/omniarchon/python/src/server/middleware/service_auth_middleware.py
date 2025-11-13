"""
Service Authentication Middleware for API Server

This middleware handles internal service-to-service authentication via X-Service-Auth headers,
enabling MCP tools to make authenticated calls to the API server without requiring user session context.

Key Features:
- Validates X-Service-Auth headers for internal service calls
- Takes precedence over user session validation
- Marks requests as service-authenticated for downstream processing
- Provides secure token-based authentication for microservices
"""

import logging
import os
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Load the shared secret from environment variables for security
# This token must be set on both the API Server and MCP Server environments
SERVICE_AUTH_TOKEN = os.getenv("SERVICE_AUTH_TOKEN")


class ServiceAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle service-to-service authentication.

    This middleware checks for X-Service-Auth headers and validates them against
    the configured SERVICE_AUTH_TOKEN. If valid, it marks the request as
    service-authenticated and bypasses user session validation.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process incoming requests for service authentication.

        Flow:
        1. Check if SERVICE_AUTH_TOKEN is configured
        2. Look for X-Service-Auth header in request
        3. If present and valid, mark as service-authenticated
        4. If present but invalid, deny request immediately
        5. If not present, proceed to user session validation
        """

        if not SERVICE_AUTH_TOKEN:
            # If the server is not configured for service auth, skip this middleware
            # This allows the system to work without service auth for development
            logger.debug("SERVICE_AUTH_TOKEN not configured, skipping service auth")
            return await call_next(request)

        # Check for the service authentication header
        service_auth_header = request.headers.get("X-Service-Auth")

        if service_auth_header:
            logger.debug(f"Service auth header present for {request.url.path}")

            if service_auth_header == SERVICE_AUTH_TOKEN:
                # Valid service token - mark request as authenticated internally
                logger.info(
                    f"✅ Service authentication successful for {request.url.path}"
                )
                request.scope["auth_type"] = "service"
                return await call_next(request)
            else:
                # Invalid service token provided - deny immediately
                logger.warning(
                    f"❌ Invalid service authentication token for {request.url.path}"
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Invalid service authentication token"},
                )

        # No service auth header present - proceed to user session validation
        logger.debug(
            f"No service auth header, proceeding to user session validation for {request.url.path}"
        )
        request.scope["auth_type"] = "user_session"
        return await call_next(request)


def is_service_authenticated(request: Request) -> bool:
    """
    Helper function to check if a request was authenticated via service auth.

    Args:
        request: The Starlette request object

    Returns:
        True if request was authenticated as a service call, False otherwise
    """
    return request.scope.get("auth_type") == "service"
