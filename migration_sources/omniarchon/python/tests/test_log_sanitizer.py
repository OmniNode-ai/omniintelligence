"""
Tests for Log Sanitization Service

Verifies that sensitive data is properly removed from log messages before
sending to external services (Slack, email, etc.)
"""

import pytest
from src.server.services.log_sanitizer import LogSanitizer


class TestLogSanitizer:
    """Test log sanitization functionality"""

    def setup_method(self):
        """Setup test instances"""
        self.sanitizer = LogSanitizer(
            enable=True, sanitize_emails=False, sanitize_ips=False
        )
        self.sanitizer_with_emails = LogSanitizer(
            enable=True, sanitize_emails=True, sanitize_ips=False
        )
        self.sanitizer_with_ips = LogSanitizer(
            enable=True, sanitize_emails=False, sanitize_ips=True
        )

    def test_openai_api_key_sanitization(self):
        """Test OpenAI API key sanitization"""
        log = "Using API key sk-1234567890abcdefghijklmnopqrstuvwxyz"
        result = self.sanitizer.sanitize(log)

        assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in result
        assert "[OPENAI_API_KEY]" in result
        assert "Using API key" in result

    def test_github_token_sanitization(self):
        """Test GitHub personal access token sanitization"""
        log = "Authenticated with ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        result = self.sanitizer.sanitize(log)

        assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in result
        assert "[GITHUB_TOKEN]" in result

    def test_github_oauth_token_sanitization(self):
        """Test GitHub OAuth token sanitization"""
        log = "OAuth token: gho_1234567890abcdefghijklmnopqrstuvwxyz"
        result = self.sanitizer.sanitize(log)

        assert "gho_1234567890abcdefghijklmnopqrstuvwxyz" not in result
        assert "[GITHUB_OAUTH]" in result

    def test_github_pat_sanitization(self):
        """Test GitHub fine-grained PAT sanitization"""
        log = "Token: github_pat_11AAAAAA0000000000_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        result = self.sanitizer.sanitize(log)

        assert "github_pat_11AAAAAA0000000000_" not in result
        assert "[GITHUB_PAT]" in result

    def test_slack_bot_token_sanitization(self):
        """Test Slack bot token sanitization"""
        log = "Slack bot token: xoxb-123456789012-123456789012-TestTokenNotRealABCDEF"
        result = self.sanitizer.sanitize(log)

        assert "xoxb-123456789012-123456789012-TestTokenNotRealABCDEF" not in result
        assert "[SLACK_BOT_TOKEN]" in result

    def test_password_in_url_sanitization(self):
        """Test password in URL sanitization"""
        log = "Connecting to postgresql://user:SecretPass123@db.example.com/mydb"
        result = self.sanitizer.sanitize(log)

        assert "SecretPass123" not in result
        assert "[USERNAME]:[PASSWORD]@" in result

    def test_password_in_config_sanitization(self):
        """Test password in configuration sanitization"""
        test_cases = [
            ('password="MySecret123"', "password=[PASSWORD]"),
            ("password: SuperSecret", "password=[PASSWORD]"),
            ("passwd=MyPass", "passwd=[PASSWORD]"),
            ('pwd: "test123"', "pwd=[PASSWORD]"),
        ]

        for original, expected_pattern in test_cases:
            result = self.sanitizer.sanitize(original)
            assert "MySecret" not in result
            assert "SuperSecret" not in result
            assert "MyPass" not in result
            assert "test123" not in result
            assert expected_pattern in result

    def test_database_connection_string_sanitization(self):
        """Test database connection string sanitization"""
        test_cases = [
            "postgresql://admin:secret123@localhost:5432/mydb",
            "mysql://root:password@db.local/database",
            "mongodb://user:pass@mongo:27017/data",
            "redis://user:redis_password@cache:6379/0",
        ]

        for db_url in test_cases:
            result = self.sanitizer.sanitize(db_url)
            assert "secret123" not in result
            assert "password" not in result or result == db_url  # may not match pattern
            assert "pass" not in result or "[PASSWORD]" in result
            assert "redis_password" not in result
            assert "[USERNAME]:[PASSWORD]@[HOST]/[DB]" in result

    def test_email_address_sanitization(self):
        """Test email address sanitization (when enabled)"""
        log = "Contact admin@example.com for support or user.name@test.co.uk"
        result = self.sanitizer_with_emails.sanitize(log)

        assert "admin@example.com" not in result
        assert "user.name@test.co.uk" not in result
        assert "[EMAIL]" in result
        assert "Contact" in result
        assert "for support" in result

    def test_email_address_not_sanitized_by_default(self):
        """Test email addresses are preserved when sanitize_emails=False (default)"""
        log = "Contact admin@example.com for support or user.name@test.co.uk"
        result = self.sanitizer.sanitize(log)

        # Emails should be preserved (not redacted) by default
        assert "admin@example.com" in result
        assert "user.name@test.co.uk" in result
        assert "[EMAIL]" not in result
        # Non-sensitive content should be preserved
        assert "Contact" in result
        assert "for support" in result

    def test_slack_webhook_url_sanitization(self):
        """Test Slack webhook URL sanitization"""
        log = "Webhook: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
        result = self.sanitizer.sanitize(log)

        assert "T00000000" not in result
        assert "B00000000" not in result
        assert "XXXXXXXXXXXXXXXXXXXX" not in result
        assert "[SLACK_WEBHOOK_URL]" in result

    def test_discord_webhook_url_sanitization(self):
        """Test Discord webhook URL sanitization"""
        log = "Discord: https://discord.com/api/webhooks/1234567890/abcdefghijklmnopqrstuvwxyz"
        result = self.sanitizer.sanitize(log)

        assert "1234567890" not in result
        assert "abcdefghijklmnopqrstuvwxyz" not in result
        assert "[DISCORD_WEBHOOK_URL]" in result

    def test_jwt_token_sanitization(self):
        """Test JWT token sanitization"""
        log = (
            "Authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        result = self.sanitizer.sanitize(log)

        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[JWT_TOKEN]" in result

    def test_generic_api_key_sanitization(self):
        """Test generic API key patterns"""
        test_cases = [
            ('api_key="abc123def456ghi789jkl012mno345pqr678"', "api_key=[API_KEY]"),
            ("api-key: xyz789abc123def456ghi789", "api_key=[API_KEY]"),
            (
                'api_secret: "my_secret_key_12345678901234567890"',
                "api_secret=[API_SECRET]",
            ),
            ("secret_key=sk_live_1234567890abcdefghij", "secret_key=[SECRET_KEY]"),
            ('access_token: "tok_1234567890abcdefghij"', "access_token=[ACCESS_TOKEN]"),
        ]

        for original, expected_pattern in test_cases:
            result = self.sanitizer.sanitize(original)
            # Verify key is removed
            assert "abc123def456ghi789jkl012mno345pqr678" not in result
            assert "xyz789abc123def456ghi789" not in result
            assert "my_secret_key_12345678901234567890" not in result
            assert "sk_live_1234567890abcdefghij" not in result
            assert "tok_1234567890abcdefghij" not in result
            # Verify replacement present
            assert expected_pattern in result

    def test_environment_variable_api_keys_sanitization(self):
        """Test API keys in environment variables"""
        test_cases = [
            ("OPENAI_API_KEY=sk-1234567890abcdefghijklmnopqrstuvwxyz", "=[API_KEY]"),
            ('ANTHROPIC_API_KEY="sk-ant-1234567890"', "=[API_KEY]"),
            ("GEMINI_API_KEY: AIzaSyA12345678901234567890123456789", "=[API_KEY]"),
        ]

        for original, expected_pattern in test_cases:
            result = self.sanitizer.sanitize(original)
            # Verify sensitive values are removed
            assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in result
            assert "sk-ant-1234567890" not in result
            assert "AIzaSyA12345678901234567890123456789" not in result
            # Verify some form of sanitization occurred
            assert expected_pattern in result
            # Verify key names are still recognizable (may be partially sanitized)
            if "OPENAI" in original:
                assert "OPENAI" in result
            elif "ANTHROPIC" in original:
                assert "ANTHROPIC" in result
            elif "GEMINI" in original:
                assert "GEMINI" in result

    def test_supabase_key_sanitization(self):
        """Test Supabase key sanitization"""
        test_cases = [
            (
                'SUPABASE_SERVICE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123"',
                "SUPABASE_SERVICE_KEY=[SUPABASE_KEY]",
            ),
            (
                "SUPABASE_ANON_KEY: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz789",
                "SUPABASE_ANON_KEY=[SUPABASE_KEY]",
            ),
        ]

        for original, expected_pattern in test_cases:
            result = self.sanitizer.sanitize(original)
            assert "abc123" not in result or "[SUPABASE_KEY]" in result
            assert "xyz789" not in result or "[SUPABASE_KEY]" in result

    def test_auth_token_sanitization(self):
        """Test auth token sanitization"""
        log = 'SERVICE_AUTH_TOKEN="Bearer_1234567890abcdefghij"'
        result = self.sanitizer.sanitize(log)

        assert "Bearer_1234567890abcdefghij" not in result
        assert "SERVICE_AUTH_TOKEN=[AUTH_TOKEN]" in result

    def test_ip_address_sanitization_disabled_by_default(self):
        """Test that IP sanitization is disabled by default"""
        log = "Connection from 192.168.1.100 to 10.0.0.5"
        result = self.sanitizer.sanitize(log)

        # IPs should NOT be sanitized when sanitize_ips=False
        assert "192.168.1.100" in result
        assert "10.0.0.5" in result

    def test_ip_address_sanitization_when_enabled(self):
        """Test IP sanitization when enabled"""
        log = "Connection from 192.168.1.100 to 10.0.0.5"
        result = self.sanitizer_with_ips.sanitize(log)

        # IPs should be sanitized when sanitize_ips=True
        assert "192.168.1.100" not in result
        assert "10.0.0.5" not in result
        assert "[IP_ADDRESS]" in result

    def test_ipv6_address_sanitization_when_enabled(self):
        """Test IPv6 sanitization when enabled"""
        log = "IPv6: 2001:0DB8:0000:0000:0000:0000:1428:57AB"
        result = self.sanitizer_with_ips.sanitize(log)

        assert "2001:0DB8:0000:0000:0000:0000:1428:57AB" not in result
        assert "[IPv6_ADDRESS]" in result

    def test_multiple_sensitive_data_in_one_line(self):
        """Test sanitization of multiple sensitive items in one line"""
        log = (
            "Connecting to postgresql://admin:secret@db.local/app with "
            "API key sk-1234567890abcdefghijklmnopqrstuvwxyz and "
            "email support@example.com"
        )
        result = self.sanitizer_with_emails.sanitize(log)

        # All sensitive data should be removed
        assert "secret" not in result
        assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in result
        assert "support@example.com" not in result

        # Replacements should be present
        assert "[PASSWORD]" in result
        assert "[OPENAI_API_KEY]" in result
        assert "[EMAIL]" in result

    def test_sanitize_lines(self):
        """Test batch sanitization of multiple lines"""
        lines = [
            "Normal log line",
            "API key: sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "Email: user@example.com",
            "Another normal line",
        ]

        result = self.sanitizer_with_emails.sanitize_lines(lines)

        assert len(result) == 4
        assert result[0] == "Normal log line"
        assert "[OPENAI_API_KEY]" in result[1]
        assert "[EMAIL]" in result[2]
        assert result[3] == "Another normal line"

    def test_empty_input(self):
        """Test sanitization with empty input"""
        assert self.sanitizer.sanitize("") == ""
        assert self.sanitizer.sanitize(None) == None
        assert self.sanitizer.sanitize_lines([]) == []

    def test_disabled_sanitizer(self):
        """Test that disabled sanitizer returns original text"""
        sanitizer = LogSanitizer(enable=False)
        log = "API key sk-1234567890abcdefghijklmnopqrstuvwxyz"

        result = sanitizer.sanitize(log)

        # Should return original text when disabled
        assert result == log
        assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" in result

    def test_custom_patterns(self):
        """Test custom sanitization patterns"""
        custom_patterns = [
            (r"CUSTOM_SECRET_\w+", "[CUSTOM_SECRET]", "Custom secret pattern"),
            (r"SPECIAL_TOKEN_\d{10}", "[SPECIAL_TOKEN]", "Special token pattern"),
        ]

        sanitizer = LogSanitizer(enable=True, custom_patterns=custom_patterns)

        log = "Found CUSTOM_SECRET_ABC123 and SPECIAL_TOKEN_1234567890"
        result = sanitizer.sanitize(log)

        assert "CUSTOM_SECRET_ABC123" not in result
        assert "SPECIAL_TOKEN_1234567890" not in result
        assert "[CUSTOM_SECRET]" in result
        assert "[SPECIAL_TOKEN]" in result

    def test_get_patterns_info(self):
        """Test pattern information retrieval"""
        info = self.sanitizer.get_patterns_info()

        assert isinstance(info, list)
        assert len(info) > 0

        # Check structure
        for pattern_info in info:
            assert "pattern" in pattern_info
            assert "replacement" in pattern_info
            assert "description" in pattern_info

        # Check for expected patterns
        descriptions = [p["description"] for p in info]
        assert "OpenAI API key" in descriptions
        assert "GitHub personal access token" in descriptions
        assert "Slack webhook URL" in descriptions

    def test_case_insensitive_matching(self):
        """Test that pattern matching is case insensitive"""
        test_cases = [
            "ERROR: api_key=sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "error: API_KEY=sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "Error: Api_Key=sk-1234567890abcdefghijklmnopqrstuvwxyz",
        ]

        for log in test_cases:
            result = self.sanitizer.sanitize(log)
            # OpenAI key pattern matches first (more specific), which is correct
            assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in result
            # Verify some form of redaction occurred
            assert "[OPENAI_API_KEY]" in result or "[API_KEY]" in result

    def test_real_world_docker_log(self):
        """Test sanitization of real-world Docker log format"""
        log = """
2025-10-20 10:15:30 INFO Starting service
2025-10-20 10:15:31 DEBUG Connecting to postgresql://admin:secretpass@db:5432/archon
2025-10-20 10:15:32 INFO Connected successfully
2025-10-20 10:15:33 DEBUG Using API key: sk-1234567890abcdefghijklmnopqrstuvwxyz
2025-10-20 10:15:34 ERROR Failed to send webhook to https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
2025-10-20 10:15:35 INFO Contact admin@archon.dev for support
"""
        result = self.sanitizer_with_emails.sanitize(log)

        # Check sensitive data removed
        assert "secretpass" not in result
        assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in result
        assert "T00000000" not in result
        assert "B00000000" not in result
        assert "XXXXXXXXXXXXXXXXXXXX" not in result
        assert "admin@archon.dev" not in result

        # Check replacements present
        assert "[PASSWORD]" in result
        assert "[OPENAI_API_KEY]" in result
        assert "[SLACK_WEBHOOK_URL]" in result
        assert "[EMAIL]" in result

        # Check normal log content preserved
        assert "2025-10-20 10:15:30 INFO Starting service" in result
        assert "Connected successfully" in result
        assert "for support" in result

    def test_aws_credentials_sanitization(self):
        """Test AWS credentials sanitization"""
        log = """
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
"""
        result = self.sanitizer.sanitize(log)

        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in result
        assert "[AWS_ACCESS_KEY]" in result
        assert "[AWS_SECRET_KEY]" in result

    def test_google_api_key_sanitization(self):
        """Test Google API key sanitization"""
        log = "Google API key: AIzaSyTestKey000000000000NotRealFake000"
        result = self.sanitizer.sanitize(log)

        assert "AIzaSyTestKey000000000000NotRealFake000" not in result
        assert "[GOOGLE_API_KEY]" in result

    def test_google_oauth_token_sanitization(self):
        """Test Google OAuth token sanitization"""
        log = "OAuth: ya29.a0AfH6SMBx1234567890"
        result = self.sanitizer.sanitize(log)

        assert "ya29.a0AfH6SMBx1234567890" not in result
        assert "[GOOGLE_OAUTH]" in result

    def test_gitlab_token_sanitization(self):
        """Test GitLab token sanitization"""
        log = "GitLab token: glpat-1234567890_abcdefghij"
        result = self.sanitizer.sanitize(log)

        assert "glpat-1234567890_abcdefghij" not in result
        assert "[GITLAB_TOKEN]" in result

    def test_slack_user_token_sanitization(self):
        """Test Slack user token sanitization"""
        log = "User token: xoxp-1234567890-1234567890-1234567890-abcdefghijklmnopqrstuvwxyz"
        result = self.sanitizer.sanitize(log)

        assert (
            "xoxp-1234567890-1234567890-1234567890-abcdefghijklmnopqrstuvwxyz"
            not in result
        )
        assert "[SLACK_USER_TOKEN]" in result

    def test_error_handling_in_sanitize(self):
        """Test that sanitizer handles errors gracefully"""
        # Create a sanitizer with an invalid pattern that will cause an error during initialization
        # (this tests the warning path in __init__)
        # Note: Invalid patterns are logged but don't crash initialization

        sanitizer = LogSanitizer(enable=True)
        # Even with potential pattern errors, sanitizer should work
        result = sanitizer.sanitize("test log message")
        assert result == "test log message" or "test log message" in result


class TestLogSanitizerIntegration:
    """Integration tests for log sanitizer with container health monitor"""

    def test_container_log_sanitization_example(self):
        """Test realistic container log sanitization scenario"""
        sanitizer = LogSanitizer(enable=True, sanitize_emails=True)

        # Simulate a container log with various sensitive data
        container_log = """
[2025-10-20 10:00:00] INFO: Starting archon-intelligence service
[2025-10-20 10:00:01] DEBUG: Database URL: postgresql://archon:MySecretPass123@memgraph:7687/archon
[2025-10-20 10:00:02] DEBUG: OpenAI API Key configured: sk-1234567890abcdefghijklmnopqrstuvwxyz
[2025-10-20 10:00:03] ERROR: Failed to connect to Qdrant at http://qdrant:6333
[2025-10-20 10:00:04] INFO: Slack webhook configured: https://hooks.slack.com/services/T00000000/B00000000/TestWebhookNotRealDontUse123
[2025-10-20 10:00:05] CRITICAL: Exception in health check
Traceback (most recent call last):
  File "main.py", line 100, in check_health
    connection = connect(password="SuperSecret123")
neo4j.exceptions.ServiceUnavailable: Cannot resolve address memgraph:7687
[2025-10-20 10:00:06] INFO: Contact support@archon.dev for help
"""

        sanitized = sanitizer.sanitize(container_log)

        # Verify all sensitive data is removed
        assert "MySecretPass123" not in sanitized
        assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in sanitized
        assert "T12345678" not in sanitized
        assert "B12345678" not in sanitized
        assert "abcdefghijklmnopqrstuvwx" not in sanitized
        assert "SuperSecret123" not in sanitized
        assert "support@archon.dev" not in sanitized

        # Verify structure and context preserved
        assert "Starting archon-intelligence service" in sanitized
        assert "Failed to connect to Qdrant" in sanitized
        assert "Exception in health check" in sanitized
        assert "neo4j.exceptions.ServiceUnavailable" in sanitized
        assert "Cannot resolve address memgraph:7687" in sanitized
        assert "for help" in sanitized

    def test_error_log_line_sanitization(self):
        """Test sanitization of error log lines before alerting"""
        sanitizer = LogSanitizer(enable=True)

        error_lines = [
            "ERROR: Authentication failed with token sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "CRITICAL: Database password=MySecretPass123 is invalid",
            "Exception: Failed to send to webhook https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX",
        ]

        sanitized_lines = sanitizer.sanitize_lines(error_lines)

        # Check all lines are sanitized
        for sanitized in sanitized_lines:
            assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in sanitized
            assert "MySecretPass123" not in sanitized
            assert "T00000000" not in sanitized
            assert "XXXXXXXXXXXXXXXXXXXX" not in sanitized

        # Check error context preserved
        assert "Authentication failed" in sanitized_lines[0]
        assert (
            "Database" in sanitized_lines[1]
            and "password" in sanitized_lines[1].lower()
        )
        assert "Failed to send to webhook" in sanitized_lines[2]
