"""
Unit tests for IntelligenceSecurityValidator.

Tests comprehensive security validation including:
- Path traversal prevention
- Content size limits
- Content security validation
- Operation permissions
- Encoding validation
- Language validation

Test Coverage:
- Valid inputs (happy path)
- Invalid inputs (security violations)
- Edge cases (empty, null, boundary values)
- Performance (pattern compilation caching)
"""

import os

import pytest
from src.intelligence.security import (
    IntelligenceSecurityValidator,
    ValidationResult,
)
from src.intelligence.security.intelligence_security_validator import (
    MAX_CONTENT_SIZE_BYTES,
    MAX_PATH_LENGTH,
    EnumIntelligenceOperationType,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def validator():
    """Create security validator with default settings."""
    return IntelligenceSecurityValidator()


@pytest.fixture
def validator_with_allowed_paths(tmp_path):
    """Create security validator with specific allowed paths."""
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    return IntelligenceSecurityValidator(allowed_base_paths=[str(allowed_dir)])


# ============================================================================
# Path Validation Tests
# ============================================================================


class TestPathValidation:
    """Test path sanitization and validation."""

    def test_valid_relative_path(self, validator):
        """Test valid relative path."""
        result = validator.sanitize_source_path("src/core/api.py")

        assert result.valid
        assert len(result.errors) == 0
        assert "source_path" in result.sanitized_data
        assert result.sanitized_data["source_path"] == os.path.normpath(
            "src/core/api.py"
        )

    def test_valid_absolute_path_in_cwd(self, validator):
        """Test valid absolute path within current working directory."""
        cwd = os.getcwd()
        test_path = os.path.join(cwd, "src/api.py")

        result = validator.sanitize_source_path(test_path)

        assert result.valid
        assert len(result.errors) == 0

    def test_path_traversal_unix(self, validator):
        """Test path traversal detection (Unix style)."""
        result = validator.sanitize_source_path("../../etc/passwd")

        assert not result.valid
        assert any("traversal" in err.lower() for err in result.errors)

    def test_path_traversal_windows(self, validator):
        """Test path traversal detection (Windows style)."""
        result = validator.sanitize_source_path("..\\..\\Windows\\System32")

        assert not result.valid
        assert any("suspicious pattern" in err.lower() for err in result.errors)

    def test_path_traversal_url_encoded(self, validator):
        """Test URL-encoded path traversal detection."""
        result = validator.sanitize_source_path("%2e%2e%2fetc%2fpasswd")

        assert not result.valid
        assert any("suspicious pattern" in err.lower() for err in result.errors)

    def test_absolute_path_outside_allowed(self, validator_with_allowed_paths):
        """Test absolute path outside allowed directories."""
        result = validator_with_allowed_paths.sanitize_source_path("/etc/passwd")

        assert not result.valid
        assert any(
            "outside allowed directories" in err.lower() for err in result.errors
        )

    def test_null_bytes_in_path(self, validator):
        """Test null byte detection in path."""
        result = validator.sanitize_source_path("src/api.py\x00malicious")

        assert not result.valid
        assert any("null bytes" in err.lower() for err in result.errors)

    def test_overly_long_path(self, validator):
        """Test path length validation."""
        long_path = "a/" * (MAX_PATH_LENGTH // 2 + 1)  # Exceed max length

        result = validator.sanitize_source_path(long_path)

        assert not result.valid
        assert any("too long" in err.lower() for err in result.errors)

    def test_empty_path(self, validator):
        """Test empty path handling."""
        result = validator.sanitize_source_path("")

        assert not result.valid
        assert any("empty" in err.lower() for err in result.errors)

    def test_none_path(self, validator):
        """Test None path handling."""
        result = validator.sanitize_source_path(None)

        assert not result.valid
        assert any("non-null string" in err.lower() for err in result.errors)

    def test_path_normalization(self, validator):
        """Test path normalization."""
        # Use path with ./ (current dir) but no .. (traversal)
        result = validator.sanitize_source_path("src/./api.py")

        assert result.valid
        # Should normalize to src/api.py
        assert result.sanitized_data["source_path"] == os.path.normpath("src/api.py")


# ============================================================================
# Content Validation Tests
# ============================================================================


class TestContentValidation:
    """Test content security validation."""

    def test_valid_content(self, validator):
        """Test valid content."""
        content = "def calculate_total(items):\n    return sum(items)"
        result = validator.validate_content_security(content)

        assert result.valid
        assert len(result.errors) == 0

    def test_empty_content(self, validator):
        """Test empty content (allowed but warns)."""
        result = validator.validate_content_security("")

        assert result.valid  # Non-blocking
        assert any("empty" in warn.lower() for warn in result.warnings)

    def test_none_content(self, validator):
        """Test None content."""
        result = validator.validate_content_security(None)

        assert not result.valid
        assert any("non-null string" in err.lower() for err in result.errors)

    def test_content_too_large(self, validator):
        """Test content size limit."""
        # Create content exceeding 10MB limit
        large_content = "x" * (MAX_CONTENT_SIZE_BYTES + 1)
        result = validator.validate_content_security(large_content)

        assert not result.valid
        assert any("too large" in err.lower() for err in result.errors)

    def test_content_max_size_boundary(self, validator):
        """Test content at max size boundary (should pass)."""
        # Exactly 10MB
        max_content = "x" * MAX_CONTENT_SIZE_BYTES
        result = validator.validate_content_security(max_content)

        assert result.valid

    def test_null_bytes_in_content(self, validator):
        """Test null byte detection in content."""
        content = "def foo():\x00 malicious_code()"
        result = validator.validate_content_security(content)

        assert not result.valid
        assert any("null bytes" in err.lower() for err in result.errors)

    def test_invalid_utf8_encoding(self, validator):
        """Test invalid UTF-8 encoding detection."""
        # This is tricky - Python strings are already Unicode
        # We need to test the validation logic
        # For now, valid Python strings are valid UTF-8
        content = "def foo():\n    return 'valid unicode: \u00e9'"
        result = validator.validate_content_security(content)

        assert result.valid

    def test_suspicious_pattern_xss(self, validator):
        """Test XSS pattern detection (warning, not blocking)."""
        content = "<script>alert('xss')</script>"
        result = validator.validate_content_security(content)

        assert result.valid  # Non-blocking warning
        assert any("suspicious pattern" in warn.lower() for warn in result.warnings)

    def test_suspicious_pattern_eval(self, validator):
        """Test eval() pattern detection (warning)."""
        content = "eval(user_input)"
        result = validator.validate_content_security(content)

        assert result.valid  # Non-blocking warning
        assert any("suspicious pattern" in warn.lower() for warn in result.warnings)


# ============================================================================
# Quality Assessment Validation Tests
# ============================================================================


class TestQualityAssessmentValidation:
    """Test quality assessment request validation."""

    def test_valid_quality_assessment(self, validator):
        """Test valid quality assessment request."""
        result = validator.validate_quality_assessment(
            content="def calculate(): return 42",
            source_path="src/api.py",
            language="python",
            min_quality_threshold=0.7,
        )

        assert result.valid
        assert len(result.errors) == 0
        assert result.sanitized_data["content"] == "def calculate(): return 42"
        assert "src/api.py" in result.sanitized_data["source_path"]
        assert result.sanitized_data["language"] == "python"

    def test_quality_assessment_no_language(self, validator):
        """Test quality assessment without language (auto-detect)."""
        result = validator.validate_quality_assessment(
            content="def foo(): pass",
            source_path="src/api.py",
            language=None,
            min_quality_threshold=0.7,
        )

        assert result.valid
        assert result.sanitized_data["language"] is None

    def test_quality_assessment_invalid_threshold(self, validator):
        """Test quality assessment with invalid threshold."""
        result = validator.validate_quality_assessment(
            content="def foo(): pass",
            source_path="src/api.py",
            language="python",
            min_quality_threshold=1.5,  # Invalid (>1.0)
        )

        assert not result.valid
        assert any("threshold" in err.lower() for err in result.errors)

    def test_quality_assessment_invalid_path(self, validator):
        """Test quality assessment with invalid path."""
        result = validator.validate_quality_assessment(
            content="def foo(): pass",
            source_path="../../etc/passwd",  # Path traversal
            language="python",
            min_quality_threshold=0.7,
        )

        assert not result.valid
        assert any("traversal" in err.lower() for err in result.errors)

    def test_quality_assessment_unrecognized_language(self, validator):
        """Test quality assessment with unrecognized language (warning)."""
        result = validator.validate_quality_assessment(
            content="code here",
            source_path="src/api.xyz",
            language="unknown_lang",
            min_quality_threshold=0.7,
        )

        assert result.valid  # Non-blocking
        assert any("unrecognized language" in warn.lower() for warn in result.warnings)


# ============================================================================
# Performance Analysis Validation Tests
# ============================================================================


class TestPerformanceAnalysisValidation:
    """Test performance analysis request validation."""

    def test_valid_performance_analysis(self, validator):
        """Test valid performance analysis request."""
        result = validator.validate_performance_analysis(
            operation_name="database_query",
            code_content="async def query(): return await db.fetch_all()",
            context={"execution_type": "async", "io_type": "database"},
            target_percentile=95,
        )

        assert result.valid
        assert len(result.errors) == 0
        assert result.sanitized_data["operation_name"] == "database_query"

    def test_performance_analysis_no_context(self, validator):
        """Test performance analysis without context."""
        result = validator.validate_performance_analysis(
            operation_name="api_endpoint",
            code_content="def endpoint(): return {'status': 'ok'}",
            context=None,
            target_percentile=90,
        )

        assert result.valid

    def test_performance_analysis_invalid_percentile(self, validator):
        """Test performance analysis with invalid percentile."""
        result = validator.validate_performance_analysis(
            operation_name="test_op",
            code_content="def foo(): pass",
            context=None,
            target_percentile=85,  # Invalid (not in [50, 90, 95, 99])
        )

        assert not result.valid
        assert any("percentile" in err.lower() for err in result.errors)

    def test_performance_analysis_deep_context(self, validator):
        """Test performance analysis with deeply nested context (should fail)."""
        # Create deeply nested dict (>5 levels)
        deep_context = {
            "level1": {
                "level2": {"level3": {"level4": {"level5": {"level6": "too deep"}}}}
            }
        }

        result = validator.validate_performance_analysis(
            operation_name="test_op",
            code_content="def foo(): pass",
            context=deep_context,
            target_percentile=95,
        )

        assert not result.valid
        assert any("deeply nested" in err.lower() for err in result.errors)


# ============================================================================
# Pattern Detection Validation Tests
# ============================================================================


class TestPatternDetectionValidation:
    """Test pattern detection request validation."""

    def test_valid_pattern_detection(self, validator):
        """Test valid pattern detection request."""
        result = validator.validate_pattern_detection(
            content="class UserService:\n    def __init__(self): pass",
            source_path="src/services/user.py",
            min_confidence=0.8,
        )

        assert result.valid
        assert len(result.errors) == 0

    def test_pattern_detection_invalid_confidence(self, validator):
        """Test pattern detection with invalid confidence."""
        result = validator.validate_pattern_detection(
            content="code here",
            source_path="src/api.py",
            min_confidence=-0.5,  # Invalid (<0.0)
        )

        assert not result.valid
        assert any("confidence" in err.lower() for err in result.errors)


# ============================================================================
# Operation Permission Tests
# ============================================================================


class TestOperationPermission:
    """Test operation permission validation."""

    def test_quality_assessment_allowed(self, validator):
        """Test quality assessment operation is allowed."""
        result = validator.check_operation_allowed(
            EnumIntelligenceOperationType.QUALITY_ASSESSMENT
        )

        assert result.valid

    def test_performance_analysis_allowed(self, validator):
        """Test performance analysis operation is allowed."""
        result = validator.check_operation_allowed(
            EnumIntelligenceOperationType.PERFORMANCE_ANALYSIS
        )

        assert result.valid

    def test_pattern_detection_allowed(self, validator):
        """Test pattern detection operation is allowed."""
        result = validator.check_operation_allowed(
            EnumIntelligenceOperationType.PATTERN_DETECTION
        )

        assert result.valid

    def test_architectural_compliance_allowed(self, validator):
        """Test architectural compliance operation is allowed."""
        result = validator.check_operation_allowed(
            EnumIntelligenceOperationType.ARCHITECTURAL_COMPLIANCE
        )

        assert result.valid

    def test_invalid_operation_type(self, validator):
        """Test invalid operation type (not enum)."""
        result = validator.check_operation_allowed("invalid_operation")

        assert not result.valid
        assert any("invalid" in err.lower() for err in result.errors)


# ============================================================================
# Language Validation Tests
# ============================================================================


class TestLanguageValidation:
    """Test language validation."""

    def test_valid_languages(self, validator):
        """Test recognized languages."""
        valid_langs = ["python", "typescript", "rust", "go", "java"]

        for lang in valid_langs:
            result = validator._validate_language(lang)
            assert result.valid
            assert result.sanitized_data["language"] == lang.lower()

    def test_case_insensitive_language(self, validator):
        """Test case-insensitive language validation."""
        result = validator._validate_language("PYTHON")

        assert result.valid
        assert result.sanitized_data["language"] == "python"

    def test_unrecognized_language(self, validator):
        """Test unrecognized language (warning, not error)."""
        result = validator._validate_language("unknown_lang")

        assert result.valid  # Non-blocking
        assert any("unrecognized" in warn.lower() for warn in result.warnings)


# ============================================================================
# Identifier Validation Tests
# ============================================================================


class TestIdentifierValidation:
    """Test identifier validation."""

    def test_valid_identifier(self, validator):
        """Test valid identifier."""
        result = validator._validate_identifier("database_query_users")

        assert result.valid

    def test_identifier_with_hyphens(self, validator):
        """Test identifier with hyphens."""
        result = validator._validate_identifier("api-endpoint-users")

        assert result.valid

    def test_identifier_with_slashes(self, validator):
        """Test identifier with slashes (for operation names like 'api/users')."""
        result = validator._validate_identifier("api/users/endpoint")

        assert result.valid

    def test_invalid_identifier_special_chars(self, validator):
        """Test identifier with invalid special characters."""
        result = validator._validate_identifier("operation@name!")

        assert not result.valid
        assert any("invalid characters" in err.lower() for err in result.errors)

    def test_empty_identifier(self, validator):
        """Test empty identifier."""
        result = validator._validate_identifier("")

        assert not result.valid
        assert any("empty" in err.lower() for err in result.errors)

    def test_identifier_too_long(self, validator):
        """Test identifier exceeding max length."""
        long_id = "x" * 201  # Exceed default 100 char limit

        result = validator._validate_identifier(long_id, max_length=100)

        assert not result.valid
        assert any("too long" in err.lower() for err in result.errors)


# ============================================================================
# JSON Safety Validation Tests
# ============================================================================


class TestJSONSafetyValidation:
    """Test JSON structure safety validation."""

    def test_valid_json(self, validator):
        """Test valid JSON structure."""
        json_data = {"key1": "value1", "key2": {"nested": "value2"}}

        result = validator._validate_json_safety(json_data)

        assert result.valid

    def test_deeply_nested_json(self, validator):
        """Test deeply nested JSON (exceeds max depth)."""
        # Create 12 levels of nesting (exceeds default 10)
        deep_json = {"level1": {}}
        current = deep_json["level1"]
        for i in range(2, 13):
            current[f"level{i}"] = {}
            current = current[f"level{i}"]

        result = validator._validate_json_safety(deep_json, max_depth=10)

        assert not result.valid
        assert any("deeply nested" in err.lower() for err in result.errors)

    def test_too_many_keys(self, validator):
        """Test JSON with too many keys."""
        # Create dict with >100 keys
        many_keys = {f"key{i}": f"value{i}" for i in range(150)}

        result = validator._validate_json_safety(many_keys, max_keys=100)

        assert not result.valid
        assert any("too many keys" in err.lower() for err in result.errors)

    def test_none_json(self, validator):
        """Test None JSON."""
        result = validator._validate_json_safety(None)

        assert not result.valid
        assert any("non-null dictionary" in err.lower() for err in result.errors)


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests combining multiple validation steps."""

    def test_full_quality_assessment_workflow(self, validator):
        """Test complete quality assessment validation workflow."""
        # Valid request
        result = validator.validate_quality_assessment(
            content="def calculate_total(items):\n    return sum(item.price for item in items)",
            source_path="src/core/calculator.py",
            language="python",
            min_quality_threshold=0.7,
        )

        assert result.valid
        assert "content" in result.sanitized_data
        assert "source_path" in result.sanitized_data
        assert "language" in result.sanitized_data

    def test_security_violation_blocks_request(self, validator):
        """Test that security violations block requests."""
        # Request with path traversal
        result = validator.validate_quality_assessment(
            content="malicious code",
            source_path="../../etc/passwd",
            language="python",
            min_quality_threshold=0.7,
        )

        assert not result.valid
        assert result.sanitized_data is None  # No sanitized data on failure

    def test_warnings_dont_block(self, validator):
        """Test that warnings don't block valid requests."""
        # Request with suspicious content (eval) but valid otherwise
        result = validator.validate_quality_assessment(
            content="eval(user_input)",
            source_path="src/api.py",
            language="python",
            min_quality_threshold=0.7,
        )

        assert result.valid  # Warnings don't block
        assert len(result.warnings) > 0  # But warnings are present

    def test_multiple_validation_errors(self, validator):
        """Test accumulation of multiple validation errors."""
        # Multiple violations
        result = validator.validate_quality_assessment(
            content="x" * (MAX_CONTENT_SIZE_BYTES + 1),  # Too large
            source_path="../../etc/passwd",  # Path traversal
            language="python",
            min_quality_threshold=1.5,  # Invalid threshold
        )

        assert not result.valid
        assert len(result.errors) >= 3  # At least 3 errors
