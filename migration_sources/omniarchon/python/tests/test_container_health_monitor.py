"""
Tests for Container Health Monitor

Focuses on security validation and container name sanitization.
"""

from unittest.mock import MagicMock, patch

import pytest
from src.server.services.container_health_monitor import (
    MAX_CONTAINER_NAME_LENGTH,
    ContainerHealthMonitor,
    InvalidContainerNameError,
    validate_container_name,
)


class TestContainerNameValidation:
    """Test container name validation for security"""

    def test_validate_valid_container_names(self):
        """Valid container names should pass validation"""
        valid_names = [
            "archon-mcp",
            "archon_server",
            "archon.service",
            "archon-service_1.0",
            "container123",
            "my-container_name.v2",
            "a",  # Single character
            "ABC123",  # Uppercase
            "test_container-v1.2.3",  # Mix of all allowed chars
        ]

        for name in valid_names:
            result = validate_container_name(name)
            assert result == name, f"Valid name {name!r} should pass validation"

    def test_validate_empty_name(self):
        """Empty container name should be rejected"""
        with pytest.raises(InvalidContainerNameError, match="cannot be empty"):
            validate_container_name("")

    def test_validate_too_long_name(self):
        """Container names exceeding max length should be rejected"""
        long_name = "a" * (MAX_CONTAINER_NAME_LENGTH + 1)

        with pytest.raises(InvalidContainerNameError, match="too long"):
            validate_container_name(long_name)

    def test_validate_max_length_name(self):
        """Container name at exactly max length should pass"""
        max_length_name = "a" * MAX_CONTAINER_NAME_LENGTH
        result = validate_container_name(max_length_name)
        assert result == max_length_name

    def test_validate_command_injection_attempts(self):
        """Command injection attempts should be rejected"""
        malicious_names = [
            "evil; rm -rf /",
            "container && echo hacked",
            "test | cat /etc/passwd",
            "name $(whoami)",
            "container`id`",
            "test\nmalicious",
            "container\x00null",
            "../../../etc/passwd",
            "container'DROP TABLE users",
            'test"injection',
        ]

        for name in malicious_names:
            with pytest.raises(
                InvalidContainerNameError, match="Invalid container name"
            ):
                validate_container_name(name)

    def test_validate_special_characters(self):
        """Special characters (except allowed ones) should be rejected"""
        invalid_names = [
            "container@service",  # @ not allowed
            "test#hash",  # # not allowed
            "service$var",  # $ not allowed
            "container%percent",  # % not allowed
            "test&ampersand",  # & not allowed
            "service*wildcard",  # * not allowed
            "container+plus",  # + not allowed
            "test=equals",  # = not allowed
            "service[bracket]",  # [] not allowed
            "container{brace}",  # {} not allowed
            "test/slash",  # / not allowed
            "service\\backslash",  # \ not allowed
            "container space",  # space not allowed
            "test\ttab",  # tab not allowed
        ]

        for name in invalid_names:
            with pytest.raises(
                InvalidContainerNameError, match="Invalid container name"
            ):
                validate_container_name(name)

    def test_validate_unicode_characters(self):
        """Unicode characters should be rejected"""
        unicode_names = [
            "container™",
            "test©right",
            "service®mark",
            "émoji",
            "中文",
            "日本語",
        ]

        for name in unicode_names:
            with pytest.raises(
                InvalidContainerNameError, match="Invalid container name"
            ):
                validate_container_name(name)

    def test_validate_logging_for_invalid_names(self, caplog):
        """Invalid names should be logged with warning"""
        import logging

        caplog.set_level(logging.WARNING)

        malicious_name = "evil; rm -rf /"

        with pytest.raises(InvalidContainerNameError):
            validate_container_name(malicious_name)

        # Check that warning was logged
        assert any(
            "Rejected invalid container name" in record.message
            and malicious_name in record.message
            for record in caplog.records
        ), "Should log warning for rejected container name"


class TestContainerHealthMonitorValidation:
    """Test that ContainerHealthMonitor properly validates container names"""

    @pytest.fixture
    def monitor(self, monkeypatch):
        """Create monitor instance with mocked alerting service"""
        # Set required environment variables
        monkeypatch.setenv("ALERT_CHECK_INTERVAL_SECONDS", "60")
        monkeypatch.setenv("ALERT_COOLDOWN_SECONDS", "300")
        monkeypatch.setenv("ERROR_COOLDOWN_SECONDS", "900")
        monkeypatch.setenv(
            "ENABLE_SLACK_ALERTS", "false"
        )  # Disable to avoid webhook requirement

        with (
            patch(
                "src.server.services.container_health_monitor.PipelineAlertingService"
            ),
            patch(
                "src.server.services.container_health_monitor.DOCKER_SDK_AVAILABLE",
                False,
            ),
        ):
            monitor = ContainerHealthMonitor()
            return monitor

    def test_get_container_health_validates_name(self, monitor):
        """get_container_health should validate container name"""
        with pytest.raises(InvalidContainerNameError):
            monitor.get_container_health("evil; rm -rf /")

    def test_get_container_health_accepts_valid_name(self, monitor):
        """get_container_health should accept valid container name"""
        with patch("subprocess.run") as mock_run:
            # Mock docker inspect to return "not found"
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

            # Should not raise validation error
            result = monitor.get_container_health("archon-mcp")
            assert result is None  # Container not found is OK

    def test_get_container_logs_validates_name(self, monitor):
        """get_container_logs should validate container name"""
        with pytest.raises(InvalidContainerNameError):
            monitor.get_container_logs("malicious && echo hacked")

    def test_get_container_logs_accepts_valid_name(self, monitor):
        """get_container_logs should accept valid container name"""
        with (
            patch("subprocess.run") as mock_run,
            patch.object(monitor.log_sanitizer, "sanitize", side_effect=lambda x: x),
        ):
            # Mock docker logs to return success
            mock_run.return_value = MagicMock(
                returncode=0, stdout="test logs", stderr=""
            )

            # Should not raise validation error
            result = monitor.get_container_logs("archon-mcp")
            assert result == "test logs"

    def test_get_all_containers_health_skips_invalid_names(self, monitor, caplog):
        """get_all_containers_health should skip invalid names from docker ps"""
        import logging

        caplog.set_level(logging.WARNING)

        with patch("subprocess.run") as mock_run:
            # Mock docker ps to return mix of valid and invalid names
            # Then mock docker inspect for each valid container
            mock_run.side_effect = [
                # First call: docker ps (list containers)
                MagicMock(
                    returncode=0,
                    stdout="archon-mcp\nevil; rm -rf /\narchon-server\n",
                    stderr="",
                ),
                # Second call: docker inspect for archon-mcp
                MagicMock(returncode=0, stdout="healthy\n", stderr=""),
                # Third call: docker inspect for archon-server
                MagicMock(returncode=0, stdout="healthy\n", stderr=""),
            ]

            # Should skip invalid name and continue
            result = monitor.get_all_containers_health()

            # Should have logged warning about invalid name
            assert any(
                "Skipping invalid container name" in record.message
                for record in caplog.records
            ), "Should log warning for invalid container name"


class TestValidationEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_validate_whitespace_only(self):
        """Whitespace-only names should be rejected"""
        with pytest.raises(InvalidContainerNameError):
            validate_container_name("   ")

    def test_validate_name_with_leading_trailing_spaces(self):
        """Names with leading/trailing spaces should be rejected"""
        # Note: In practice, docker ps output is stripped before validation
        # But the validation function itself should reject spaces
        with pytest.raises(InvalidContainerNameError):
            validate_container_name(" archon-mcp ")

    def test_validate_consecutive_allowed_chars(self):
        """Consecutive allowed special chars should be valid"""
        valid_names = [
            "container---service",  # Multiple hyphens
            "service___test",  # Multiple underscores
            "app...prod",  # Multiple dots
            "test-_-name",  # Mixed allowed chars
        ]

        for name in valid_names:
            result = validate_container_name(name)
            assert result == name

    def test_validate_starts_with_special_char(self):
        """Names starting with allowed special chars should be valid"""
        # Docker allows these, so we should too
        valid_names = [
            "-container",
            "_service",
            ".hidden",
        ]

        for name in valid_names:
            result = validate_container_name(name)
            assert result == name

    def test_validate_numeric_only_name(self):
        """Numeric-only names should be valid"""
        result = validate_container_name("12345")
        assert result == "12345"


class TestSecurityDocumentation:
    """Test that security features are properly documented"""

    def test_validate_function_has_security_docs(self):
        """validate_container_name should document security rules"""
        docstring = validate_container_name.__doc__
        assert docstring is not None
        assert "Security" in docstring or "command injection" in docstring.lower()
        assert "alphanumeric" in docstring.lower()
        assert "128" in docstring

    def test_exception_provides_clear_message(self):
        """InvalidContainerNameError should provide clear error message"""
        try:
            validate_container_name("evil; rm -rf /")
        except InvalidContainerNameError as e:
            error_message = str(e)
            assert "Invalid container name" in error_message
            assert "alphanumeric" in error_message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
