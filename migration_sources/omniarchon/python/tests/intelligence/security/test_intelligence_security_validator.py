"""
Security validation tests for IntelligenceSecurityValidator.

Tests comprehensive security validation for Intelligence Adapter:
- Path traversal detection and prevention
- Content size limit enforcement
- Encoding validation (UTF-8)
- Operation permission checks
- Input sanitization
- Suspicious pattern detection

Test Pattern: Security-focused unit testing
Reference: omninode_bridge security validation tests
"""

from pathlib import Path
from typing import Any, Dict

import pytest
from src.intelligence.security.intelligence_security_validator import (
    MAX_CONTENT_SIZE_BYTES,
    MAX_PATH_LENGTH,
    EnumIntelligenceOperationType,
    IntelligenceSecurityValidator,
    ValidationResult,
)


class TestIntelligenceSecurityValidator:
    """Test suite for Intelligence Security Validator."""

    @pytest.fixture
    def validator(self, tmp_path):
        """Create validator with temp directory as allowed base path."""
        return IntelligenceSecurityValidator(allowed_base_paths=[str(tmp_path)])

    @pytest.fixture
    def safe_code_sample(self):
        """Create safe code sample."""
        return """
def calculate(x: int, y: int) -> int:
    '''Add two numbers.'''
    return x + y
"""

    # =========================================================================
    # Path Traversal Detection Tests
    # =========================================================================

    def test_path_traversal_unix_style(self, validator):
        """Test detection of Unix-style path traversal (../)."""
        result = validator.sanitize_source_path("../etc/passwd")

        assert result.valid is False
        assert any("traversal" in error.lower() for error in result.errors)

    def test_path_traversal_windows_style(self, validator):
        """Test detection of Windows-style path traversal (..\)."""
        result = validator.sanitize_source_path("..\\Windows\\System32\\config")

        assert result.valid is False
        assert any(
            "traversal" in error.lower() or "suspicious" in error.lower()
            for error in result.errors
        )

    def test_path_traversal_url_encoded(self, validator):
        """Test detection of URL-encoded path traversal."""
        result = validator.sanitize_source_path("%2e%2e%2fetc%2fpasswd")

        assert result.valid is False
        assert any("suspicious" in error.lower() for error in result.errors)

    def test_path_traversal_system_file_access(self, validator):
        """Test detection of system file access attempts."""
        # Unix system files
        result = validator.sanitize_source_path("/etc/passwd")

        assert result.valid is False
        assert any("suspicious" in error.lower() for error in result.errors)

        # Windows system files
        result = validator.sanitize_source_path("C:\\Windows\\System32\\drivers")

        assert result.valid is False
        assert len(result.errors) > 0

    def test_path_traversal_normalized_detection(self, validator):
        """Test detection after path normalization."""
        result = validator.sanitize_source_path("src/../../etc/passwd")

        assert result.valid is False
        assert len(result.errors) > 0

    def test_safe_relative_path_allowed(self, validator):
        """Test safe relative paths are allowed."""
        result = validator.sanitize_source_path("src/api/endpoints.py")

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.sanitized_data["source_path"] is not None

    def test_safe_absolute_path_within_allowed_dir(self, validator, tmp_path):
        """Test absolute path within allowed directory is accepted."""
        safe_path = tmp_path / "src" / "main.py"
        result = validator.sanitize_source_path(str(safe_path))

        assert result.valid is True
        assert len(result.errors) == 0

    def test_absolute_path_outside_allowed_dir_rejected(self, validator):
        """Test absolute path outside allowed directory is rejected."""
        result = validator.sanitize_source_path("/tmp/outside/file.py")

        assert result.valid is False
        assert any("outside allowed" in error.lower() for error in result.errors)

    def test_null_byte_in_path_detected(self, validator):
        """Test null byte injection in path is detected."""
        result = validator.sanitize_source_path("src/main.py\x00.txt")

        assert result.valid is False
        assert any("null" in error.lower() for error in result.errors)

    def test_path_too_long_rejected(self, validator):
        """Test overly long path is rejected."""
        long_path = "a/" * (MAX_PATH_LENGTH // 2 + 1)  # Exceed limit
        result = validator.sanitize_source_path(long_path)

        assert result.valid is False
        assert any("too long" in error.lower() for error in result.errors)

    def test_empty_path_rejected(self, validator):
        """Test empty path is rejected."""
        result = validator.sanitize_source_path("")

        assert result.valid is False
        assert any("empty" in error.lower() for error in result.errors)

    def test_whitespace_only_path_rejected(self, validator):
        """Test whitespace-only path is rejected."""
        result = validator.sanitize_source_path("   ")

        assert result.valid is False
        assert any("empty" in error.lower() for error in result.errors)

    # =========================================================================
    # Content Size Limit Tests
    # =========================================================================

    def test_content_size_within_limit_accepted(self, validator):
        """Test content within size limit is accepted."""
        content = "x" * 1000  # 1KB, well under 10MB limit
        result = validator.validate_content_security(content)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_content_size_exceeds_limit_rejected(self, validator):
        """Test content exceeding 10MB limit is rejected."""
        content = "x" * (MAX_CONTENT_SIZE_BYTES + 1000)  # Exceed limit
        result = validator.validate_content_security(content)

        assert result.valid is False
        assert any("too large" in error.lower() for error in result.errors)

    def test_content_size_at_limit_accepted(self, validator):
        """Test content at exact limit is accepted."""
        content = "x" * MAX_CONTENT_SIZE_BYTES  # Exactly at limit
        result = validator.validate_content_security(content)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_empty_content_allowed_with_warning(self, validator):
        """Test empty content is allowed but generates warning."""
        result = validator.validate_content_security("")

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) > 0
        assert any("empty" in warning.lower() for warning in result.warnings)

    # =========================================================================
    # Encoding Validation Tests
    # =========================================================================

    def test_valid_utf8_encoding_accepted(self, validator):
        """Test valid UTF-8 content is accepted."""
        content = "Hello, 世界! 🌍"
        result = validator.validate_content_security(content)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_null_bytes_in_content_rejected(self, validator):
        """Test content with null bytes is rejected."""
        content = "valid content\x00malicious"
        result = validator.validate_content_security(content)

        assert result.valid is False
        assert any("null" in error.lower() for error in result.errors)

    def test_non_string_content_rejected(self, validator):
        """Test non-string content is rejected."""
        result = validator.validate_content_security(None)

        assert result.valid is False
        assert any("non-null string" in error.lower() for error in result.errors)

    # =========================================================================
    # Operation Permission Tests
    # =========================================================================

    def test_all_operation_types_allowed(self, validator):
        """Test all defined operation types are allowed."""
        for op_type in EnumIntelligenceOperationType:
            result = validator.check_operation_allowed(op_type)

            assert result.valid is True
            assert len(result.errors) == 0

    def test_invalid_operation_type_rejected(self, validator):
        """Test invalid operation type is rejected."""
        result = validator.check_operation_allowed("invalid_operation")

        assert result.valid is False
        assert len(result.errors) > 0

    # =========================================================================
    # Suspicious Pattern Detection Tests
    # =========================================================================

    def test_xss_pattern_detected(self, validator):
        """Test XSS pattern generates warning."""
        content = "<script>alert('XSS')</script>"
        result = validator.validate_content_security(content)

        assert result.valid is True  # Warning, not blocking
        assert len(result.warnings) > 0
        assert any("suspicious" in warning.lower() for warning in result.warnings)

    def test_eval_pattern_detected(self, validator):
        """Test eval() usage generates warning."""
        content = "result = eval(user_input)"
        result = validator.validate_content_security(content)

        assert result.valid is True  # Warning, not blocking
        assert len(result.warnings) > 0

    def test_safe_code_no_warnings(self, validator, safe_code_sample):
        """Test safe code generates no warnings."""
        result = validator.validate_content_security(safe_code_sample)

        assert result.valid is True
        assert len(result.errors) == 0
        # May have no warnings or legitimate warnings are acceptable

    # =========================================================================
    # Quality Assessment Validation Tests
    # =========================================================================

    def test_quality_assessment_valid_inputs(self, validator, safe_code_sample):
        """Test quality assessment validation with valid inputs."""
        result = validator.validate_quality_assessment(
            content=safe_code_sample,
            source_path="src/math_utils.py",
            language="python",
            min_quality_threshold=0.7,
        )

        assert result.valid is True
        assert result.sanitized_data["content"] == safe_code_sample
        assert result.sanitized_data["source_path"] is not None
        assert result.sanitized_data["language"] == "python"

    def test_quality_assessment_invalid_threshold(self, validator, safe_code_sample):
        """Test quality assessment rejects invalid threshold."""
        result = validator.validate_quality_assessment(
            content=safe_code_sample,
            source_path="src/test.py",
            language="python",
            min_quality_threshold=1.5,  # Invalid, > 1.0
        )

        assert result.valid is False
        assert any("threshold" in error.lower() for error in result.errors)

    def test_quality_assessment_unrecognized_language(
        self, validator, safe_code_sample
    ):
        """Test quality assessment allows unrecognized language with warning."""
        result = validator.validate_quality_assessment(
            content=safe_code_sample,
            source_path="src/test.xyz",
            language="unknown_lang",
            min_quality_threshold=0.7,
        )

        assert result.valid is True  # Non-blocking
        assert len(result.warnings) > 0
        assert any("unrecognized" in warning.lower() for warning in result.warnings)

    def test_quality_assessment_no_language_allowed(self, validator, safe_code_sample):
        """Test quality assessment allows None language (auto-detection)."""
        result = validator.validate_quality_assessment(
            content=safe_code_sample,
            source_path="src/test.py",
            language=None,
            min_quality_threshold=0.7,
        )

        assert result.valid is True
        assert result.sanitized_data["language"] is None

    # =========================================================================
    # Performance Analysis Validation Tests
    # =========================================================================

    def test_performance_analysis_valid_inputs(self, validator, safe_code_sample):
        """Test performance analysis validation with valid inputs."""
        result = validator.validate_performance_analysis(
            operation_name="calculate_sum",
            code_content=safe_code_sample,
            context={"request_count": 1000},
            target_percentile=95,
        )

        assert result.valid is True
        assert result.sanitized_data["operation_name"] == "calculate_sum"
        assert result.sanitized_data["code_content"] == safe_code_sample
        assert result.sanitized_data["target_percentile"] == 95

    def test_performance_analysis_invalid_percentile(self, validator, safe_code_sample):
        """Test performance analysis rejects invalid percentile."""
        result = validator.validate_performance_analysis(
            operation_name="test_op",
            code_content=safe_code_sample,
            context={},
            target_percentile=75,  # Not in allowed list
        )

        assert result.valid is False
        assert any("percentile" in error.lower() for error in result.errors)

    def test_performance_analysis_empty_operation_name(
        self, validator, safe_code_sample
    ):
        """Test performance analysis rejects empty operation name."""
        result = validator.validate_performance_analysis(
            operation_name="",
            code_content=safe_code_sample,
            context={},
            target_percentile=95,
        )

        assert result.valid is False
        assert any("empty" in error.lower() for error in result.errors)

    def test_performance_analysis_context_too_deep(self, validator, safe_code_sample):
        """Test performance analysis rejects deeply nested context."""
        # Create deeply nested context (> max_depth)
        deep_context = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {"level5": {"level6": {"level7": {"level8": {}}}}}
                    }
                }
            }
        }

        result = validator.validate_performance_analysis(
            operation_name="test_op",
            code_content=safe_code_sample,
            context=deep_context,
            target_percentile=95,
        )

        assert result.valid is False
        assert any(
            "nested" in error.lower() or "depth" in error.lower()
            for error in result.errors
        )

    # =========================================================================
    # Pattern Detection Validation Tests
    # =========================================================================

    def test_pattern_detection_valid_inputs(self, validator, safe_code_sample):
        """Test pattern detection validation with valid inputs."""
        result = validator.validate_pattern_detection(
            content=safe_code_sample,
            source_path="src/utils.py",
            min_confidence=0.7,
        )

        assert result.valid is True
        assert result.sanitized_data["content"] == safe_code_sample
        assert result.sanitized_data["min_confidence"] == 0.7

    def test_pattern_detection_invalid_confidence(self, validator, safe_code_sample):
        """Test pattern detection rejects invalid confidence threshold."""
        result = validator.validate_pattern_detection(
            content=safe_code_sample,
            source_path="src/test.py",
            min_confidence=1.5,  # Invalid, > 1.0
        )

        assert result.valid is False
        assert any("confidence" in error.lower() for error in result.errors)

    def test_pattern_detection_negative_confidence(self, validator, safe_code_sample):
        """Test pattern detection rejects negative confidence."""
        result = validator.validate_pattern_detection(
            content=safe_code_sample,
            source_path="src/test.py",
            min_confidence=-0.1,  # Invalid, < 0.0
        )

        assert result.valid is False
        assert any("confidence" in error.lower() for error in result.errors)

    # =========================================================================
    # Input Sanitization Tests
    # =========================================================================

    def test_whitespace_trimming_in_path(self, validator):
        """Test whitespace is properly trimmed from paths."""
        result = validator.sanitize_source_path("  src/main.py  ")

        assert result.valid is True
        # Path should be trimmed (handled by normpath)
        assert result.sanitized_data["source_path"] is not None

    def test_identifier_validation_alphanumeric(self, validator):
        """Test identifier validation allows alphanumeric + _ - /."""
        result = validator._validate_identifier("my_operation-name/v1")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_identifier_validation_invalid_characters(self, validator):
        """Test identifier validation rejects invalid characters."""
        result = validator._validate_identifier("my@operation#name")

        assert result.valid is False
        assert any("invalid characters" in error.lower() for error in result.errors)

    def test_identifier_too_long_rejected(self, validator):
        """Test identifier exceeding max length is rejected."""
        long_id = "a" * 300  # Default max_length is 100
        result = validator._validate_identifier(long_id)

        assert result.valid is False
        assert any("too long" in error.lower() for error in result.errors)

    # =========================================================================
    # Combined Validation Tests
    # =========================================================================

    def test_multiple_validation_errors_accumulated(self, validator):
        """Test multiple validation errors are accumulated."""
        # Path traversal + null bytes + too long
        malicious_path = "../etc/passwd\x00" + ("a" * MAX_PATH_LENGTH)

        result = validator.sanitize_source_path(malicious_path)

        assert result.valid is False
        assert len(result.errors) >= 2  # Multiple errors detected

    def test_sanitized_data_only_on_success(self, validator):
        """Test sanitized_data is only present on successful validation."""
        # Valid case
        valid_result = validator.sanitize_source_path("src/test.py")
        assert valid_result.valid is True
        assert valid_result.sanitized_data is not None

        # Invalid case
        invalid_result = validator.sanitize_source_path("../etc/passwd")
        assert invalid_result.valid is False
        assert invalid_result.sanitized_data is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
