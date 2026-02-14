# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for sensitive environment variable redaction in Contract Linter.

Tests for _is_sensitive_env_var, _get_sensitive_env_values, and redact_sensitive_values
functions that prevent accidental exposure of secrets in error messages.

Note: These tests require omnibase_core to be installed.
"""

import os
from unittest import mock

import pytest

# Skip entire module if omnibase_core is not available
pytest.importorskip(
    "omnibase_core", reason="omnibase_core required for contract linter tests"
)

from omniintelligence.tools.contract_linter import (
    REDACTED_VALUE,
    SENSITIVE_ENV_VAR_PATTERNS,
    _get_sensitive_env_values,
    _is_sensitive_env_var,
    redact_sensitive_values,
)

# =============================================================================
# Test Class: Sensitive Environment Variable Detection
# =============================================================================


@pytest.mark.unit
class TestIsSensitiveEnvVar:
    """Tests for _is_sensitive_env_var function."""

    def test_api_key_patterns(self):
        """Test that API key patterns are detected as sensitive."""
        assert _is_sensitive_env_var("API_KEY") is True
        assert _is_sensitive_env_var("MY_API_KEY") is True
        assert _is_sensitive_env_var("SERVICE_APIKEY") is True
        assert _is_sensitive_env_var("OPENAI_API_KEY") is True

    def test_secret_patterns(self):
        """Test that secret patterns are detected as sensitive.

        Note: Pattern is *_SECRET, so it requires a prefix.
        """
        assert _is_sensitive_env_var("APP_SECRET") is True
        assert _is_sensitive_env_var("AWS_SECRET_ACCESS_KEY") is True
        assert _is_sensitive_env_var("CLIENT_SECRET") is True
        # Without prefix, doesn't match *_SECRET pattern
        assert _is_sensitive_env_var("SECRET") is False

    def test_password_patterns(self):
        """Test that password patterns are detected as sensitive.

        Note: Pattern is *_PASSWORD, so it requires a prefix.
        """
        assert _is_sensitive_env_var("DB_PASSWORD") is True
        assert _is_sensitive_env_var("ADMIN_PASSWORD") is True
        # Without prefix, doesn't match *_PASSWORD pattern
        assert _is_sensitive_env_var("PASSWORD") is False

    def test_token_patterns(self):
        """Test that token patterns are detected as sensitive.

        Note: Pattern is *_TOKEN, so it requires a prefix.
        """
        assert _is_sensitive_env_var("AUTH_TOKEN") is True
        assert _is_sensitive_env_var("ACCESS_TOKEN") is True
        assert _is_sensitive_env_var("REFRESH_TOKEN") is True
        # Without prefix, doesn't match *_TOKEN pattern
        assert _is_sensitive_env_var("TOKEN") is False

    def test_credential_patterns(self):
        """Test that credential patterns are detected as sensitive.

        Note: Pattern is *_CREDENTIAL*, so it requires a prefix and can have suffix.
        """
        assert _is_sensitive_env_var("DB_CREDENTIALS") is True
        assert _is_sensitive_env_var("AWS_CREDENTIAL") is True
        assert _is_sensitive_env_var("USER_CREDENTIALS_PATH") is True
        # Without prefix, doesn't match *_CREDENTIAL* pattern
        assert _is_sensitive_env_var("CREDENTIAL") is False

    def test_database_url_pattern(self):
        """Test that DATABASE_URL is detected as sensitive."""
        assert _is_sensitive_env_var("DATABASE_URL") is True

    def test_connection_string_patterns(self):
        """Test that connection string patterns are detected as sensitive."""
        assert _is_sensitive_env_var("DB_CONNECTION_STRING") is True
        assert _is_sensitive_env_var("REDIS_CONNECTION_STRING") is True

    def test_cloud_provider_patterns(self):
        """Test that cloud provider env vars are detected as sensitive."""
        # AWS
        assert _is_sensitive_env_var("AWS_ACCESS_KEY_ID") is True
        assert _is_sensitive_env_var("AWS_SECRET_ACCESS_KEY") is True
        assert _is_sensitive_env_var("AWS_SESSION_TOKEN") is True
        # Azure
        assert _is_sensitive_env_var("AZURE_CLIENT_SECRET") is True
        assert _is_sensitive_env_var("AZURE_TENANT_ID") is True
        # GCP
        assert _is_sensitive_env_var("GCP_SERVICE_ACCOUNT_KEY") is True
        assert _is_sensitive_env_var("GOOGLE_APPLICATION_CREDENTIALS") is True

    def test_certificate_patterns(self):
        """Test that certificate patterns are detected as sensitive."""
        assert _is_sensitive_env_var("SSL_CERT") is True
        assert _is_sensitive_env_var("TLS_CERTIFICATE") is True
        assert _is_sensitive_env_var("CLIENT_PEM") is True
        assert _is_sensitive_env_var("SERVER_RSA") is True
        assert _is_sensitive_env_var("SSH_PRIVATE_KEY") is True

    def test_auth_patterns(self):
        """Test that auth patterns are detected as sensitive."""
        assert _is_sensitive_env_var("OAUTH_AUTH_TOKEN") is True
        assert _is_sensitive_env_var("JWT_AUTH_SECRET") is True

    def test_non_sensitive_env_vars(self):
        """Test that non-sensitive env vars are not flagged."""
        assert _is_sensitive_env_var("PATH") is False
        assert _is_sensitive_env_var("HOME") is False
        assert _is_sensitive_env_var("USER") is False
        assert _is_sensitive_env_var("SHELL") is False
        assert _is_sensitive_env_var("LANG") is False
        assert _is_sensitive_env_var("TERM") is False
        assert _is_sensitive_env_var("DEBUG") is False
        assert _is_sensitive_env_var("LOG_LEVEL") is False
        assert _is_sensitive_env_var("PORT") is False
        assert _is_sensitive_env_var("HOST") is False

    def test_case_insensitivity(self):
        """Test that pattern matching is case-insensitive."""
        # lowercase
        assert _is_sensitive_env_var("api_key") is True
        assert _is_sensitive_env_var("database_url") is True
        # mixed case
        assert _is_sensitive_env_var("Api_Key") is True
        assert _is_sensitive_env_var("Database_Url") is True


# =============================================================================
# Test Class: Get Sensitive Environment Values
# =============================================================================


@pytest.mark.unit
class TestGetSensitiveEnvValues:
    """Tests for _get_sensitive_env_values function."""

    def test_returns_frozenset(self):
        """Test that function returns a frozenset."""
        result = _get_sensitive_env_values()
        assert isinstance(result, frozenset)

    def test_collects_sensitive_values(self):
        """Test that sensitive env var values are collected."""
        with mock.patch.dict(
            os.environ,
            {
                "MY_API_KEY": "secret_api_key_123",
                "DB_PASSWORD": "super_secure_password",
                "NORMAL_VAR": "normal_value",
            },
            clear=True,
        ):
            values = _get_sensitive_env_values()
            assert "secret_api_key_123" in values
            assert "super_secure_password" in values
            assert "normal_value" not in values

    def test_excludes_empty_values(self):
        """Test that empty env var values are excluded."""
        with mock.patch.dict(
            os.environ,
            {
                "MY_API_KEY": "",
                "DB_PASSWORD": "valid_password",
            },
            clear=True,
        ):
            values = _get_sensitive_env_values()
            assert "" not in values
            assert "valid_password" in values


# =============================================================================
# Test Class: Redact Sensitive Values
# =============================================================================


@pytest.mark.unit
class TestRedactSensitiveValues:
    """Tests for redact_sensitive_values function."""

    def test_redacts_sensitive_value_in_message(self):
        """Test that sensitive values are redacted from messages."""
        with mock.patch.dict(
            os.environ,
            {"MY_API_KEY": "secret_api_key_123"},
            clear=True,
        ):
            message = "Failed to authenticate with key: secret_api_key_123"
            result = redact_sensitive_values(message)
            assert "secret_api_key_123" not in result
            assert REDACTED_VALUE in result
            assert result == f"Failed to authenticate with key: {REDACTED_VALUE}"

    def test_redacts_multiple_sensitive_values(self):
        """Test that multiple sensitive values are all redacted."""
        with mock.patch.dict(
            os.environ,
            {
                "MY_API_KEY": "api_key_value",
                "DB_PASSWORD": "db_password_value",
            },
            clear=True,
        ):
            message = "API key: api_key_value, DB password: db_password_value"
            result = redact_sensitive_values(message)
            assert "api_key_value" not in result
            assert "db_password_value" not in result
            assert result.count(REDACTED_VALUE) == 2

    def test_preserves_non_sensitive_values(self):
        """Test that non-sensitive values are preserved."""
        with mock.patch.dict(
            os.environ,
            {
                "NORMAL_VAR": "normal_value",
                "LOG_LEVEL": "DEBUG",
            },
            clear=True,
        ):
            message = "Log level: DEBUG, Normal: normal_value"
            result = redact_sensitive_values(message)
            assert result == message  # No changes

    def test_handles_empty_message(self):
        """Test that empty messages are handled gracefully."""
        assert redact_sensitive_values("") == ""
        assert redact_sensitive_values(None) is None  # type: ignore[arg-type]

    def test_handles_message_without_sensitive_values(self):
        """Test that messages without sensitive values are unchanged."""
        with mock.patch.dict(os.environ, {}, clear=True):
            message = "This is a normal error message"
            result = redact_sensitive_values(message)
            assert result == message

    def test_skips_short_values(self):
        """Test that values shorter than 3 characters are not redacted.

        This prevents false positives from single character or very short
        env var values that could match common words.
        """
        with mock.patch.dict(
            os.environ,
            {"MY_API_KEY": "ab"},  # Only 2 characters
            clear=True,
        ):
            message = "The value ab appears in this message"
            result = redact_sensitive_values(message)
            # Should not be redacted because the value is too short
            assert result == message
            assert "ab" in result

    def test_redacts_value_appearing_multiple_times(self):
        """Test that a sensitive value appearing multiple times is redacted everywhere."""
        with mock.patch.dict(
            os.environ,
            {"MY_API_KEY": "secret123"},
            clear=True,
        ):
            message = "First: secret123, Second: secret123, Third: secret123"
            result = redact_sensitive_values(message)
            assert "secret123" not in result
            assert result.count(REDACTED_VALUE) == 3

    def test_case_sensitive_redaction(self):
        """Test that redaction is case-sensitive to avoid false positives."""
        with mock.patch.dict(
            os.environ,
            {"MY_API_KEY": "SecretValue"},
            clear=True,
        ):
            message = "Value: SecretValue, Other: secretvalue, Another: SECRETVALUE"
            result = redact_sensitive_values(message)
            # Only exact match should be redacted
            assert "SecretValue" not in result
            assert "secretvalue" in result
            assert "SECRETVALUE" in result


# =============================================================================
# Test Class: Integration with Error Messages
# =============================================================================


@pytest.mark.unit
class TestRedactionIntegration:
    """Tests for redaction integration with error message formatting."""

    def test_exception_message_redaction(self):
        """Test that exception messages with sensitive values are redacted."""
        with mock.patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:password123@host/db"},
            clear=True,
        ):
            try:
                # Simulate an error that includes the sensitive value
                raise ValueError(
                    "Connection failed: postgresql://user:password123@host/db"
                )
            except ValueError as e:
                result = redact_sensitive_values(str(e))
                assert "password123" not in result
                assert REDACTED_VALUE in result

    def test_formatted_error_redaction(self):
        """Test that f-string formatted errors are properly redacted."""
        with mock.patch.dict(
            os.environ,
            {"AWS_SECRET_ACCESS_KEY": "aws_secret_key_value"},
            clear=True,
        ):
            error_value = "aws_secret_key_value"
            message = f"AWS authentication failed with key: {error_value}"
            result = redact_sensitive_values(message)
            assert "aws_secret_key_value" not in result


# =============================================================================
# Test Class: Pattern Coverage
# =============================================================================


@pytest.mark.unit
class TestPatternCoverage:
    """Tests to verify all documented patterns are covered."""

    def test_all_documented_patterns_have_tests(self):
        """Verify that SENSITIVE_ENV_VAR_PATTERNS are all tested.

        This meta-test ensures that if new patterns are added, corresponding
        tests should also be added.
        """
        # All patterns should match at least one example in the tests above
        for pattern in SENSITIVE_ENV_VAR_PATTERNS:
            # Create a test env var name that should match the pattern
            if pattern.startswith("*"):
                test_name = "TEST" + pattern[1:]
            elif pattern.endswith("*"):
                test_name = pattern[:-1] + "_TEST"
            else:
                test_name = pattern

            # Clean up any wildcards in the middle
            test_name = test_name.replace("*", "_")

            assert _is_sensitive_env_var(test_name), (
                f"Pattern '{pattern}' should match test name '{test_name}'"
            )
