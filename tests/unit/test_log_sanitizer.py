"""
Unit tests for LogSanitizer.

Tests cover:
- Various secret pattern sanitization (OpenAI, GitHub, JWT, etc.)
- Email and IP sanitization (optional features)
- Custom patterns
- Edge cases (None, empty, disabled)
- Cache operations
- Environment variable configuration
- Error handling
"""

import os
from unittest.mock import patch

from omniintelligence.utils.log_sanitizer import (
    LogSanitizer,
    get_log_sanitizer,
    sanitize_logs,
)


class TestLogSanitizerBasics:
    """Test basic sanitization functionality."""

    def test_sanitize_openai_api_key(self):
        """Test OpenAI API key sanitization."""
        sanitizer = LogSanitizer()
        text = "Using key: sk-1234567890abcdefghijklmnop"
        result = sanitizer.sanitize(text)
        assert "[OPENAI_API_KEY]" in result
        assert "sk-1234567890" not in result

    def test_sanitize_github_personal_access_token(self):
        """Test GitHub PAT sanitization."""
        sanitizer = LogSanitizer()
        text = "Token: ghp_1234567890abcdefghijklmnopqrstuvwxyz1234"
        result = sanitizer.sanitize(text)
        assert "[GITHUB_TOKEN]" in result
        assert "ghp_" not in result

    def test_sanitize_github_oauth_token(self):
        """Test GitHub OAuth token sanitization."""
        sanitizer = LogSanitizer()
        text = "OAuth: gho_1234567890abcdefghijklmnopqrstuvwxyz1234"
        result = sanitizer.sanitize(text)
        assert "[GITHUB_OAUTH]" in result

    def test_sanitize_github_fine_grained_pat(self):
        """Test GitHub fine-grained PAT sanitization."""
        sanitizer = LogSanitizer()
        text = "Token: github_pat_1234567890abcdefghij"
        result = sanitizer.sanitize(text)
        assert "[GITHUB_PAT]" in result

    def test_sanitize_gitlab_token(self):
        """Test GitLab token sanitization."""
        sanitizer = LogSanitizer()
        text = "Token: glpat-1234567890abcdefghij"
        result = sanitizer.sanitize(text)
        assert "[GITLAB_TOKEN]" in result

    def test_sanitize_slack_bot_token(self):
        """Test Slack bot token sanitization."""
        sanitizer = LogSanitizer()
        text = "Slack: xoxb-12345678901-234567890123-abcdefghij"
        result = sanitizer.sanitize(text)
        assert "[SLACK_BOT_TOKEN]" in result

    def test_sanitize_slack_user_token(self):
        """Test Slack user token sanitization."""
        sanitizer = LogSanitizer()
        text = "Slack: xoxp-12345678901-234567890123-abcdefghij"
        result = sanitizer.sanitize(text)
        assert "[SLACK_USER_TOKEN]" in result

    def test_sanitize_google_api_key(self):
        """Test Google API key sanitization."""
        sanitizer = LogSanitizer()
        text = "Google: AIzaSyA1234567890abcdefghijklmnopqrstuv"
        result = sanitizer.sanitize(text)
        assert "[GOOGLE_API_KEY]" in result

    def test_sanitize_google_oauth_token(self):
        """Test Google OAuth token sanitization."""
        sanitizer = LogSanitizer()
        text = "Token: ya29.a0AfH6SMBx1234567890abcdefghij"
        result = sanitizer.sanitize(text)
        assert "[GOOGLE_OAUTH]" in result

    def test_sanitize_aws_access_key(self):
        """Test AWS access key sanitization."""
        sanitizer = LogSanitizer()
        text = "AWS Key: AKIAIOSFODNN7EXAMPLE"
        result = sanitizer.sanitize(text)
        assert "[AWS_ACCESS_KEY]" in result

    def test_sanitize_aws_secret_key(self):
        """Test AWS secret key sanitization."""
        sanitizer = LogSanitizer()
        text = 'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
        result = sanitizer.sanitize(text)
        assert "[AWS_SECRET_KEY]" in result

    def test_sanitize_jwt_token(self):
        """Test JWT token sanitization."""
        sanitizer = LogSanitizer()
        # Sample JWT structure: header.payload.signature
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        text = f"Bearer {jwt}"
        result = sanitizer.sanitize(text)
        assert "[JWT_TOKEN]" in result
        assert "eyJ" not in result

    def test_sanitize_password_in_url(self):
        """Test password in URL sanitization."""
        sanitizer = LogSanitizer()
        text = "Connecting to postgresql://user:secretpass123@localhost:5432/db"
        result = sanitizer.sanitize(text)
        assert "secretpass123" not in result
        assert "[PASSWORD]" in result

    def test_sanitize_password_in_config(self):
        """Test password in config sanitization."""
        sanitizer = LogSanitizer()
        text = 'password = "mysecretpassword"'
        result = sanitizer.sanitize(text)
        assert "mysecretpassword" not in result
        assert "[PASSWORD]" in result

    def test_sanitize_passwd_in_config(self):
        """Test passwd in config sanitization."""
        sanitizer = LogSanitizer()
        text = "passwd: mypassword123"
        result = sanitizer.sanitize(text)
        assert "mypassword123" not in result
        assert "[PASSWORD]" in result

    def test_sanitize_pwd_in_config(self):
        """Test pwd in config sanitization."""
        sanitizer = LogSanitizer()
        text = 'pwd="secretpwd"'
        result = sanitizer.sanitize(text)
        assert "secretpwd" not in result
        assert "[PASSWORD]" in result

    def test_sanitize_database_connection_string(self):
        """Test database connection string sanitization."""
        sanitizer = LogSanitizer()
        text = "mongodb://admin:password123@cluster.mongodb.net/mydb"
        result = sanitizer.sanitize(text)
        assert "password123" not in result
        assert "[DB]" in result

    def test_sanitize_slack_webhook(self):
        """Test Slack webhook URL sanitization."""
        sanitizer = LogSanitizer()
        text = "Webhook: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
        result = sanitizer.sanitize(text)
        assert "[SLACK_WEBHOOK_URL]" in result

    def test_sanitize_discord_webhook(self):
        """Test Discord webhook URL sanitization."""
        sanitizer = LogSanitizer()
        text = "Webhook: https://discord.com/api/webhooks/1234567890/abcdefghijklmnop"
        result = sanitizer.sanitize(text)
        assert "[DISCORD_WEBHOOK_URL]" in result

    def test_sanitize_generic_api_key(self):
        """Test generic API key sanitization."""
        sanitizer = LogSanitizer()
        text = 'api_key = "abcdefghijklmnopqrstuvwxyz"'
        result = sanitizer.sanitize(text)
        assert "api_key=[API_KEY]" in result

    def test_sanitize_generic_api_secret(self):
        """Test generic API secret sanitization."""
        sanitizer = LogSanitizer()
        text = 'api_secret: "abcdefghijklmnopqrstuvwxyz"'
        result = sanitizer.sanitize(text)
        assert "api_secret=[API_SECRET]" in result

    def test_sanitize_generic_secret_key(self):
        """Test generic secret key sanitization."""
        sanitizer = LogSanitizer()
        text = 'secret_key="abcdefghijklmnopqrstuvwxyz"'
        result = sanitizer.sanitize(text)
        assert "secret_key=[SECRET_KEY]" in result

    def test_sanitize_generic_access_token(self):
        """Test generic access token sanitization."""
        sanitizer = LogSanitizer()
        text = 'access_token = "abcdefghijklmnopqrstuvwxyz"'
        result = sanitizer.sanitize(text)
        assert "access_token=[ACCESS_TOKEN]" in result

    def test_sanitize_openai_env_var(self):
        """Test OpenAI API key in environment variable format."""
        sanitizer = LogSanitizer()
        text = 'OPENAI_API_KEY="sk-1234567890abcdefgh"'
        result = sanitizer.sanitize(text)
        assert "[API_KEY]" in result

    def test_sanitize_anthropic_env_var(self):
        """Test Anthropic API key in environment variable format."""
        sanitizer = LogSanitizer()
        text = "ANTHROPIC_API_KEY=sk-ant-1234567890"
        result = sanitizer.sanitize(text)
        assert "[API_KEY]" in result

    def test_sanitize_supabase_key(self):
        """Test Supabase key sanitization."""
        sanitizer = LogSanitizer()
        text = "SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = sanitizer.sanitize(text)
        assert "[SUPABASE_KEY]" in result

    def test_sanitize_auth_token(self):
        """Test auth token sanitization."""
        sanitizer = LogSanitizer()
        text = "SERVICE_AUTH_TOKEN=token_12345678"
        result = sanitizer.sanitize(text)
        assert "[AUTH_TOKEN]" in result


class TestLogSanitizerEdgeCases:
    """Test edge cases and special scenarios."""

    def test_sanitize_empty_string(self):
        """Test sanitization of empty string."""
        sanitizer = LogSanitizer()
        result = sanitizer.sanitize("")
        assert result == ""

    def test_sanitize_none_like_empty(self):
        """Test that empty string returns empty string."""
        sanitizer = LogSanitizer()
        result = sanitizer.sanitize("")
        assert result == ""

    def test_sanitize_text_without_secrets(self):
        """Test text without any secrets passes through unchanged."""
        sanitizer = LogSanitizer()
        text = "This is a normal log message without any secrets"
        result = sanitizer.sanitize(text)
        assert result == text

    def test_sanitize_multiple_secrets_in_one_line(self):
        """Test sanitization of multiple secrets in one line."""
        sanitizer = LogSanitizer()
        text = "OpenAI: sk-1234567890abcdefghijklmnop GitHub: ghp_1234567890abcdefghijklmnopqrstuvwxyz1234"
        result = sanitizer.sanitize(text)
        assert "[OPENAI_API_KEY]" in result
        assert "[GITHUB_TOKEN]" in result

    def test_sanitize_disabled(self):
        """Test that disabled sanitizer returns original text."""
        sanitizer = LogSanitizer(enable=False)
        text = "sk-1234567890abcdefghijklmnop"
        result = sanitizer.sanitize(text)
        # When disabled, original text is returned (line 282)
        assert result == text

    def test_sanitize_preserves_non_secret_content(self):
        """Test that non-secret content is preserved."""
        sanitizer = LogSanitizer()
        text = "User logged in at 2024-01-15 with sk-1234567890abcdefghijklmnop"
        result = sanitizer.sanitize(text)
        assert "User logged in at 2024-01-15" in result
        assert "[OPENAI_API_KEY]" in result


class TestLogSanitizerEmailSanitization:
    """Test email sanitization feature (line 214)."""

    def test_email_sanitization_disabled_by_default(self):
        """Test emails are NOT sanitized by default."""
        sanitizer = LogSanitizer()
        text = "Contact: test@example.com"
        result = sanitizer.sanitize(text)
        assert "test@example.com" in result  # Email should remain

    def test_email_sanitization_enabled(self):
        """Test emails ARE sanitized when enabled (line 214)."""
        sanitizer = LogSanitizer(sanitize_emails=True)
        text = "Contact: test@example.com"
        result = sanitizer.sanitize(text)
        assert "[EMAIL]" in result
        assert "test@example.com" not in result

    def test_email_sanitization_multiple_emails(self):
        """Test multiple email sanitization."""
        sanitizer = LogSanitizer(sanitize_emails=True)
        text = "From: sender@test.com To: recipient@example.org"
        result = sanitizer.sanitize(text)
        assert result.count("[EMAIL]") == 2


class TestLogSanitizerIPSanitization:
    """Test IP address sanitization feature (line 217)."""

    def test_ip_sanitization_disabled_by_default(self):
        """Test IPs are NOT sanitized by default."""
        sanitizer = LogSanitizer()
        text = "Connected from 192.168.1.100"
        result = sanitizer.sanitize(text)
        assert "192.168.1.100" in result  # IP should remain

    def test_ip_sanitization_enabled_ipv4(self):
        """Test IPv4 addresses ARE sanitized when enabled (line 217)."""
        sanitizer = LogSanitizer(sanitize_ips=True)
        text = "Connected from 192.168.1.100"
        result = sanitizer.sanitize(text)
        assert "[IP_ADDRESS]" in result
        assert "192.168.1.100" not in result

    def test_ip_sanitization_multiple_ips(self):
        """Test multiple IP sanitization."""
        sanitizer = LogSanitizer(sanitize_ips=True)
        text = "From 10.0.0.1 to 172.16.0.1"
        result = sanitizer.sanitize(text)
        assert result.count("[IP_ADDRESS]") == 2


class TestLogSanitizerCustomPatterns:
    """Test custom pattern functionality (line 220)."""

    def test_custom_pattern_addition(self):
        """Test adding custom patterns (line 220)."""
        custom_patterns = [
            (r"CUSTOM-[A-Z0-9]{10}", "[CUSTOM_TOKEN]", "Custom token"),
        ]
        sanitizer = LogSanitizer(custom_patterns=custom_patterns)
        text = "Token: CUSTOM-ABCDEF1234"
        result = sanitizer.sanitize(text)
        assert "[CUSTOM_TOKEN]" in result

    def test_custom_pattern_with_default_patterns(self):
        """Test custom patterns work alongside default patterns."""
        custom_patterns = [
            (r"MY_SECRET_[0-9]+", "[MY_SECRET]", "My secret pattern"),
        ]
        sanitizer = LogSanitizer(custom_patterns=custom_patterns)

        # Test custom pattern
        text1 = "MY_SECRET_12345678901234567890"
        result1 = sanitizer.sanitize(text1)
        assert "[MY_SECRET]" in result1

        # Test default pattern still works
        text2 = "sk-1234567890abcdefghijklmnop"
        result2 = sanitizer.sanitize(text2)
        assert "[OPENAI_API_KEY]" in result2

    def test_multiple_custom_patterns(self):
        """Test multiple custom patterns."""
        custom_patterns = [
            (r"SECRET_A_[0-9]+", "[SECRET_A]", "Secret A"),
            (r"SECRET_B_[A-Z]+", "[SECRET_B]", "Secret B"),
        ]
        sanitizer = LogSanitizer(custom_patterns=custom_patterns)
        text = (
            "SECRET_A_123456789012345678901234 and SECRET_B_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        )
        result = sanitizer.sanitize(text)
        assert "[SECRET_A]" in result
        assert "[SECRET_B]" in result


class TestLogSanitizerInvalidPatterns:
    """Test handling of invalid regex patterns (lines 228-229)."""

    def test_invalid_regex_pattern_is_skipped(self):
        """Test that invalid regex patterns are skipped with warning (lines 228-229)."""
        # Invalid regex with unbalanced parentheses
        custom_patterns = [
            (r"[invalid(regex", "[INVALID]", "Invalid pattern"),
            (r"VALID-[A-Z]+", "[VALID]", "Valid pattern"),
        ]
        # Should not raise, just log warning
        sanitizer = LogSanitizer(custom_patterns=custom_patterns)

        # Valid pattern should still work
        text = "VALID-ABCDEFGHIJKLMNOPQRSTU"
        result = sanitizer.sanitize(text)
        assert "[VALID]" in result


class TestLogSanitizerSanitizeLines:
    """Test sanitize_lines method (lines 302-305)."""

    def test_sanitize_lines_basic(self):
        """Test basic line sanitization."""
        sanitizer = LogSanitizer()
        lines = [
            "Line 1 with sk-1234567890abcdefghijklmnop",
            "Line 2 with ghp_1234567890abcdefghijklmnopqrstuvwxyz1234",
        ]
        result = sanitizer.sanitize_lines(lines)
        assert "[OPENAI_API_KEY]" in result[0]
        assert "[GITHUB_TOKEN]" in result[1]

    def test_sanitize_lines_empty_list(self):
        """Test sanitizing empty list (line 302-303)."""
        sanitizer = LogSanitizer()
        result = sanitizer.sanitize_lines([])
        assert result == []

    def test_sanitize_lines_disabled(self):
        """Test sanitize_lines when disabled (line 302)."""
        sanitizer = LogSanitizer(enable=False)
        lines = ["sk-1234567890abcdefghijklmnop"]
        result = sanitizer.sanitize_lines(lines)
        # When disabled, original lines are returned
        assert result == lines

    def test_sanitize_lines_preserves_order(self):
        """Test that line order is preserved."""
        sanitizer = LogSanitizer()
        lines = ["First line", "Second line", "Third line"]
        result = sanitizer.sanitize_lines(lines)
        assert result == lines


class TestLogSanitizerCacheOperations:
    """Test cache-related methods (lines 330-334, 348-349)."""

    def test_get_cache_info(self):
        """Test get_cache_info returns valid cache statistics (lines 330-334)."""
        sanitizer = LogSanitizer()
        # Clear any existing cache
        sanitizer.clear_cache()

        # Perform some sanitizations
        sanitizer.sanitize("test message 1")
        sanitizer.sanitize("test message 2")
        sanitizer.sanitize("test message 1")  # Cache hit

        cache_info = sanitizer.get_cache_info()
        assert "hits" in cache_info
        assert "misses" in cache_info
        assert "size" in cache_info
        assert "maxsize" in cache_info
        assert "hit_rate_percent" in cache_info
        assert cache_info["hits"] >= 1  # At least one hit from repeated message
        assert cache_info["misses"] >= 2  # At least two misses from unique messages

    def test_get_cache_info_empty_cache(self):
        """Test get_cache_info with empty cache."""
        sanitizer = LogSanitizer()
        sanitizer.clear_cache()

        cache_info = sanitizer.get_cache_info()
        assert cache_info["hits"] == 0
        assert cache_info["misses"] == 0
        assert cache_info["size"] == 0
        assert cache_info["hit_rate_percent"] == 0.0

    def test_clear_cache(self):
        """Test clear_cache method (lines 348-349)."""
        sanitizer = LogSanitizer()

        # Add some items to cache
        sanitizer.sanitize("test message")

        # Verify cache has items
        cache_info_before = sanitizer.get_cache_info()
        assert cache_info_before["size"] >= 1

        # Clear cache
        sanitizer.clear_cache()

        # Verify cache is empty
        cache_info_after = sanitizer.get_cache_info()
        assert cache_info_after["size"] == 0
        assert cache_info_after["hits"] == 0
        assert cache_info_after["misses"] == 0

    def test_cache_improves_performance_on_repeated_content(self):
        """Test that cache provides hits on repeated content."""
        sanitizer = LogSanitizer()
        sanitizer.clear_cache()

        text = "Repeated message with sk-1234567890abcdefghijklmnop"

        # First call - cache miss
        sanitizer.sanitize(text)
        info1 = sanitizer.get_cache_info()

        # Second call - should be cache hit
        sanitizer.sanitize(text)
        info2 = sanitizer.get_cache_info()

        assert info2["hits"] > info1["hits"]


class TestLogSanitizerPatternsInfo:
    """Test get_patterns_info method (line 314)."""

    def test_get_patterns_info_returns_list(self):
        """Test get_patterns_info returns pattern list (line 314)."""
        sanitizer = LogSanitizer()
        patterns_info = sanitizer.get_patterns_info()
        assert isinstance(patterns_info, list)
        assert len(patterns_info) > 0

    def test_get_patterns_info_structure(self):
        """Test pattern info structure."""
        sanitizer = LogSanitizer()
        patterns_info = sanitizer.get_patterns_info()

        for info in patterns_info:
            assert "pattern" in info
            assert "replacement" in info
            assert "description" in info

    def test_get_patterns_info_includes_custom(self):
        """Test custom patterns appear in patterns info."""
        custom_patterns = [
            (r"MY_CUSTOM_[0-9]+", "[MY_CUSTOM]", "My custom description"),
        ]
        sanitizer = LogSanitizer(custom_patterns=custom_patterns)
        patterns_info = sanitizer.get_patterns_info()

        descriptions = [p["description"] for p in patterns_info]
        assert "My custom description" in descriptions


class TestLogSanitizerErrorHandling:
    """Test error handling (lines 287-290)."""

    def test_sanitize_error_returns_original_text(self):
        """Test that errors during sanitization return original text (lines 287-290)."""
        sanitizer = LogSanitizer()
        text = "test message"

        # Mock the cached method to raise an exception
        with patch.object(
            sanitizer, "_sanitize_cached", side_effect=Exception("Test error")
        ):
            result = sanitizer.sanitize(text)
            # Should return original text on error
            assert result == text


class TestGlobalSanitizer:
    """Test global sanitizer functions (lines 381-388, 410-411)."""

    def test_get_log_sanitizer_creates_instance(self):
        """Test get_log_sanitizer creates instance."""
        # Reset global sanitizer
        import omniintelligence.utils.log_sanitizer as module

        module._sanitizer = None

        sanitizer = get_log_sanitizer()
        assert isinstance(sanitizer, LogSanitizer)

    def test_sanitize_logs_convenience_function(self):
        """Test sanitize_logs convenience function (lines 410-411)."""
        # Reset global sanitizer
        import omniintelligence.utils.log_sanitizer as module

        module._sanitizer = None

        text = "API key: sk-1234567890abcdefghijklmnop"
        result = sanitize_logs(text)
        assert "[OPENAI_API_KEY]" in result

    def test_get_log_sanitizer_with_env_vars(self):
        """Test get_log_sanitizer reads environment variables."""
        import omniintelligence.utils.log_sanitizer as module

        module._sanitizer = None

        env_vars = {
            "ENABLE_LOG_SANITIZATION": "true",
            "SANITIZE_EMAIL_ADDRESSES": "true",
            "SANITIZE_IP_ADDRESSES": "true",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            module._sanitizer = None
            sanitizer = get_log_sanitizer()
            assert sanitizer.sanitize_emails is True
            assert sanitizer.sanitize_ips is True

    def test_get_log_sanitizer_disabled_via_env(self):
        """Test disabling sanitization via environment variable."""
        import omniintelligence.utils.log_sanitizer as module

        module._sanitizer = None

        with patch.dict(os.environ, {"ENABLE_LOG_SANITIZATION": "false"}, clear=False):
            module._sanitizer = None
            sanitizer = get_log_sanitizer()
            assert sanitizer.enable is False

    def test_get_log_sanitizer_custom_patterns_from_env(self):
        """Test custom patterns from environment variable (lines 381-388)."""
        import omniintelligence.utils.log_sanitizer as module

        module._sanitizer = None

        custom_patterns_str = "CUSTOM_[0-9]+|[CUSTOM]|Custom pattern"

        with patch.dict(
            os.environ,
            {"CUSTOM_SANITIZATION_PATTERNS": custom_patterns_str},
            clear=False,
        ):
            module._sanitizer = None
            sanitizer = get_log_sanitizer()

            # Test the custom pattern works
            text = "CUSTOM_1234567890123456789012"
            result = sanitizer.sanitize(text)
            assert "[CUSTOM]" in result

    def test_get_log_sanitizer_multiple_custom_patterns_from_env(self):
        """Test multiple custom patterns from environment variable."""
        import omniintelligence.utils.log_sanitizer as module

        module._sanitizer = None

        # Multiple patterns separated by semicolon
        custom_patterns_str = "PATTERN_A_[0-9]+|[PATTERN_A]|Pattern A;PATTERN_B_[A-Z]+|[PATTERN_B]|Pattern B"

        with patch.dict(
            os.environ,
            {"CUSTOM_SANITIZATION_PATTERNS": custom_patterns_str},
            clear=False,
        ):
            module._sanitizer = None
            sanitizer = get_log_sanitizer()

            patterns_info = sanitizer.get_patterns_info()
            descriptions = [p["description"] for p in patterns_info]
            assert "Pattern A" in descriptions
            assert "Pattern B" in descriptions

    def test_get_log_sanitizer_invalid_custom_patterns_from_env(self):
        """Test handling of invalid custom patterns in env var (lines 381-388)."""
        import omniintelligence.utils.log_sanitizer as module

        module._sanitizer = None

        # Invalid format (only 2 parts instead of 3)
        custom_patterns_str = "INVALID_PATTERN|[INVALID]"

        with patch.dict(
            os.environ,
            {"CUSTOM_SANITIZATION_PATTERNS": custom_patterns_str},
            clear=False,
        ):
            module._sanitizer = None
            # Should not raise, just skip invalid pattern
            sanitizer = get_log_sanitizer()
            assert isinstance(sanitizer, LogSanitizer)

    def test_get_log_sanitizer_empty_custom_pattern_string(self):
        """Test empty custom pattern string from env."""
        import omniintelligence.utils.log_sanitizer as module

        module._sanitizer = None

        with patch.dict(os.environ, {"CUSTOM_SANITIZATION_PATTERNS": ""}, clear=False):
            module._sanitizer = None
            sanitizer = get_log_sanitizer()
            assert isinstance(sanitizer, LogSanitizer)

    def test_get_log_sanitizer_returns_same_instance(self):
        """Test get_log_sanitizer returns singleton."""
        import omniintelligence.utils.log_sanitizer as module

        module._sanitizer = None

        sanitizer1 = get_log_sanitizer()
        sanitizer2 = get_log_sanitizer()
        assert sanitizer1 is sanitizer2


class TestLogSanitizerPerformance:
    """Test performance characteristics."""

    def test_large_input_handling(self):
        """Test handling of large input."""
        sanitizer = LogSanitizer()

        # Generate large text with secrets
        lines = []
        for i in range(100):
            lines.append(f"Line {i}: sk-{i:020d}abcdefghijkl")

        large_text = "\n".join(lines)
        result = sanitizer.sanitize(large_text)

        # All API keys should be sanitized
        assert "[OPENAI_API_KEY]" in result
        # Original keys should not be present
        assert "sk-00000000000000000000" not in result

    def test_nested_dict_simulation(self):
        """Test sanitization of JSON-like string content."""
        sanitizer = LogSanitizer()

        json_text = """{
            "api_key": "sk-1234567890abcdefghijklmnop",
            "config": {
                "github_token": "ghp_1234567890abcdefghijklmnopqrstuvwxyz1234",
                "database": "postgresql://user:secret123@localhost/db"
            }
        }"""

        result = sanitizer.sanitize(json_text)
        assert "[OPENAI_API_KEY]" in result
        assert "[GITHUB_TOKEN]" in result
        assert "[PASSWORD]" in result or "[DB]" in result


class TestLogSanitizerIntegration:
    """Integration tests combining multiple features."""

    def test_all_features_enabled(self):
        """Test with all optional features enabled."""
        custom_patterns = [
            (r"INTERNAL_[A-Z0-9]{8}", "[INTERNAL_ID]", "Internal ID"),
        ]
        sanitizer = LogSanitizer(
            sanitize_emails=True,
            sanitize_ips=True,
            custom_patterns=custom_patterns,
        )

        text = (
            "User test@example.com from 192.168.1.1 "
            "using token sk-1234567890abcdefghijklmnop "
            "with internal id INTERNAL_ABC12345"
        )

        result = sanitizer.sanitize(text)
        assert "[EMAIL]" in result
        assert "[IP_ADDRESS]" in result
        assert "[OPENAI_API_KEY]" in result
        assert "[INTERNAL_ID]" in result

    def test_sanitizer_thread_safety_basic(self):
        """Test basic thread safety of sanitizer."""
        import concurrent.futures

        sanitizer = LogSanitizer()

        def sanitize_text(i: int) -> str:
            text = f"Request {i}: sk-{i:020d}abcdefghijkl"
            return sanitizer.sanitize(text)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(sanitize_text, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All results should be sanitized
        for result in results:
            assert "[OPENAI_API_KEY]" in result


class TestLogSanitizerLegacyImports:
    """Test backwards compatibility with legacy import paths."""

    def test_legacy_import_emits_deprecation_warning(self):
        """Test that importing from _legacy emits deprecation warning."""
        import sys
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Clear any cached imports to force reimport
            modules_to_clear = [
                k for k in sys.modules if k.startswith("omniintelligence._legacy")
            ]
            for mod in modules_to_clear:
                del sys.modules[mod]

            # Now import and check for warnings
            from omniintelligence._legacy.utils import log_sanitizer as legacy_module  # noqa: F401

            # Should have at least one deprecation warning
            deprecation_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "deprecated" in str(deprecation_warnings[0].message).lower()

    def test_legacy_import_provides_same_class(self):
        """Test that legacy import provides the same LogSanitizer class."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from omniintelligence._legacy.utils.log_sanitizer import (
                LogSanitizer as LegacyLogSanitizer,
            )

        from omniintelligence.utils.log_sanitizer import LogSanitizer

        assert LogSanitizer is LegacyLogSanitizer

    def test_legacy_import_provides_same_functions(self):
        """Test that legacy import provides the same functions."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from omniintelligence._legacy.utils.log_sanitizer import (
                get_log_sanitizer as legacy_get_log_sanitizer,
            )
            from omniintelligence._legacy.utils.log_sanitizer import (
                sanitize_logs as legacy_sanitize_logs,
            )

        from omniintelligence.utils.log_sanitizer import (
            get_log_sanitizer,
            sanitize_logs,
        )

        assert get_log_sanitizer is legacy_get_log_sanitizer
        assert sanitize_logs is legacy_sanitize_logs

    def test_legacy_sanitizer_works_correctly(self):
        """Test that sanitizer from legacy import works correctly."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from omniintelligence._legacy.utils.log_sanitizer import LogSanitizer

        sanitizer = LogSanitizer()
        text = "Using key: sk-1234567890abcdefghijklmnop"
        result = sanitizer.sanitize(text)
        assert "[OPENAI_API_KEY]" in result
        assert "sk-1234567890" not in result
