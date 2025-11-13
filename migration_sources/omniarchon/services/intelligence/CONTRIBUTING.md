# Contributing to Archon Intelligence Service

## Code Style and Conventions

### Import Standards

This project follows a consistent import pattern to ensure clean, maintainable code. All imports must follow these conventions:

#### 1. Package Re-exports Pattern

All packages should re-export their public API through `__init__.py` files with explicit `__all__` definitions.

**Example** (`src/services/quality/__init__.py`):
```python
"""Quality assessment services for code generation intelligence."""

from .onex_quality_scorer import ONEXQualityScorer
from .comprehensive_onex_scorer import ComprehensiveONEXScorer
from .codegen_quality_service import CodegenQualityService

__all__ = [
    "ONEXQualityScorer",
    "ComprehensiveONEXScorer",
    "CodegenQualityService",
]
```

#### 2. Service/Handler Implementations

Always import from package `__init__.py`, never from direct modules.

**✅ Good**:
```python
from src.services.quality import CodegenQualityService, ComprehensiveONEXScorer
from src.services.langextract import CodegenLangExtractService
```

**❌ Bad**:
```python
from src.services.quality.codegen_quality_service import CodegenQualityService
from src.services.langextract.codegen_langextract_service import CodegenLangExtractService
```

#### 3. Test Imports

Tests should use package imports with `src.` prefix:

**✅ Good**:
```python
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from src.handlers import CodegenAnalysisHandler
from src.services.langextract import CodegenLangExtractService
```

**❌ Bad**:
```python
from handlers.codegen_analysis_handler import CodegenAnalysisHandler
from src.services.langextract.codegen_langextract_service import CodegenLangExtractService
```

#### 4. Internal Package Imports

Within a package, use relative imports:

**✅ Good** (within `src/services/langextract/`):
```python
from ..pattern_learning.phase2_matching.client_langextract_http import ClientLangextractHttp
```

**❌ Bad**:
```python
from src.services.pattern_learning.phase2_matching.client_langextract_http import ClientLangextractHttp
```

#### 5. Lazy Imports for Circular Dependencies

For packages with circular dependencies (like handlers), use lazy imports via `__getattr__`:

**Example** (`src/handlers/__init__.py`):
```python
"""Event handlers for intelligence services."""

from .base_response_publisher import BaseResponsePublisher

__all__ = [
    "BaseResponsePublisher",
    "CodegenValidationHandler",
    "CodegenAnalysisHandler",
]

def __getattr__(name):
    """Lazy import handlers to avoid dependency issues."""
    if name == "CodegenValidationHandler":
        from .codegen_validation_handler import CodegenValidationHandler
        return CodegenValidationHandler
    # ... other handlers
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Benefits of This Pattern

1. **Single Source of Truth**: Package `__init__.py` defines what's public via `__all__`
2. **Easier Refactoring**: Only update `__init__.py` when moving modules
3. **Cleaner Imports**: Less boilerplate in import statements
4. **Better IDE Support**: Clearer public API for autocomplete
5. **isinstance() Compatible**: Importing same class instance ensures isinstance checks work

### Running Tests

Tests must be run from the `services/intelligence` directory (not from `tests/`):

```bash
# From services/intelligence directory
poetry run python -m pytest tests/unit/test_codegen_analysis_handler.py -v

# Run all handler tests
poetry run python -m pytest tests/unit/ -v

# Run specific test
poetry run python -m pytest tests/unit/test_codegen_analysis_handler.py::TestCodegenAnalysisHandler::test_can_handle_valid_event_types -v
```

### Pre-commit Checklist

Before committing code changes:

1. **Verify imports follow conventions** - Check for direct module imports
2. **Update `__init__.py`** - If adding new public modules, add re-exports
3. **Run tests** - Ensure all tests pass from correct directory
4. **Check isinstance usage** - Verify type checks work with import pattern

### Common Issues

#### Issue: "ModuleNotFoundError: No module named 'src'"

**Solution**: Run pytest from `services/intelligence` directory, not `tests/` directory.

```bash
# Wrong (from tests/)
cd tests && poetry run pytest unit/test_file.py  # ❌

# Correct (from services/intelligence/)
cd services/intelligence && poetry run python -m pytest tests/unit/test_file.py  # ✅
```

#### Issue: isinstance() checks failing

**Solution**: Ensure both locations import from the same package `__init__.py`:

```python
# Both should use:
from src.services.quality import CodegenQualityService

# Not mix:
from src.services.quality import CodegenQualityService  # Location 1
from src.services.quality.codegen_quality_service import CodegenQualityService  # Location 2 ❌
```

## Code Review Guidelines

When reviewing pull requests, check for:

- [ ] All imports follow package re-export pattern
- [ ] No direct module imports (except for internal package imports)
- [ ] Test imports use `src.` prefix
- [ ] Internal package imports use relative imports
- [ ] New modules added to appropriate `__init__.py` with `__all__` export
- [ ] Tests run from correct directory and pass
- [ ] isinstance() checks work correctly

## Additional Resources

- [Python Import System](https://docs.python.org/3/reference/import.html)
- [Python Packaging Guide](https://packaging.python.org/en/latest/)
- [PEP 8 Style Guide](https://peps.python.org/pep-0008/)
