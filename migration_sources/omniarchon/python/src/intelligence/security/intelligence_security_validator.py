"""
Intelligence Security Validator - ONEX Effect Node Security

Comprehensive security validation for Intelligence Adapter Effect Node.
Validates inputs before calling Intelligence Service APIs to prevent:
- Path traversal attacks
- Content injection attacks
- Buffer overflow (via size limits)
- Encoding vulnerabilities
- Invalid operation requests

ONEX Pattern: Security layer for Effect Node (Intelligence Adapter)
Based on: /omninode_bridge/security/validation.py patterns

Security Checks:
1. Path Traversal: Detect ../, absolute paths outside allowed directories
2. Content Size: Enforce 10MB limit (from ModelIntelligenceInput)
3. Content Security: Check for null bytes, suspicious patterns
4. Operation Permissions: Validate operation type is allowed
5. Encoding: Validate UTF-8 encoding
6. Language: Validate language is recognized

Usage:
    validator = IntelligenceSecurityValidator()

    # Validate quality assessment request
    result = validator.validate_quality_assessment(
        content=code,
        source_path="src/api.py",
        language="python"
    )

    if not result.valid:
        logger.error(f"Validation failed: {result.errors}")
        raise SecurityValidationError(result.errors)

    # Use sanitized data
    sanitized_path = result.sanitized_data["source_path"]
"""

import logging
import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Constants and Enums
# ============================================================================


class EnumIntelligenceOperationType(str, Enum):
    """Intelligence operation types (must match Intelligence Service API)."""

    QUALITY_ASSESSMENT = "quality_assessment"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    PATTERN_DETECTION = "pattern_detection"
    ARCHITECTURAL_COMPLIANCE = "architectural_compliance"


# Security Constants
MAX_CONTENT_SIZE_BYTES = 10 * 1024 * 1024  # 10MB limit
MAX_PATH_LENGTH = 4096  # Maximum path length (typical filesystem limit)
ALLOWED_LANGUAGES = {
    "python",
    "typescript",
    "javascript",
    "rust",
    "go",
    "java",
    "c",
    "cpp",
    "c++",
    "csharp",
    "c#",
    "ruby",
    "php",
    "swift",
    "kotlin",
    "scala",
    "r",
    "julia",
    "perl",
    "lua",
    "shell",
    "bash",
    "sql",
    "html",
    "css",
    "markdown",
    "json",
    "yaml",
    "xml",
}

# Suspicious patterns in source code content
SUSPICIOUS_CONTENT_PATTERNS = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),  # XSS
    re.compile(r"\x00"),  # Null bytes
    re.compile(
        r"(eval|exec)\s*\(", re.IGNORECASE
    ),  # Dynamic code execution (Note: legitimate in some contexts)
]


# ============================================================================
# Models
# ============================================================================


class ValidationResult(BaseModel):
    """
    Validation result container.

    Attributes:
        valid: Whether validation passed
        errors: List of validation errors (blocking)
        warnings: List of validation warnings (non-blocking)
        sanitized_data: Sanitized/normalized data (if valid)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid": True,
                "errors": [],
                "warnings": ["Content contains eval() - ensure context is safe"],
                "sanitized_data": {
                    "content": "def calculate(): return 42",
                    "source_path": "src/core/calculator.py",
                    "language": "python",
                },
            }
        }
    )

    valid: bool = Field(
        ..., description="Whether validation passed (True = safe to proceed)"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Validation errors (blocking - must fix to proceed)",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Validation warnings (non-blocking - informational)",
    )
    sanitized_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Sanitized/normalized data (safe to use)"
    )


# ============================================================================
# Security Validator
# ============================================================================


class IntelligenceSecurityValidator:
    """
    Security validator for intelligence operations.

    Validates:
    - Input sanitization (content, paths)
    - Path traversal prevention
    - Content size limits
    - Operation permissions
    - Encoding validation
    - Language validation

    Based on omninode_bridge SecurityValidator patterns with
    intelligence-specific enhancements.
    """

    def __init__(self, allowed_base_paths: Optional[List[str]] = None):
        """
        Initialize security validator.

        Args:
            allowed_base_paths: List of allowed base paths for path validation.
                               If None, uses current working directory.
        """
        self.allowed_base_paths = allowed_base_paths or [os.getcwd()]
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance (follows omninode_bridge pattern)."""
        # Path traversal patterns (compiled for performance)
        self.path_traversal_patterns = [
            re.compile(r"\.\.\/"),  # Unix path traversal
            re.compile(r"\.\.\\"),  # Windows path traversal
            re.compile(r"%2e%2e%2f", re.IGNORECASE),  # URL-encoded path traversal
            re.compile(r"%2e%2e\\", re.IGNORECASE),  # URL-encoded Windows traversal
            re.compile(r"\/etc\/passwd", re.IGNORECASE),  # Unix system file access
            re.compile(r"\/proc\/", re.IGNORECASE),  # Unix /proc access
            re.compile(r"C:\\Windows\\", re.IGNORECASE),  # Windows system access
        ]

        # Content security patterns
        self.content_security_patterns = SUSPICIOUS_CONTENT_PATTERNS

    # ========================================================================
    # Core Validation Methods
    # ========================================================================

    def validate_quality_assessment(
        self,
        content: str,
        source_path: str,
        language: Optional[str] = None,
        min_quality_threshold: float = 0.7,
    ) -> ValidationResult:
        """
        Validate quality assessment request inputs.

        Args:
            content: Source code content to analyze
            source_path: File path for context
            language: Programming language (auto-detected if None)
            min_quality_threshold: Minimum quality score (0.0-1.0)

        Returns:
            ValidationResult with validation status and sanitized data
        """
        errors = []
        warnings = []
        sanitized_data = {}

        # Validate content
        content_result = self.validate_content_security(content)
        if not content_result.valid:
            errors.extend(content_result.errors)
        warnings.extend(content_result.warnings)
        sanitized_data["content"] = content

        # Validate source path
        path_result = self.sanitize_source_path(source_path)
        if not path_result.valid:
            errors.extend(path_result.errors)
            warnings.extend(path_result.warnings)
            sanitized_data["source_path"] = source_path  # Use original on error
        else:
            warnings.extend(path_result.warnings)
            sanitized_data["source_path"] = path_result.sanitized_data.get(
                "source_path", source_path
            )

        # Validate language
        if language is not None:
            lang_result = self._validate_language(language)
            if not lang_result.valid:
                errors.extend(lang_result.errors)
            warnings.extend(lang_result.warnings)
            sanitized_data["language"] = language.lower()
        else:
            sanitized_data["language"] = None

        # Validate threshold
        if not (0.0 <= min_quality_threshold <= 1.0):
            errors.append(
                f"min_quality_threshold must be between 0.0 and 1.0, got: {min_quality_threshold}"
            )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            sanitized_data=sanitized_data if len(errors) == 0 else None,
        )

    def validate_performance_analysis(
        self,
        operation_name: str,
        code_content: str,
        context: Optional[Dict[str, Any]] = None,
        target_percentile: int = 95,
    ) -> ValidationResult:
        """
        Validate performance analysis request inputs.

        Args:
            operation_name: Operation identifier
            code_content: Code to analyze
            context: Execution context metadata
            target_percentile: Target performance percentile

        Returns:
            ValidationResult with validation status and sanitized data
        """
        errors = []
        warnings = []
        sanitized_data = {}

        # Validate operation name
        name_result = self._validate_identifier(operation_name, max_length=200)
        if not name_result.valid:
            errors.extend(name_result.errors)
        sanitized_data["operation_name"] = operation_name.strip()

        # Validate content
        content_result = self.validate_content_security(code_content)
        if not content_result.valid:
            errors.extend(content_result.errors)
        warnings.extend(content_result.warnings)
        sanitized_data["code_content"] = code_content

        # Validate context (optional)
        if context is not None:
            context_result = self._validate_json_safety(
                context, max_depth=5, max_keys=50
            )
            if not context_result.valid:
                errors.extend(context_result.errors)
        sanitized_data["context"] = context

        # Validate percentile
        if target_percentile not in [50, 90, 95, 99]:
            errors.append(
                f"target_percentile must be one of [50, 90, 95, 99], got: {target_percentile}"
            )
        sanitized_data["target_percentile"] = target_percentile

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            sanitized_data=sanitized_data if len(errors) == 0 else None,
        )

    def validate_pattern_detection(
        self,
        content: str,
        source_path: str,
        min_confidence: float = 0.7,
    ) -> ValidationResult:
        """
        Validate pattern detection request inputs.

        Args:
            content: Source code content to analyze
            source_path: File path for context
            min_confidence: Minimum confidence threshold

        Returns:
            ValidationResult with validation status and sanitized data
        """
        errors = []
        warnings = []
        sanitized_data = {}

        # Validate content
        content_result = self.validate_content_security(content)
        if not content_result.valid:
            errors.extend(content_result.errors)
        warnings.extend(content_result.warnings)
        sanitized_data["content"] = content

        # Validate source path
        path_result = self.sanitize_source_path(source_path)
        if not path_result.valid:
            errors.extend(path_result.errors)
            warnings.extend(path_result.warnings)
            sanitized_data["source_path"] = source_path  # Use original on error
        else:
            warnings.extend(path_result.warnings)
            sanitized_data["source_path"] = path_result.sanitized_data.get(
                "source_path", source_path
            )

        # Validate confidence
        if not (0.0 <= min_confidence <= 1.0):
            errors.append(
                f"min_confidence must be between 0.0 and 1.0, got: {min_confidence}"
            )
        sanitized_data["min_confidence"] = min_confidence

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            sanitized_data=sanitized_data if len(errors) == 0 else None,
        )

    # ========================================================================
    # Core Security Methods
    # ========================================================================

    def sanitize_source_path(self, path: str) -> ValidationResult:
        """
        Sanitize and validate source path.

        Prevents:
        - Path traversal attacks (../)
        - Absolute paths outside allowed directories
        - Null bytes and control characters
        - Overly long paths

        Args:
            path: File path to validate and sanitize

        Returns:
            ValidationResult with sanitized path
        """
        errors = []
        warnings = []

        # Null safety
        if path is None or not isinstance(path, str):
            errors.append("source_path must be a non-null string")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Empty check
        if not path.strip():
            errors.append("source_path cannot be empty")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Length check
        if len(path) > MAX_PATH_LENGTH:
            errors.append(
                f"source_path too long (max {MAX_PATH_LENGTH} chars): {len(path)} chars"
            )

        # Remove null bytes
        if "\x00" in path:
            errors.append("source_path contains null bytes")
            path = path.replace("\x00", "")

        # Check for path traversal patterns
        for pattern in self.path_traversal_patterns:
            if pattern.search(path):
                errors.append(
                    f"source_path contains suspicious pattern: {pattern.pattern}"
                )

        # Normalize path
        try:
            normalized_path = os.path.normpath(path)

            # Check if absolute path is within allowed base paths
            if os.path.isabs(normalized_path):
                is_allowed = any(
                    normalized_path.startswith(os.path.abspath(base_path))
                    for base_path in self.allowed_base_paths
                )
                if not is_allowed:
                    errors.append(
                        f"Absolute path outside allowed directories: {normalized_path}"
                    )
            else:
                # Relative path - check for traversal
                if normalized_path.startswith(".."):
                    errors.append(f"Path traversal detected: {normalized_path}")

        except (ValueError, TypeError) as e:
            errors.append(f"Invalid path format: {str(e)}")
            normalized_path = path

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            sanitized_data=(
                {"source_path": normalized_path} if len(errors) == 0 else None
            ),
        )

    def validate_content_security(self, content: str) -> ValidationResult:
        """
        Validate content for security issues.

        Checks:
        - Size limits (10MB max)
        - Encoding (UTF-8)
        - Null bytes
        - Suspicious patterns (logged as warnings, not blocking)

        Args:
            content: Content to validate

        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []

        # Null safety
        if content is None or not isinstance(content, str):
            errors.append("content must be a non-null string")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Empty check (allowed but warn)
        if not content.strip():
            warnings.append("content is empty")
            return ValidationResult(
                valid=True,
                errors=errors,
                warnings=warnings,
                sanitized_data={"content": content},
            )

        # Size check (10MB limit)
        content_size = len(content.encode("utf-8"))
        if content_size > MAX_CONTENT_SIZE_BYTES:
            errors.append(
                f"content too large: {content_size} bytes (max {MAX_CONTENT_SIZE_BYTES} bytes / 10MB)"
            )

        # Encoding validation (must be valid UTF-8)
        try:
            content.encode("utf-8")
        except UnicodeEncodeError as e:
            errors.append(f"content contains invalid UTF-8: {str(e)}")

        # Null byte check
        if "\x00" in content:
            errors.append("content contains null bytes")

        # Suspicious pattern detection (warnings only, not blocking)
        for pattern in self.content_security_patterns:
            if pattern.search(content):
                warnings.append(
                    f"Suspicious pattern detected: {pattern.pattern} - verify context is safe"
                )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            sanitized_data={"content": content} if len(errors) == 0 else None,
        )

    def check_operation_allowed(
        self, operation_type: EnumIntelligenceOperationType
    ) -> ValidationResult:
        """
        Check if operation type is allowed.

        Currently all intelligence operation types are allowed,
        but this method provides extension point for:
        - Rate limiting per operation type
        - Permission-based access control
        - Feature flags for beta operations

        Args:
            operation_type: Intelligence operation type

        Returns:
            ValidationResult indicating if operation is allowed
        """
        errors = []
        warnings = []

        # Validate enum - must be an Enum instance and member of EnumIntelligenceOperationType
        # Note: isinstance(enum_member, EnumClass) doesn't work for str-based enums
        # so we check if it's an Enum and if it's in the enum members
        if not isinstance(operation_type, Enum):
            errors.append(
                f"Invalid operation_type: must be EnumIntelligenceOperationType, got {type(operation_type)}"
            )
        elif operation_type not in EnumIntelligenceOperationType:
            errors.append(
                f"Invalid operation_type: must be a member of EnumIntelligenceOperationType, got {operation_type}"
            )

        # All operations currently allowed (extension point for future restrictions)
        if len(errors) == 0:
            allowed_operations = set(EnumIntelligenceOperationType)
            if operation_type not in allowed_operations:
                errors.append(f"Operation not allowed: {operation_type}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            sanitized_data=(
                {"operation_type": operation_type} if len(errors) == 0 else None
            ),
        )

    # ========================================================================
    # Helper Validation Methods
    # ========================================================================

    def _validate_language(self, language: str) -> ValidationResult:
        """
        Validate programming language.

        Args:
            language: Programming language identifier

        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []

        if not isinstance(language, str):
            errors.append(f"language must be a string, got {type(language)}")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        language_lower = language.lower().strip()

        if language_lower not in ALLOWED_LANGUAGES:
            warnings.append(
                f"Unrecognized language: {language} (will attempt auto-detection)"
            )

        return ValidationResult(
            valid=True,  # Non-blocking, auto-detection will handle
            errors=errors,
            warnings=warnings,
            sanitized_data={"language": language_lower},
        )

    def _validate_identifier(
        self, value: str, max_length: int = 100
    ) -> ValidationResult:
        """
        Validate identifier (alphanumeric + underscore + hyphen).

        Args:
            value: Identifier to validate
            max_length: Maximum allowed length

        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []

        if value is None or not isinstance(value, str):
            errors.append("Identifier must be a non-null string")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        if not value.strip():
            errors.append("Identifier cannot be empty")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        if len(value) > max_length:
            errors.append(
                f"Identifier too long (max {max_length} chars): {len(value)} chars"
            )

        # Allow alphanumeric, underscore, hyphen, and forward slash (for paths in operation names)
        if not re.match(r"^[a-zA-Z0-9_\-\/]+$", value):
            errors.append(
                "Identifier contains invalid characters (allowed: alphanumeric, _, -, /)"
            )

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_json_safety(
        self, value: Dict[str, Any], max_depth: int = 10, max_keys: int = 100
    ) -> ValidationResult:
        """
        Validate JSON structure safety (based on omninode_bridge sanitize_json).

        Args:
            value: Dictionary to validate
            max_depth: Maximum nesting depth
            max_keys: Maximum total keys

        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []

        if value is None or not isinstance(value, dict):
            errors.append("Value must be a non-null dictionary")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        def count_keys(obj: Any, depth: int = 0) -> int:
            if depth > max_depth:
                raise ValueError(f"JSON too deeply nested (max depth: {max_depth})")

            if isinstance(obj, dict):
                count = len(obj)
                for v in obj.values():
                    if v is not None:
                        count += count_keys(v, depth + 1)
                return count
            elif isinstance(obj, list):
                count = 0
                for item in obj:
                    if item is not None:
                        count += count_keys(item, depth + 1)
                return count
            return 0

        try:
            total_keys = count_keys(value)
            if total_keys > max_keys:
                errors.append(
                    f"Too many keys in JSON (max {max_keys}): {total_keys} keys"
                )
        except ValueError as e:
            errors.append(str(e))

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings
        )
