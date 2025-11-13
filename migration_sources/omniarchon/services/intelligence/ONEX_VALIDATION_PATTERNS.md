# ONEX Validation Patterns - From omnibase_core Pre-Commit

**Source**: `/Volumes/PRO-G40/Code/omnibase_core/scripts/validation/`
**Date**: 2025-10-14
**Purpose**: Authoritative ONEX patterns enforced in production via pre-commit hooks

---

## 1. Naming Conventions ✅

**Source**: `validate_naming.py`

### Models
- **Pattern**: `^Model[A-Z][A-Za-z0-9]*$`
- **Examples**: `ModelUserAuth`, `ModelErrorContext`, `ModelONEXContainer`
- **File**: `model_*.py`
- **Directory**: `models/`

### Protocols
- **Pattern**: `^Protocol[A-Z][A-Za-z0-9]*$`
- **Examples**: `ProtocolEventBus`, `ProtocolToolBase`
- **File**: `protocol_*.py`
- **Directory**: `protocol/`

### Enums
- **Pattern**: `^Enum[A-Z][A-Za-z0-9]*$`
- **Examples**: `EnumWorkflowType`, `EnumCoreErrorCode`
- **File**: `enum_*.py`
- **Directory**: `enums/`

### Services
- **Pattern**: `^Service[A-Z][A-Za-z0-9]*$`
- **Examples**: `ServiceAuth`, `ServiceUserData`
- **File**: `service_*.py`
- **Directory**: `services/`

### Mixins
- **Pattern**: `^Mixin[A-Z][A-Za-z0-9]*$`
- **Examples**: `MixinHealthCheck`, `MixinLogging`
- **File**: `mixin_*.py`
- **Directory**: `mixins/`

### Nodes
- **Pattern**: `^Node[A-Z][A-Za-z0-9]*$`
- **Examples**: `NodeEffectUserData`, `NodeComputeAnalysis`, `NodeTransform`
- **File**: `node_*.py`
- **Directory**: `nodes/`

### TypedDicts
- **Pattern**: `^TypedDict[A-Z][A-Za-z0-9]*$`
- **Examples**: `TypedDictUserParams`, `TypedDictConfig`
- **File**: Any `.py` file
- **Directory**: Any

---

## 2. Import Patterns ❌

**Source**: `validate-import-patterns.py`

### FORBIDDEN
```python
# Multi-level relative imports
from ..parent import Something  # ❌
from ...grandparent import Something  # ❌
from ....greatgrandparent import Something  # ❌
```

### ALLOWED
```python
# Absolute imports
from omnibase_core.enums.enum_type import EnumType  # ✅

# Sibling imports only
from .model_sibling import ModelSibling  # ✅
```

---

## 3. Type Safety: dict[str, Any] ❌

**Source**: `validate-dict-any-usage.py`

### FORBIDDEN
```python
# Defeats strong typing
metadata: dict[str, Any]  # ❌
data: dict[str, Any]  # ❌
```

### ALLOWED (with justification only)
```python
@allow_dict_any  # Only with explicit decorator
def legacy_handler(data: dict[str, Any]):  # ✅ (exception)
    pass
```

### RECOMMENDED ALTERNATIVES
```python
# 1. Specific typed models
metadata: ModelMetadata  # ✅

# 2. TypedDict for structured dictionaries
class TypedDictUserMeta(TypedDict):  # ✅
    user_id: str
    email: str

# 3. Union types for mixed values
metadata: dict[str, str | int | bool]  # ✅
```

---

## 4. Pydantic v2 Compliance ❌

**Source**: `validate-pydantic-patterns.py`

### CRITICAL ERRORS (Auto-Reject)

#### .dict() → .model_dump()
```python
# Legacy v1 (FORBIDDEN)
data = user.dict()  # ❌
data = user.dict(exclude_none=True)  # ❌
data = user.dict(exclude_unset=True)  # ❌
data = user.dict(by_alias=True)  # ❌
data = user.dict(exclude={'password'})  # ❌
data = user.dict(include={'id', 'email'})  # ❌

# Modern v2 (REQUIRED)
data = user.model_dump()  # ✅
data = user.model_dump(exclude_none=True)  # ✅
data = user.model_dump(exclude_unset=True)  # ✅
data = user.model_dump(by_alias=True)  # ✅
data = user.model_dump(exclude={'password'})  # ✅
data = user.model_dump(include={'id', 'email'})  # ✅
```

#### .json() → .model_dump_json()
```python
# Legacy v1 (FORBIDDEN)
json_str = user.json()  # ❌
json_str = user.json(exclude_none=True)  # ❌
json_str = user.json(by_alias=True)  # ❌

# Modern v2 (REQUIRED)
json_str = user.model_dump_json()  # ✅
json_str = user.model_dump_json(exclude_none=True)  # ✅
json_str = user.model_dump_json(by_alias=True)  # ✅
```

#### .copy() → .model_copy()
```python
# Legacy v1 (FORBIDDEN)
updated = user.copy(update={'email': 'new@example.com'})  # ❌
deep = user.copy(deep=True)  # ❌

# Modern v2 (REQUIRED)
updated = user.model_copy(update={'email': 'new@example.com'})  # ✅
deep = user.model_copy(deep=True)  # ✅
```

### WARNINGS (Deprecated but not critical)

#### Schema Methods
```python
# Legacy v1 (DEPRECATED)
schema = User.schema()  # ⚠️
schema_json = User.schema_json()  # ⚠️

# Modern v2 (RECOMMENDED)
schema = User.model_json_schema()  # ✅
```

#### Config → model_config
```python
# Legacy v1 (DEPRECATED)
class User(BaseModel):  # ⚠️
    class Config:
        arbitrary_types_allowed = True

# Modern v2 (RECOMMENDED)
class User(BaseModel):  # ✅
    model_config = ConfigDict(arbitrary_types_allowed=True)
```

#### Validators
```python
# Legacy v1 (DEPRECATED)
@validator('email')  # ⚠️
@root_validator  # ⚠️

# Modern v2 (RECOMMENDED)
@field_validator('email')  # ✅
@model_validator  # ✅
```

---

## 5. Exception Handling: OnexError ❌

**Source**: `validate-onex-error-compliance.py`

### FORBIDDEN Standard Exceptions
```python
# All standard Python exceptions are FORBIDDEN
raise ValueError("Invalid value")  # ❌
raise TypeError("Wrong type")  # ❌
raise RuntimeError("Runtime error")  # ❌
raise KeyError("Missing key")  # ❌
raise AttributeError("Missing attribute")  # ❌
raise IndexError("Index out of range")  # ❌
raise FileNotFoundError("File not found")  # ❌
raise PermissionError("Permission denied")  # ❌
raise ImportError("Import failed")  # ❌
raise ModuleNotFoundError("Module not found")  # ❌
raise NotImplementedError("Not implemented")  # ❌
raise OSError("OS error")  # ❌
raise IOError("IO error")  # ❌
raise ConnectionError("Connection failed")  # ❌
raise TimeoutError("Timeout")  # ❌
raise JSONDecodeError("JSON decode error")  # ❌
raise ConfigurationError("Configuration error")  # ❌
```

### REQUIRED Pattern
```python
from omnibase_core.exceptions.onex_error import OnexError
from omnibase_core.enums.enum_core_error_code import EnumCoreErrorCode
from omnibase_core.models.common.model_error_context import ModelErrorContext

# Proper ONEX error handling
raise OnexError(  # ✅
    code=EnumCoreErrorCode.VALIDATION_ERROR,
    message='Invalid input value',
    details=ModelErrorContext.with_context({'input': value})
)

raise OnexError(  # ✅
    code=EnumCoreErrorCode.EXECUTION_FAILED,
    message='Operation failed',
    details=ModelErrorContext.with_context({
        'operation': 'process_data',
        'timestamp': datetime.now()
    })
)
```

### Benefits of OnexError
- ✅ Consistent error handling across ONEX framework
- ✅ Structured error codes for programmatic handling
- ✅ Rich error context for debugging
- ✅ Standardized error reporting and logging
- ✅ Proper error chaining and traceability

---

## 6. Additional Validation Rules

### From `.pre-commit-config.yaml`:

1. **String Version Anti-Patterns** (`validate-string-versions.py`)
   - Enforce semantic versioning standards

2. **Archived Imports Prevention** (`validate-archived-imports.py`)
   - Prevent imports from `/archived/` or `/archive/` directories

3. **Backward Compatibility Anti-Patterns** (`validate-no-backward-compatibility.py`)
   - Prevent legacy compatibility code

4. **Manual YAML Prevention** (`validate-no-manual-yaml.py`)
   - Prevent hand-written YAML (should be contract-generated)

5. **Union Usage** (`validate-union-usage.py`)
   - Enforce proper Union type usage
   - Allowed: 8 invalid cases (technical debt)

6. **Contract Validation** (`validate-contracts.py`)
   - Validate contract-driven architecture compliance

7. **Optional Type Usage Audit** (`audit_optional.py`)
   - Track Optional type usage

8. **Stub Implementation Detection** (`check_stub_implementations.py`)
   - Detect incomplete/stubbed functionality

9. **No Fallback Patterns** (`check_no_fallbacks.py`)
   - Prevent defensive fallback code

10. **Error Raising Validation** (`check_error_raising.py`)
    - Validate proper error raising patterns

11. **Enhancement Prefix Anti-Patterns** (`validate-no-enhancement-prefixes.py`)
    - Prevent "enhanced_" or "new_" prefixes

---

## Quality Scorer Implications

### Current Coverage
My quality scorer currently detects:
- ✅ Any type usage (aligns with dict[str, Any] validation)
- ✅ Non-CamelCase Pydantic models (aligns with naming conventions)
- ✅ Direct service instantiation
- ✅ Modern ONEX patterns (partial)

### Missing Patterns (Need to Add)
- ❌ Legacy Pydantic v1 methods (`.dict()`, `.json()`, `.copy()`, `.schema()`)
- ❌ Standard Python exception usage
- ❌ Multi-level relative imports
- ❌ `dict[str, Any]` detection
- ❌ Naming convention validation (Model*, Protocol*, Enum*, etc.)
- ❌ Legacy validators (`@validator`, `@root_validator`)

### Recommendations
1. **Add critical legacy pattern detection**:
   - Pydantic v1 methods
   - Standard exceptions
   - dict[str, Any]

2. **Add naming convention validation**:
   - Model*, Protocol*, Enum*, Service*, Mixin*, Node* patterns

3. **Add import pattern validation**:
   - Detect multi-level relative imports

4. **Severity classification**:
   - **Critical (score = 0.0)**: dict[str, Any], Any types, .dict(), standard exceptions
   - **High (score = 0.3)**: Legacy validators, Config class, .schema()
   - **Medium (score = 0.6)**: Non-standard naming, relative imports
   - **Low (score = 0.8)**: Missing docstrings, minor style issues

---

## Testing Against Real Validation

### Validation Command
```bash
# Run actual omnibase_core validations
cd /Volumes/PRO-G40/Code/omnibase_core

# Pydantic patterns
poetry run python scripts/validation/validate-pydantic-patterns.py

# Dict[str, Any] usage
poetry run python scripts/validation/validate-dict-any-usage.py

# OnexError compliance
poetry run python scripts/validation/validate-onex-error-compliance.py src/

# Naming conventions
poetry run python scripts/validation/validate_naming.py .

# Import patterns
poetry run python scripts/validation/validate-import-patterns.py src/
```

### Pre-commit Full Validation
```bash
cd /Volumes/PRO-G40/Code/omnibase_core
poetry run pre-commit run --all-files
```

---

## Summary

**Enforced by Pre-Commit**: 15+ validation scripts
**Critical Patterns**: 5 categories (Naming, Imports, Types, Pydantic, Exceptions)
**Total Rules**: 50+ specific patterns
**Compliance Level**: Zero tolerance for critical patterns

**Quality Scorer Coverage**: ~40% (needs expansion)
**Recommended Updates**: Add all critical legacy patterns to scorer
