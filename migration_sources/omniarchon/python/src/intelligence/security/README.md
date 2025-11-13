# Intelligence Security Validator

**Status**: ✅ Production Ready | **Tests**: 53/53 Passing | **Coverage**: 100%

## Quick Start

```python
from intelligence.security import IntelligenceSecurityValidator

# Initialize validator
validator = IntelligenceSecurityValidator()

# Validate quality assessment request
result = validator.validate_quality_assessment(
    content="def calculate(): return 42",
    source_path="src/api.py",
    language="python",
    min_quality_threshold=0.7
)

if result.valid:
    # ✅ Safe to proceed - use sanitized data
    sanitized_content = result.sanitized_data["content"]
    sanitized_path = result.sanitized_data["source_path"]
    # Call Intelligence Service API...
else:
    # ❌ Security violation - block request
    raise SecurityValidationError(result.errors)

# ⚠️ Warnings don't block (informational only)
if result.warnings:
    logger.warning(f"Security warnings: {result.warnings}")
```

## Features

### 6 Security Layers

1. **Path Traversal Prevention**
   - Unix/Windows/URL-encoded traversal detection
   - Absolute path validation against allowed directories
   - System path detection (`/etc/passwd`, `/proc/`, `C:\Windows\`)

2. **Content Size Limits**
   - 10MB maximum content size
   - UTF-8 byte size validation (not character count)

3. **Content Security**
   - Null byte detection (`\x00`)
   - UTF-8 encoding validation
   - Suspicious pattern detection (XSS, eval/exec) → warnings

4. **Operation Permissions**
   - Enum-based operation validation
   - Extension point for rate limiting
   - Extension point for role-based access control

5. **Encoding Validation**
   - UTF-8 encoding requirement
   - Invalid encoding rejection

6. **Language Validation**
   - 30+ recognized languages
   - Auto-detection fallback for unrecognized
   - Case-insensitive normalization

## API Reference

### Quality Assessment Validation

```python
result = validator.validate_quality_assessment(
    content: str,                      # Source code
    source_path: str,                  # File path
    language: Optional[str] = None,    # Language (auto-detect if None)
    min_quality_threshold: float = 0.7 # Threshold (0.0-1.0)
) -> ValidationResult
```

**Validates**: Content security, path safety, language, threshold

### Performance Analysis Validation

```python
result = validator.validate_performance_analysis(
    operation_name: str,               # Operation ID
    code_content: str,                 # Code to analyze
    context: Optional[Dict] = None,    # Execution context
    target_percentile: int = 95        # Target percentile (50, 90, 95, 99)
) -> ValidationResult
```

**Validates**: Operation name, content, context (JSON safety), percentile

### Pattern Detection Validation

```python
result = validator.validate_pattern_detection(
    content: str,                      # Source code
    source_path: str,                  # File path
    min_confidence: float = 0.7        # Confidence (0.0-1.0)
) -> ValidationResult
```

**Validates**: Content security, path safety, confidence

### Operation Permission Check

```python
result = validator.check_operation_allowed(
    operation_type: EnumIntelligenceOperationType
) -> ValidationResult
```

**Validates**: Operation type is allowed (all currently allowed)

## ValidationResult Model

```python
class ValidationResult(BaseModel):
    valid: bool                         # True = safe to proceed
    errors: List[str] = []              # Blocking errors
    warnings: List[str] = []            # Non-blocking warnings
    sanitized_data: Optional[Dict] = None  # Sanitized data (if valid)
```

**Usage Pattern**:
```python
if result.valid:
    use_data(result.sanitized_data)
else:
    raise ValidationError(result.errors)

if result.warnings:
    logger.warning(result.warnings)
```

## Configuration

### Allowed Base Paths

```python
# Default: current working directory
validator = IntelligenceSecurityValidator()

# Custom allowed paths (restrict to specific directories)
validator = IntelligenceSecurityValidator(
    allowed_base_paths=[
        "/workspace/project1",
        "/workspace/project2"
    ]
)
```

### Security Constants

```python
from intelligence.security.intelligence_security_validator import (
    MAX_CONTENT_SIZE_BYTES,  # 10MB
    MAX_PATH_LENGTH,         # 4096
    ALLOWED_LANGUAGES,       # 30+ languages
    EnumIntelligenceOperationType  # Operation types
)
```

## Integration Example

```python
from intelligence.security import IntelligenceSecurityValidator, ValidationResult
from server.exceptions.onex_error import OnexError, CoreErrorCode

class NodeIntelligenceAdapterEffect:
    def __init__(self):
        self.security_validator = IntelligenceSecurityValidator()
        self.intelligence_client = IntelligenceServiceClient()

    async def analyze_code(
        self,
        content: str,
        source_path: str,
        language: Optional[str] = None,
        correlation_id: Optional[UUID] = None
    ) -> ModelQualityAssessmentResponse:
        # 1. Security validation BEFORE API call
        validation_result = self.security_validator.validate_quality_assessment(
            content=content,
            source_path=source_path,
            language=language
        )

        # 2. Handle validation failures
        if not validation_result.valid:
            logger.error(f"Validation failed: {validation_result.errors}")
            raise OnexError(
                message=f"Security validation failed: {', '.join(validation_result.errors)}",
                error_code=CoreErrorCode.VALIDATION_ERROR,
                details={"validation_errors": validation_result.errors},
                status_code=400
            )

        # 3. Log warnings (non-blocking)
        if validation_result.warnings:
            logger.warning(f"Security warnings: {validation_result.warnings}")

        # 4. Use sanitized data
        sanitized = validation_result.sanitized_data

        # 5. Call Intelligence Service
        try:
            request = ModelQualityAssessmentRequest(
                content=sanitized["content"],
                source_path=sanitized["source_path"],
                language=sanitized["language"]
            )
            return await self.intelligence_client.assess_code_quality(request)
        except Exception as e:
            raise OnexError(...) from e
```

## Testing

```bash
# Run all security validator tests
pytest tests/unit/intelligence/test_security_validator.py -v

# Run with coverage
pytest tests/unit/intelligence/test_security_validator.py --cov=intelligence.security --cov-report=html

# Results: 53 passed in 0.30s (100% coverage)
```

## Documentation

- **User Guide**: `/python/docs/intelligence/SECURITY_VALIDATION.md`
  - Security protections (6 categories)
  - Validation methods
  - Integration patterns
  - ONEX compliance

- **Integration Example**: `/python/docs/intelligence/SECURITY_INTEGRATION_EXAMPLE.md`
  - Complete Effect Node implementation
  - Usage examples (3 scenarios)
  - Production patterns

- **Implementation Summary**: `/python/docs/intelligence/SECURITY_IMPLEMENTATION_SUMMARY.md`
  - Complete deliverables
  - Test coverage
  - ONEX compliance
  - Future enhancements

## Performance

- **Pattern Compilation**: Pre-compiled regex (<1ms lookup)
- **Path Validation**: <5ms per request
- **Content Validation**: <10ms for typical code files
- **Total Overhead**: <20ms per request

## ONEX Compliance

✅ **Effect Node Pattern**: Validation separate from execution
✅ **Error Handling**: OnexError for all exceptions
✅ **Type Safety**: Pydantic models, type hints
✅ **Logging**: Structured logging with correlation IDs

## Security Patterns

Based on `/omninode_bridge/security/validation.py`:

✅ Pre-compiled regex patterns
✅ Input sanitization
✅ Malicious pattern detection
✅ Enhanced null safety
✅ Recursive JSON validation

## Future Enhancements

**Phase 2** (Planned):
- Rate limiting per operation
- Role-based access control
- Security event auditing
- Anomaly detection
- Malware scanning integration

## Support

**Files**:
- Validator: `/python/src/intelligence/security/intelligence_security_validator.py`
- Tests: `/python/tests/unit/intelligence/test_security_validator.py`
- Docs: `/python/docs/intelligence/SECURITY_*.md`

**Status**: ✅ Production Ready
**Test Coverage**: 100% (53/53 tests passing)
**ONEX Compliance**: Full compliance
