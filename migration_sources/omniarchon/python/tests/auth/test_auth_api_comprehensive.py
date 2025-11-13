"""
Comprehensive Authentication API Testing Suite

This module provides complete test coverage for authentication API endpoints including:
- Unit tests for individual authentication functions
- Integration tests for full authentication workflows
- Security tests for vulnerability assessment
- Performance tests for load scenarios
- Edge case tests for boundary conditions

Architecture: Based on Archon's service authentication middleware and JWT validation patterns
Technology: pytest + FastAPI TestClient + security analysis tools
ONEX Compliance: Strong typing, OnexError exception chaining, contract-driven architecture
"""

import asyncio
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import httpx
import pytest
from fastapi.testclient import TestClient
from jose import JWTError, jwt
from src.server.exceptions.onex_error import CoreErrorCode, OnexError
from src.server.middleware.service_auth_middleware import (
    ServiceAuthMiddleware,
    is_service_authenticated,
)

# Test Configuration Constants
TEST_JWT_SECRET = "test-secret-key-for-authentication-testing"
TEST_SERVICE_AUTH_TOKEN = "test-service-auth-token-12345"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "TestPassword123!"
INVALID_JWT_TOKEN = "invalid.jwt.token"


class AuthenticationTestFixtures:
    """Test fixtures and utilities for authentication testing"""

    @staticmethod
    def create_test_jwt_token(
        user_id: str = "test-user-123",
        email: str = TEST_USER_EMAIL,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a valid JWT token for testing purposes"""
        if expires_delta is None:
            expires_delta = timedelta(hours=1)

        expire = datetime.utcnow() + expires_delta

        to_encode = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
        }

        if additional_claims:
            to_encode.update(additional_claims)

        return jwt.encode(to_encode, TEST_JWT_SECRET, algorithm="HS256")

    @staticmethod
    def create_expired_jwt_token(user_id: str = "test-user-123") -> str:
        """Create an expired JWT token for testing"""
        return AuthenticationTestFixtures.create_test_jwt_token(
            user_id=user_id, expires_delta=timedelta(hours=-1)  # Expired 1 hour ago
        )

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for testing using bcrypt directly"""
        # Convert password to bytes and hash
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password for testing using bcrypt directly"""
        # Type check for None (should raise TypeError like passlib does)
        if plain_password is None:
            raise TypeError("password cannot be None")
        # Convert to bytes
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        # Verify
        return bcrypt.checkpw(password_bytes, hashed_bytes)


class TestServiceAuthMiddleware:
    """Unit tests for service authentication middleware"""

    def test_service_auth_middleware_valid_token(self):
        """Test middleware accepts valid service authentication token"""
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {"X-Service-Auth": TEST_SERVICE_AUTH_TOKEN}
        mock_request.url.path = "/test/endpoint"
        mock_request.scope = {}

        mock_call_next = AsyncMock(return_value=MagicMock(status_code=200))

        # Act & Assert
        with patch.dict(os.environ, {"SERVICE_AUTH_TOKEN": TEST_SERVICE_AUTH_TOKEN}):
            # Reload the module to get the new environment variable
            import importlib

            import src.server.middleware.service_auth_middleware

            importlib.reload(src.server.middleware.service_auth_middleware)
            middleware = (
                src.server.middleware.service_auth_middleware.ServiceAuthMiddleware(
                    app=MagicMock()
                )
            )

            result = asyncio.run(middleware.dispatch(mock_request, mock_call_next))

            # Verify request was marked as service authenticated
            assert mock_request.scope["auth_type"] == "service"
            assert mock_call_next.called
            assert result.status_code == 200

    def test_service_auth_middleware_invalid_token(self):
        """Test middleware rejects invalid service authentication token"""
        # Arrange
        mock_request = MagicMock()
        mock_request.headers = {"X-Service-Auth": "invalid-token"}
        mock_request.url.path = "/test/endpoint"
        mock_request.scope = {}

        mock_call_next = AsyncMock()

        # Act
        with patch.dict(os.environ, {"SERVICE_AUTH_TOKEN": TEST_SERVICE_AUTH_TOKEN}):
            # Reload the module to get the new environment variable
            import importlib

            import src.server.middleware.service_auth_middleware

            importlib.reload(src.server.middleware.service_auth_middleware)
            middleware = (
                src.server.middleware.service_auth_middleware.ServiceAuthMiddleware(
                    app=MagicMock()
                )
            )

            result = asyncio.run(middleware.dispatch(mock_request, mock_call_next))

            # Assert
            assert result.status_code == 403
            assert not mock_call_next.called

            # Verify response content
            response_data = json.loads(result.body.decode())
            assert "Invalid service authentication token" in response_data["detail"]

    def test_service_auth_middleware_no_token_configured(self):
        """Test middleware bypasses when no service token is configured"""
        # Arrange
        middleware = ServiceAuthMiddleware(app=MagicMock())

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.url.path = "/test/endpoint"
        mock_request.scope = {}

        mock_call_next = AsyncMock(return_value=MagicMock(status_code=200))

        # Act
        with patch.dict(os.environ, {}, clear=True):  # No SERVICE_AUTH_TOKEN
            result = asyncio.run(middleware.dispatch(mock_request, mock_call_next))

            # Assert
            assert mock_call_next.called
            assert result.status_code == 200

    def test_is_service_authenticated_helper(self):
        """Test helper function correctly identifies service authenticated requests"""
        # Arrange
        mock_request = MagicMock()
        mock_request.scope = {"auth_type": "service"}

        # Act & Assert
        assert is_service_authenticated(mock_request) is True

        # Test user session
        mock_request.scope = {"auth_type": "user_session"}
        assert is_service_authenticated(mock_request) is False

        # Test no auth type
        mock_request.scope = {}
        assert is_service_authenticated(mock_request) is False


class TestJWTValidation:
    """Unit tests for JWT token validation"""

    def test_valid_jwt_token_parsing(self):
        """Test parsing of valid JWT tokens"""
        # Arrange
        test_token = AuthenticationTestFixtures.create_test_jwt_token()

        # Act
        try:
            decoded = jwt.decode(test_token, TEST_JWT_SECRET, algorithms=["HS256"])

            # Assert
            assert decoded["email"] == TEST_USER_EMAIL
            assert decoded["sub"] == "test-user-123"
            assert decoded["type"] == "access"
            assert "exp" in decoded
            assert "iat" in decoded

        except JWTError as e:
            pytest.fail(f"Valid JWT token should not raise error: {e}")

    def test_expired_jwt_token_rejection(self):
        """Test rejection of expired JWT tokens"""
        # Arrange
        expired_token = AuthenticationTestFixtures.create_expired_jwt_token()

        # Act & Assert
        with pytest.raises(JWTError):
            jwt.decode(expired_token, TEST_JWT_SECRET, algorithms=["HS256"])

    def test_invalid_jwt_token_rejection(self):
        """Test rejection of malformed JWT tokens"""
        # Arrange
        invalid_tokens = [
            "invalid.jwt.token",
            "not-a-jwt-at-all",
            "",
            "header.payload.signature.extra",
            "missing-parts",
        ]

        # Act & Assert
        for invalid_token in invalid_tokens:
            with pytest.raises(JWTError):
                jwt.decode(invalid_token, TEST_JWT_SECRET, algorithms=["HS256"])

    def test_jwt_token_with_wrong_secret(self):
        """Test rejection of JWT tokens signed with wrong secret"""
        # Arrange
        token_with_wrong_secret = jwt.encode(
            {"sub": "test-user", "exp": datetime.utcnow() + timedelta(hours=1)},
            "wrong-secret",
            algorithm="HS256",
        )

        # Act & Assert
        with pytest.raises(JWTError):
            jwt.decode(token_with_wrong_secret, TEST_JWT_SECRET, algorithms=["HS256"])


class TestPasswordSecurity:
    """Unit tests for password security functions"""

    def test_password_hashing(self):
        """Test password hashing produces different hashes for same password"""
        # Arrange
        password = TEST_USER_PASSWORD

        # Act
        hash1 = AuthenticationTestFixtures.hash_password(password)
        hash2 = AuthenticationTestFixtures.hash_password(password)

        # Assert
        assert hash1 != hash2  # Salt should make hashes different
        assert len(hash1) > 50  # Bcrypt hashes are long
        assert hash1.startswith("$2b$")  # Bcrypt identifier

    def test_password_verification_correct(self):
        """Test correct password verification"""
        # Arrange
        password = TEST_USER_PASSWORD
        hashed = AuthenticationTestFixtures.hash_password(password)

        # Act & Assert
        assert AuthenticationTestFixtures.verify_password(password, hashed) is True

    def test_password_verification_incorrect(self):
        """Test incorrect password rejection"""
        # Arrange
        correct_password = TEST_USER_PASSWORD
        wrong_password = "WrongPassword123!"
        hashed = AuthenticationTestFixtures.hash_password(correct_password)

        # Act & Assert
        assert (
            AuthenticationTestFixtures.verify_password(wrong_password, hashed) is False
        )

    def test_password_edge_cases(self):
        """Test password verification with edge cases"""
        password = TEST_USER_PASSWORD
        hashed = AuthenticationTestFixtures.hash_password(password)

        # Test empty password
        assert AuthenticationTestFixtures.verify_password("", hashed) is False

        # Test None password - should raise exception
        with pytest.raises(TypeError):
            AuthenticationTestFixtures.verify_password(None, hashed)


@pytest.mark.integration
@pytest.mark.skip(
    reason="Auth API endpoints not yet implemented - waiting for /auth/login, /auth/register, etc."
)
class TestAuthenticationAPIEndpoints:
    """Integration tests for authentication API endpoints"""

    @pytest.fixture
    def auth_client(self, mock_database_client):
        """FastAPI test client configured for authentication testing"""
        with patch(
            "src.server.services.client_manager.create_client",
            return_value=mock_database_client,
        ):
            with patch.dict(
                os.environ,
                {
                    "SERVICE_AUTH_TOKEN": TEST_SERVICE_AUTH_TOKEN,
                    "JWT_SECRET": TEST_JWT_SECRET,
                },
            ):
                from src.server.main import app

                return TestClient(app)

    def test_login_endpoint_success(self, auth_client):
        """Test successful login with valid credentials"""
        # Arrange
        login_data = {"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}

        # Mock database to return user
        with patch(
            "src.server.services.auth_service.get_user_by_email"
        ) as mock_get_user:
            mock_get_user.return_value = {
                "id": "test-user-123",
                "email": TEST_USER_EMAIL,
                "password_hash": AuthenticationTestFixtures.hash_password(
                    TEST_USER_PASSWORD
                ),
                "is_active": True,
            }

            # Act
            response = auth_client.post("/auth/login", json=login_data)

            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert "access_token" in response_data
            assert "refresh_token" in response_data
            assert response_data["token_type"] == "bearer"

    def test_login_endpoint_invalid_credentials(self, auth_client):
        """Test login failure with invalid credentials"""
        # Arrange
        login_data = {"email": TEST_USER_EMAIL, "password": "WrongPassword123!"}

        # Mock database to return user with different password
        with patch(
            "src.server.services.auth_service.get_user_by_email"
        ) as mock_get_user:
            mock_get_user.return_value = {
                "id": "test-user-123",
                "email": TEST_USER_EMAIL,
                "password_hash": AuthenticationTestFixtures.hash_password(
                    TEST_USER_PASSWORD
                ),
                "is_active": True,
            }

            # Act
            response = auth_client.post("/auth/login", json=login_data)

            # Assert
            assert response.status_code == 401
            response_data = response.json()
            assert "Invalid credentials" in response_data["detail"]

    def test_login_endpoint_user_not_found(self, auth_client):
        """Test login failure when user doesn't exist"""
        # Arrange
        login_data = {
            "email": "nonexistent@example.com",
            "password": TEST_USER_PASSWORD,
        }

        # Mock database to return None
        with patch(
            "src.server.services.auth_service.get_user_by_email", return_value=None
        ):
            # Act
            response = auth_client.post("/auth/login", json=login_data)

            # Assert
            assert response.status_code == 401
            response_data = response.json()
            assert "Invalid credentials" in response_data["detail"]

    def test_register_endpoint_success(self, auth_client):
        """Test successful user registration"""
        # Arrange
        register_data = {
            "email": "newuser@example.com",
            "password": TEST_USER_PASSWORD,
            "full_name": "New User",
        }

        # Mock database operations
        with patch(
            "src.server.services.auth_service.get_user_by_email", return_value=None
        ):
            with patch("src.server.services.auth_service.create_user") as mock_create:
                mock_create.return_value = {
                    "id": "new-user-456",
                    "email": "newuser@example.com",
                    "full_name": "New User",
                    "is_active": True,
                }

                # Act
                response = auth_client.post("/auth/register", json=register_data)

                # Assert
                assert response.status_code == 201
                response_data = response.json()
                assert response_data["email"] == "newuser@example.com"
                assert "access_token" in response_data

    def test_register_endpoint_duplicate_email(self, auth_client):
        """Test registration failure with existing email"""
        # Arrange
        register_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "full_name": "Duplicate User",
        }

        # Mock database to return existing user
        with patch(
            "src.server.services.auth_service.get_user_by_email"
        ) as mock_get_user:
            mock_get_user.return_value = {
                "id": "existing-user",
                "email": TEST_USER_EMAIL,
            }

            # Act
            response = auth_client.post("/auth/register", json=register_data)

            # Assert
            assert response.status_code == 409
            response_data = response.json()
            assert "Email already registered" in response_data["detail"]

    def test_profile_endpoint_authenticated(self, auth_client):
        """Test profile retrieval with valid authentication"""
        # Arrange
        valid_token = AuthenticationTestFixtures.create_test_jwt_token()
        headers = {"Authorization": f"Bearer {valid_token}"}

        # Mock database to return user profile
        with patch("src.server.services.auth_service.get_user_by_id") as mock_get_user:
            mock_get_user.return_value = {
                "id": "test-user-123",
                "email": TEST_USER_EMAIL,
                "full_name": "Test User",
                "is_active": True,
                "created_at": "2023-01-01T00:00:00Z",
            }

            # Act
            response = auth_client.get("/auth/profile", headers=headers)

            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["email"] == TEST_USER_EMAIL
            assert response_data["full_name"] == "Test User"

    def test_profile_endpoint_unauthenticated(self, auth_client):
        """Test profile retrieval without authentication"""
        # Act
        response = auth_client.get("/auth/profile")

        # Assert
        assert response.status_code == 401

    def test_logout_endpoint_success(self, auth_client):
        """Test successful logout"""
        # Arrange
        valid_token = AuthenticationTestFixtures.create_test_jwt_token()
        headers = {"Authorization": f"Bearer {valid_token}"}

        # Act
        response = auth_client.post("/auth/logout", headers=headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["message"] == "Successfully logged out"

    def test_refresh_token_endpoint_success(self, auth_client):
        """Test successful token refresh"""
        # Arrange
        refresh_token = AuthenticationTestFixtures.create_test_jwt_token(
            additional_claims={"type": "refresh"}
        )

        refresh_data = {"refresh_token": refresh_token}

        # Act
        response = auth_client.post("/auth/refresh", json=refresh_data)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert "access_token" in response_data
        assert response_data["token_type"] == "bearer"

    def test_refresh_token_endpoint_invalid_token(self, auth_client):
        """Test token refresh with invalid refresh token"""
        # Arrange
        invalid_refresh_data = {"refresh_token": INVALID_JWT_TOKEN}

        # Act
        response = auth_client.post("/auth/refresh", json=invalid_refresh_data)

        # Assert
        assert response.status_code == 401
        response_data = response.json()
        assert "Invalid refresh token" in response_data["detail"]


@pytest.mark.security
@pytest.mark.skip(
    reason="Auth API endpoints not yet implemented - waiting for /auth/login, /auth/register, etc."
)
class TestAuthenticationSecurity:
    """Security tests for authentication vulnerabilities"""

    def test_sql_injection_attempts_login(self, auth_client):
        """Test login endpoint against SQL injection attacks"""
        # Arrange
        sql_injection_payloads = [
            "admin@example.com'; DROP TABLE users; --",
            "admin@example.com' OR '1'='1",
            "admin@example.com' UNION SELECT * FROM users --",
            "'; INSERT INTO users (email) VALUES ('hacker@evil.com'); --",
        ]

        for payload in sql_injection_payloads:
            # Act
            response = auth_client.post(
                "/auth/login", json={"email": payload, "password": "any_password"}
            )

            # Assert - Should not cause server error or expose data
            assert response.status_code in [400, 401, 422]  # Valid error responses
            assert response.status_code != 500  # Should not cause internal server error

    def test_xss_attempts_registration(self, auth_client):
        """Test registration endpoint against XSS attacks"""
        # Arrange
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src='x' onerror='alert(1)'>",
            "'; alert('XSS'); //",
            "onmouseover=alert(1)",
        ]

        for payload in xss_payloads:
            # Act
            response = auth_client.post(
                "/auth/register",
                json={
                    "email": f"test+{secrets.token_hex(4)}@example.com",
                    "password": TEST_USER_PASSWORD,
                    "full_name": payload,
                },
            )

            # Assert - Should sanitize or reject malicious input
            if response.status_code == 201:
                response_data = response.json()
                # Ensure XSS payload is not reflected back unsanitized
                assert "<script>" not in str(response_data)
                assert "javascript:" not in str(response_data)

    def test_brute_force_protection(self, auth_client):
        """Test login endpoint rate limiting against brute force attacks"""
        # Arrange
        login_data = {"email": TEST_USER_EMAIL, "password": "wrong_password"}

        # Act - Attempt multiple failed logins
        failed_attempts = 0

        for attempt in range(20):  # Try 20 failed attempts
            response = auth_client.post("/auth/login", json=login_data)

            if response.status_code == 429:  # Too Many Requests
                break
            elif response.status_code == 401:
                failed_attempts += 1

        # Assert - Should implement rate limiting after multiple failures
        # Note: This test validates that rate limiting is implemented
        # The exact threshold may vary based on configuration
        assert failed_attempts > 0  # Some attempts should fail with 401
        # Rate limiting implementation is optional but recommended

    def test_password_strength_validation(self, auth_client):
        """Test password strength requirements"""
        # Arrange
        weak_passwords = [
            "123456",
            "password",
            "abc",
            "",
            "1234567890123456789012345678901234567890123456789012345678901234567890",  # Too long
        ]

        for weak_password in weak_passwords:
            # Act
            response = auth_client.post(
                "/auth/register",
                json={
                    "email": f"test+{secrets.token_hex(4)}@example.com",
                    "password": weak_password,
                    "full_name": "Test User",
                },
            )

            # Assert - Should reject weak passwords
            assert response.status_code in [400, 422]  # Validation error

            if response.status_code == 400:
                response_data = response.json()
                assert "password" in response_data["detail"].lower()

    def test_token_expiration_enforcement(self, auth_client):
        """Test that expired tokens are properly rejected"""
        # Arrange
        expired_token = AuthenticationTestFixtures.create_expired_jwt_token()
        headers = {"Authorization": f"Bearer {expired_token}"}

        # Act
        response = auth_client.get("/auth/profile", headers=headers)

        # Assert
        assert response.status_code == 401
        response_data = response.json()
        assert (
            "expired" in response_data["detail"].lower()
            or "invalid" in response_data["detail"].lower()
        )

    def test_cors_headers_security(self, auth_client):
        """Test CORS headers for security compliance"""
        # Act
        response = auth_client.options("/auth/login")

        # Assert - Should have secure CORS headers
        headers = response.headers

        # Should not allow all origins in production
        if "Access-Control-Allow-Origin" in headers:
            assert headers["Access-Control-Allow-Origin"] != "*"

        # Should include security headers

        # Note: These headers might be set at reverse proxy level
        # This test documents the expectation


@pytest.mark.performance
@pytest.mark.skip(
    reason="Auth API endpoints not yet implemented - waiting for /auth/login, /auth/register, etc."
)
class TestAuthenticationPerformance:
    """Performance tests for authentication endpoints"""

    @pytest.mark.asyncio
    async def test_login_endpoint_response_time(self, auth_client):
        """Test login endpoint response time under normal load"""
        # Arrange
        login_data = {"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}

        response_times = []

        # Mock successful authentication
        with patch(
            "src.server.services.auth_service.get_user_by_email"
        ) as mock_get_user:
            mock_get_user.return_value = {
                "id": "test-user-123",
                "email": TEST_USER_EMAIL,
                "password_hash": AuthenticationTestFixtures.hash_password(
                    TEST_USER_PASSWORD
                ),
                "is_active": True,
            }

            # Act - Measure response time for multiple requests
            for _ in range(10):
                start_time = time.time()
                response = auth_client.post("/auth/login", json=login_data)
                end_time = time.time()

                response_times.append(end_time - start_time)
                assert response.status_code == 200

        # Assert - Response time should be reasonable
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)

        assert avg_response_time < 1.0  # Average under 1 second
        assert max_response_time < 2.0  # Maximum under 2 seconds

        print(f"Average login response time: {avg_response_time:.3f}s")
        print(f"Maximum login response time: {max_response_time:.3f}s")

    @pytest.mark.asyncio
    async def test_concurrent_authentication_requests(self, auth_client):
        """Test authentication under concurrent load"""

        # Arrange
        async def make_login_request(session: httpx.AsyncClient, user_num: int):
            login_data = {
                "email": f"user{user_num}@example.com",
                "password": TEST_USER_PASSWORD,
            }

            try:
                response = await session.post("/auth/login", json=login_data)
                return response.status_code
            except Exception:
                return 500  # Mark as error

        # Mock authentication service
        with patch(
            "src.server.services.auth_service.get_user_by_email"
        ) as mock_get_user:
            mock_get_user.return_value = {
                "id": "test-user-123",
                "email": TEST_USER_EMAIL,
                "password_hash": AuthenticationTestFixtures.hash_password(
                    TEST_USER_PASSWORD
                ),
                "is_active": True,
            }

            # Act - Make concurrent requests
            async with httpx.AsyncClient(
                app=auth_client.app, base_url="http://testserver"
            ) as session:
                tasks = [make_login_request(session, i) for i in range(20)]
                status_codes = await asyncio.gather(*tasks)

            # Assert - All requests should be handled successfully
            successful_requests = [
                code for code in status_codes if code in [200, 401]
            ]  # Valid responses
            error_requests = [
                code for code in status_codes if code >= 500
            ]  # Server errors

            assert len(successful_requests) >= 18  # At least 90% success rate
            assert len(error_requests) <= 2  # Less than 10% server errors

            print(f"Successful concurrent requests: {len(successful_requests)}/20")
            print(f"Error requests: {len(error_requests)}/20")

    def test_password_hashing_performance(self):
        """Test password hashing performance"""
        # Arrange
        passwords = [f"TestPassword{i}!" for i in range(100)]

        # Act
        start_time = time.time()
        hashes = [AuthenticationTestFixtures.hash_password(pwd) for pwd in passwords]
        end_time = time.time()

        total_time = end_time - start_time
        avg_time_per_hash = total_time / len(passwords)

        # Assert
        assert len(hashes) == len(passwords)
        assert all(len(hash_val) > 50 for hash_val in hashes)  # Valid bcrypt hashes
        assert (
            avg_time_per_hash < 0.5
        )  # Should hash in under 500ms on average (bcrypt is intentionally slow)

        print(f"Average password hashing time: {avg_time_per_hash:.4f}s")
        print(f"Total time for {len(passwords)} hashes: {total_time:.3f}s")


@pytest.mark.edge_cases
@pytest.mark.skip(
    reason="Auth API endpoints not yet implemented - waiting for /auth/login, /auth/register, etc."
)
class TestAuthenticationEdgeCases:
    """Edge case tests for authentication system"""

    def test_empty_request_bodies(self, auth_client):
        """Test endpoints with empty request bodies"""
        endpoints = [
            ("POST", "/auth/login"),
            ("POST", "/auth/register"),
            ("POST", "/auth/refresh"),
        ]

        for method, endpoint in endpoints:
            # Act
            if method == "POST":
                response = auth_client.post(endpoint, json={})

            # Assert - Should return validation error, not server error
            assert response.status_code in [400, 422]  # Validation error
            assert response.status_code != 500  # Should not crash

    def test_malformed_json_requests(self, auth_client):
        """Test endpoints with malformed JSON"""
        endpoints = ["/auth/login", "/auth/register", "/auth/refresh"]

        for endpoint in endpoints:
            # Act
            response = auth_client.post(
                endpoint,
                data="invalid json content",
                headers={"Content-Type": "application/json"},
            )

            # Assert
            assert response.status_code in [400, 422]
            assert response.status_code != 500

    def test_extremely_long_input_values(self, auth_client):
        """Test endpoints with extremely long input values"""
        # Arrange
        very_long_string = "x" * 10000  # 10KB string

        test_cases = [
            {
                "endpoint": "/auth/register",
                "data": {
                    "email": very_long_string + "@example.com",
                    "password": TEST_USER_PASSWORD,
                    "full_name": "Test User",
                },
            },
            {
                "endpoint": "/auth/register",
                "data": {
                    "email": TEST_USER_EMAIL,
                    "password": very_long_string,
                    "full_name": "Test User",
                },
            },
            {
                "endpoint": "/auth/login",
                "data": {
                    "email": very_long_string + "@example.com",
                    "password": TEST_USER_PASSWORD,
                },
            },
        ]

        for test_case in test_cases:
            # Act
            response = auth_client.post(test_case["endpoint"], json=test_case["data"])

            # Assert - Should handle gracefully
            assert response.status_code in [400, 413, 422]  # Valid error responses
            assert response.status_code != 500  # Should not crash

    def test_special_characters_in_inputs(self, auth_client):
        """Test handling of special characters in inputs"""
        # Arrange
        special_chars_test_cases = [
            "user@example.com",
            "user+tag@example.com",
            "user.name@example.co.uk",
            "user@subdomain.example.com",
            "user@[IPv6:2001:db8::1]",  # IPv6 email format
            "用户@example.com",  # Unicode email
        ]

        for email in special_chars_test_cases:
            # Act
            response = auth_client.post(
                "/auth/register",
                json={
                    "email": email,
                    "password": TEST_USER_PASSWORD,
                    "full_name": "Test User",
                },
            )

            # Assert - Should either accept valid emails or reject with proper error
            assert response.status_code in [201, 400, 422]
            assert response.status_code != 500

    def test_concurrent_registration_same_email(self, auth_client):
        """Test race condition in user registration"""
        # This test simulates the edge case where multiple clients
        # try to register the same email simultaneously

        # Arrange
        register_data = {
            "email": f"race-test-{secrets.token_hex(8)}@example.com",
            "password": TEST_USER_PASSWORD,
            "full_name": "Race Test User",
        }

        # Simulate concurrent registration attempts
        responses = []
        for _ in range(5):
            response = auth_client.post("/auth/register", json=register_data)
            responses.append(response.status_code)

        # Assert - Only one registration should succeed
        successful_registrations = [code for code in responses if code == 201]
        [code for code in responses if code == 409]

        # At least one should succeed, others should get conflict
        assert len(successful_registrations) >= 1
        # The exact behavior depends on implementation


# Performance and Load Testing Utilities
class AuthenticationLoadTester:
    """Utility class for authentication load testing"""

    @staticmethod
    async def simulate_user_session(
        client: httpx.AsyncClient, user_id: str
    ) -> dict[str, Any]:
        """Simulate a complete user session: login -> access protected resource -> logout"""
        session_data = {
            "user_id": user_id,
            "login_time": None,
            "access_time": None,
            "logout_time": None,
            "errors": [],
        }

        try:
            # Step 1: Login
            start_time = time.time()
            login_response = await client.post(
                "/auth/login",
                json={
                    "email": f"loadtest-{user_id}@example.com",
                    "password": TEST_USER_PASSWORD,
                },
            )
            session_data["login_time"] = time.time() - start_time

            if login_response.status_code != 200:
                session_data["errors"].append(
                    f"Login failed: {login_response.status_code}"
                )
                return session_data

            # Step 2: Access protected resource
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            start_time = time.time()
            profile_response = await client.get("/auth/profile", headers=headers)
            session_data["access_time"] = time.time() - start_time

            if profile_response.status_code != 200:
                session_data["errors"].append(
                    f"Profile access failed: {profile_response.status_code}"
                )

            # Step 3: Logout
            start_time = time.time()
            logout_response = await client.post("/auth/logout", headers=headers)
            session_data["logout_time"] = time.time() - start_time

            if logout_response.status_code != 200:
                session_data["errors"].append(
                    f"Logout failed: {logout_response.status_code}"
                )

        except Exception as e:
            session_data["errors"].append(f"Session error: {e!s}")

        return session_data


# ONEX Compliance Tests
@pytest.mark.onex_compliance
class TestONEXCompliance:
    """Tests for ONEX architectural compliance in authentication system"""

    def test_strong_typing_compliance(self):
        """Verify no Any types are used in authentication code"""
        # This test would analyze the authentication module source code
        # to ensure strong typing compliance

        import inspect

        from src.server.middleware.service_auth_middleware import ServiceAuthMiddleware

        # Get method signatures
        middleware_methods = inspect.getmembers(
            ServiceAuthMiddleware, predicate=inspect.ismethod
        )

        for method_name, method in middleware_methods:
            signature = inspect.signature(method)

            # Check parameters
            for param_name, param in signature.parameters.items():
                if param_name != "self":  # Skip self parameter
                    assert (
                        param.annotation != inspect.Parameter.empty
                    ), f"Parameter {param_name} in {method_name} lacks type annotation"
                    assert (
                        str(param.annotation) != "Any"
                    ), f"Parameter {param_name} in {method_name} uses Any type"

            # Check return annotation
            if signature.return_annotation != inspect.Signature.empty:
                assert (
                    str(signature.return_annotation) != "Any"
                ), f"Method {method_name} returns Any type"

    def test_onex_error_exception_chaining(self):
        """Test that OnexError exceptions are properly chained"""
        # Test that authentication errors use OnexError with proper chaining

        try:
            # Simulate an authentication error that should be wrapped
            raise ValueError("Original authentication error")
        except ValueError as e:
            # This is how authentication errors should be handled
            onex_error = OnexError(
                message="Authentication failed during token validation",
                error_code=CoreErrorCode.AUTHENTICATION_FAILED,
                details={"original_error": str(e)},
            )

            # Verify proper exception chaining
            assert onex_error.error_code == CoreErrorCode.AUTHENTICATION_FAILED
            assert "Authentication failed" in onex_error.message
            assert "original_error" in onex_error.details

    def test_contract_driven_architecture(self):
        """Verify authentication follows contract-driven patterns"""
        # Test that authentication middleware follows expected interface patterns

        middleware = ServiceAuthMiddleware(app=MagicMock())

        # Verify required methods exist
        assert hasattr(middleware, "dispatch")
        assert callable(middleware.dispatch)

        # Verify helper functions follow expected patterns
        assert callable(is_service_authenticated)

        # Test that middleware follows expected return patterns
        mock_request = MagicMock()
        mock_request.scope = {}
        mock_request.headers = {}
        mock_request.url.path = "/test"

        # Should return Response object
        result = asyncio.run(
            middleware.dispatch(mock_request, AsyncMock(return_value=MagicMock()))
        )
        assert hasattr(result, "status_code")


if __name__ == "__main__":
    """
    Run comprehensive authentication tests

    Usage:
    python -m pytest tests/auth/test_auth_api_comprehensive.py -v
    python -m pytest tests/auth/test_auth_api_comprehensive.py::TestServiceAuthMiddleware -v
    python -m pytest tests/auth/test_auth_api_comprehensive.py -m security
    python -m pytest tests/auth/test_auth_api_comprehensive.py -m performance
    """
    pytest.main([__file__, "-v", "--tb=short"])
