---
name: "Test Suite Refactoring - Reduce Large Test Files to <15KB"
description: "Systematic refactoring of 31 large test files (>15KB) by extracting fixtures, utilities, and helper classes"
---

## Original Story

```
Refactor large test files (>10KB) in python/tests/.

**Files to refactor (30+ files):**
- test_rag_strategies.py (20KB)
- test_search_performance.py (29KB)
- test_menu_handler.py (21KB)
- test_async_embedding_service.py (22KB)
- test_rag_integration.py (25KB)
- test_menu_integration.py (22KB)
- test_async_credential_service.py (18KB)
- test_kafka_consumer.py (12KB)
- test_menu_poc.py (26KB)
- test_mcp_client_endpoints.py (15KB)
- test_pre_push_intelligence.py (19KB)
- test_coverage_optimization.py (44KB)
- test_async_background_task_manager.py (18KB)
- test_async_source_summary.py (20KB)
- test_async_llm_provider_service.py (20KB)
- test_cache_management.py (18KB)
- test_unified_menu.py (12KB)
- test_crawl_orchestration_isolated.py (18KB)
- And others in subdirectories

**Task:**
1. Identify test files >15KB
2. Extract test utilities, fixtures, and helper functions to separate modules
3. Group related test classes
4. Create conftest.py files for shared fixtures
5. Target: Reduce each test file to <15KB

**Return:** Summary of refactored test files with new structure.
```

## Story Metadata

**Story Type**: Refactor
**Estimated Complexity**: High
**Primary Systems Affected**: Test Suite (python/tests/)

---

## CONTEXT REFERENCES

### Codebase Analysis Results

**Total Files Identified**: 31 test files > 15KB (~1.2MB total)

**Distribution**:
- Root `/python/tests/`: 18 files (largest: 43KB)
- `/auth/`: 3 files (largest: 59KB - test_auth_security_owasp.py)
- `/integration/`: 3 files (max: 27KB)
- `/performance/`: 2 files (max: 37KB)
- `/unit/`: 3 files (max: 28KB)
- `/mcp_server/modules/`: 2 files (max: 19KB)

**Key Patterns Identified**:
1. **106 inline fixtures** scattered across test files (should be in conftest.py)
2. **85+ mock/setup helper functions** duplicated across files
3. **10+ utility classes** embedded in test files (Analyzers, Managers, Builders)
4. **Common test data patterns** repeated across tests
5. **Performance test utilities** (orchestrators, cache clients, metrics)

**Existing Infrastructure**:
- `/python/tests/conftest.py` - Main test configuration with environment setup
- `/python/tests/fixtures/intelligence_documents.py` - Intelligence test data
- `/python/tests/fixtures/correlation_test_data.py` - Correlation algorithm test data

---

## IMPLEMENTATION TASKS

### Phase 1: Create Shared Test Utilities Infrastructure

### CREATE python/tests/utils/__init__.py:

- IMPLEMENT: Test utilities package initialization
- PATTERN: Standard Python package structure
- IMPORTS: None (package marker)
- CONTENT: Empty file to make directory a package
- **VALIDATE**: `ls -la python/tests/utils/__init__.py`

### CREATE python/tests/utils/mock_helpers.py:

- IMPLEMENT: Centralized mock creation utilities
- EXTRACT: Common mock patterns from test files:
  - `create_mock_database_client()` - Supabase mock with method chaining
  - `create_mock_embedding_service()` - Embedding API mock
  - `create_mock_rag_service()` - RAG service mock
  - `create_mock_credential_service()` - Credential service mock
  - `AsyncContextManager` - Reusable async context manager class
  - `create_mock_httpx_client()` - HTTP client mock with connection pooling
- PATTERN: Follow existing mock patterns in conftest.py (lines 50-93)
- IMPORTS: `from unittest.mock import MagicMock, AsyncMock, patch`
- GOTCHA: Ensure method chaining works for Supabase-style APIs (.table().select().eq().execute())
- **VALIDATE**: `python -c "from tests.utils.mock_helpers import create_mock_database_client; print('✓ Mock helpers import successful')"`

### CREATE python/tests/utils/test_builders.py:

- IMPLEMENT: Test data builder utilities
- EXTRACT: Common test data patterns:
  - `TestDataBuilder` class with fluent interface
  - `build_test_project(overrides={})` - Project test data
  - `build_test_task(overrides={})` - Task test data
  - `build_test_knowledge_item(overrides={})` - Knowledge item test data
  - `build_test_user(overrides={})` - User test data
  - `build_test_document(overrides={})` - Document test data
- PATTERN: Builder pattern with sensible defaults and override support
- IMPORTS: `from typing import Dict, Any, Optional`
- GOTCHA: Ensure builders return deep copies to avoid test interference
- **VALIDATE**: `python -c "from tests.utils.test_builders import build_test_project; print('✓ Test builders import successful')"`

### CREATE python/tests/utils/performance_helpers.py:

- IMPLEMENT: Performance testing utilities
- EXTRACT: Performance test patterns from test_search_performance.py and test_coverage_optimization.py:
  - `PerformanceMetrics` dataclass (duration, memory, cpu)
  - `measure_performance(func)` decorator
  - `benchmark_async(func, iterations=10)` async function
  - `assert_performance_threshold(duration_ms, threshold_ms, label)`
  - `create_performance_report(metrics_list)` - Generate performance summary
- PATTERN: Follow pytest benchmark patterns with async support
- IMPORTS: `import time, asyncio, psutil; from dataclasses import dataclass; from typing import Callable, List, Dict, Any`
- GOTCHA: Use `time.perf_counter()` for accurate timing, not `time.time()`
- **VALIDATE**: `python -c "from tests.utils.performance_helpers import measure_performance; print('✓ Performance helpers import successful')"`

### CREATE python/tests/utils/analysis_helpers.py:

- IMPLEMENT: Test analysis and coverage utilities
- EXTRACT: Helper classes from test_coverage_optimization.py:
  - `TestCategoryAnalyzer` class (categorize_test, is_parallelizable, estimate_duration)
  - `TestFileAnalyzer` class (analyze_test_file, extract AST info)
  - `TestExecutionOptimizer` class (discover_tests, create_execution_plan, optimize_for_speed)
  - `TestCoverageAnalyzer` class (analyze_component_coverage, generate_coverage_report)
- PATTERN: Follow existing class structure in test_coverage_optimization.py (lines 67-674)
- IMPORTS: `import ast, os, subprocess; from pathlib import Path; from typing import Dict, List, Any; from collections import defaultdict`
- GOTCHA: These classes are used by test_coverage_optimization.py, ensure backward compatibility
- **VALIDATE**: `python -c "from tests.utils.analysis_helpers import TestCategoryAnalyzer; print('✓ Analysis helpers import successful')"`

### Phase 2: Create Category-Specific Fixture Files

### CREATE python/tests/fixtures/auth_fixtures.py:

- IMPLEMENT: Auth-specific test fixtures
- EXTRACT: Common fixtures from auth/test_auth_*.py files:
  - `@pytest.fixture` `mock_jwt_token()` - JWT token generation
  - `@pytest.fixture` `mock_user_session()` - User session data
  - `@pytest.fixture` `auth_headers()` - Authorization headers
  - `@pytest.fixture` `security_test_data()` - OWASP test vectors
  - `@pytest.fixture` `auth_performance_config()` - Performance test config
- PATTERN: Follow existing fixture pattern in fixtures/intelligence_documents.py
- IMPORTS: `import pytest; from typing import Dict, Any`
- GOTCHA: Use session-scoped fixtures for expensive setup
- **VALIDATE**: `python -c "from tests.fixtures.auth_fixtures import *; print('✓ Auth fixtures import successful')"`

### CREATE python/tests/fixtures/rag_fixtures.py:

- IMPLEMENT: RAG and search test fixtures
- EXTRACT: Common fixtures from test_rag_*.py and test_search_*.py files:
  - `@pytest.fixture` `rag_service()` - Mock RAG service instance
  - `@pytest.fixture` `mock_vector_results()` - Vector search results
  - `@pytest.fixture` `mock_rag_query_response()` - RAG query response
  - `@pytest.fixture` `search_test_documents()` - Test document corpus
  - `@pytest.fixture` `embedding_vectors()` - Mock embedding vectors (1536 dimensions)
  - `RAGTestDataManager` class - Test data management helper
- PATTERN: Async fixtures for async RAG operations
- IMPORTS: `import pytest; from unittest.mock import AsyncMock, MagicMock; from typing import List, Dict, Any`
- GOTCHA: RAG fixtures need proper async setup/teardown
- **VALIDATE**: `python -c "from tests.fixtures.rag_fixtures import RAGTestDataManager; print('✓ RAG fixtures import successful')"`

### CREATE python/tests/fixtures/performance_fixtures.py:

- IMPLEMENT: Performance and cache test fixtures
- EXTRACT: Common fixtures from test_search_performance.py and test_cache_management.py:
  - `@pytest.fixture` `research_orchestrator()` - ResearchOrchestrator instance with cleanup
  - `@pytest.fixture` `cache_client()` - ValkeyCache instance (test database 15)
  - `@pytest.fixture` `test_timeouts()` - Configurable timeout values from environment
  - `@pytest.fixture` `performance_baseline()` - Baseline performance metrics
  - `@pytest.fixture` `cache_key_generator()` - Cache key generation helper
- PATTERN: Follow test_search_performance.py fixtures (lines 30-60)
- IMPORTS: `import pytest, asyncio, os; from typing import Dict, Any`
- GOTCHA: Use test database 15 for cache to avoid conflicts; ensure cleanup in fixture teardown
- **VALIDATE**: `python -c "from tests.fixtures.performance_fixtures import *; print('✓ Performance fixtures import successful')"`

### CREATE python/tests/fixtures/mcp_fixtures.py:

- IMPLEMENT: MCP server test fixtures
- EXTRACT: Common fixtures from mcp_server/*/test_*.py files:
  - `@pytest.fixture` `mock_mcp_context()` - MCP context mock
  - `@pytest.fixture` `mock_tool_response()` - MCP tool response builder
  - `@pytest.fixture` `mcp_test_projects()` - Project test data for MCP
  - `@pytest.fixture` `mcp_test_documents()` - Document test data for MCP
  - `@pytest.fixture` `mcp_test_tasks()` - Task test data for MCP
- PATTERN: Simple fixtures for MCP tool testing
- IMPORTS: `import pytest; from typing import Dict, List, Any`
- GOTCHA: MCP fixtures should return JSON-serializable data
- **VALIDATE**: `python -c "from tests.fixtures.mcp_fixtures import *; print('✓ MCP fixtures import successful')"`

### Phase 3: Create Category-Specific conftest.py Files

### CREATE python/tests/auth/conftest.py:

- IMPLEMENT: Auth test configuration
- IMPORTS: Import from fixtures/auth_fixtures.py and utils/mock_helpers.py
- CONTENT:
  ```python
  """Auth test configuration and fixtures."""
  import pytest
  from tests.fixtures.auth_fixtures import *
  from tests.utils.mock_helpers import create_mock_database_client

  # Re-export fixtures for auth tests
  __all__ = ['mock_jwt_token', 'mock_user_session', 'auth_headers', 'security_test_data', 'auth_performance_config']
  ```
- PATTERN: Follow python/tests/conftest.py structure (lines 33-35)
- GOTCHA: Use `__all__` to control fixture exports
- **VALIDATE**: `python -c "import tests.auth.conftest; print('✓ Auth conftest import successful')"`

### CREATE python/tests/integration/conftest.py:

- IMPLEMENT: Integration test configuration
- IMPORTS: Import common fixtures and mock helpers
- CONTENT:
  ```python
  """Integration test configuration and fixtures."""
  import pytest
  from tests.utils.mock_helpers import create_mock_database_client, create_mock_httpx_client

  @pytest.fixture
  def integration_timeout():
      """Integration test timeout (2 seconds)."""
      return 2.0

  @pytest.fixture
  def mock_service_clients():
      """Mock all external service clients."""
      return {
          'database': create_mock_database_client(),
          'http': create_mock_httpx_client(),
      }
  ```
- PATTERN: Integration-specific timeouts and service mocks
- GOTCHA: Integration tests need longer timeouts than unit tests
- **VALIDATE**: `python -c "import tests.integration.conftest; print('✓ Integration conftest import successful')"`

### CREATE python/tests/performance/conftest.py:

- IMPLEMENT: Performance test configuration
- IMPORTS: Import from fixtures/performance_fixtures.py
- CONTENT:
  ```python
  """Performance test configuration and fixtures."""
  import pytest
  from tests.fixtures.performance_fixtures import *

  # Re-export performance fixtures
  __all__ = ['research_orchestrator', 'cache_client', 'test_timeouts', 'performance_baseline']

  @pytest.fixture(scope="session")
  def performance_test_mode():
      """Enable performance test mode."""
      return True
  ```
- PATTERN: Session-scoped fixtures for expensive setup
- GOTCHA: Performance tests should use session scope where possible
- **VALIDATE**: `python -c "import tests.performance.conftest; print('✓ Performance conftest import successful')"`

### CREATE python/tests/unit/conftest.py:

- IMPLEMENT: Unit test configuration
- IMPORTS: Import mock helpers for unit tests
- CONTENT:
  ```python
  """Unit test configuration and fixtures."""
  import pytest
  from tests.utils.mock_helpers import *
  from tests.utils.test_builders import *

  @pytest.fixture
  def unit_test_timeout():
      """Unit test timeout (100ms)."""
      return 0.1

  @pytest.fixture(autouse=True)
  def isolate_unit_tests(monkeypatch):
      """Automatically isolate unit tests from external dependencies."""
      monkeypatch.setenv("TEST_MODE", "unit")
      monkeypatch.setenv("DISABLE_EXTERNAL_CALLS", "true")
  ```
- PATTERN: Auto-use fixtures for test isolation
- GOTCHA: Unit tests should be completely isolated with mocks
- **VALIDATE**: `python -c "import tests.unit.conftest; print('✓ Unit conftest import successful')"`

### CREATE python/tests/mcp_server/conftest.py:

- IMPLEMENT: MCP server test configuration
- IMPORTS: Import from fixtures/mcp_fixtures.py
- CONTENT:
  ```python
  """MCP server test configuration and fixtures."""
  import pytest
  from tests.fixtures.mcp_fixtures import *

  # Re-export MCP fixtures
  __all__ = ['mock_mcp_context', 'mock_tool_response', 'mcp_test_projects', 'mcp_test_documents', 'mcp_test_tasks']
  ```
- PATTERN: Simple fixture re-exports
- GOTCHA: MCP tests need JSON-serializable data
- **VALIDATE**: `python -c "import tests.mcp_server.conftest; print('✓ MCP conftest import successful')"`

### Phase 4: Refactor Large Test Files (Root Directory)

### UPDATE python/tests/test_coverage_optimization.py:

- REFACTOR: Extract helper classes to utils/analysis_helpers.py
- REMOVE: Lines 67-674 (TestCategoryAnalyzer, TestFileAnalyzer, TestExecutionOptimizer, TestCoverageAnalyzer classes)
- ADD: Import statement at top: `from tests.utils.analysis_helpers import TestCategoryAnalyzer, TestFileAnalyzer, TestExecutionOptimizer, TestCoverageAnalyzer`
- KEEP: Test classes (TestCoverageValidation, TestExecutionOptimization) and test functions
- TARGET: Reduce from 43KB to <15KB
- **VALIDATE**: `pytest python/tests/test_coverage_optimization.py -v && wc -c python/tests/test_coverage_optimization.py`

### UPDATE python/tests/test_search_performance.py:

- REFACTOR: Extract fixtures to fixtures/performance_fixtures.py
- REMOVE: Lines 30-60 (research_orchestrator, cache_client fixtures)
- ADD: Import statement: `from tests.fixtures.performance_fixtures import research_orchestrator, cache_client, test_timeouts`
- EXTRACT: Performance metric collection logic to utils/performance_helpers.py
- REMOVE: Duplicate performance measurement code
- ADD: Use `measure_performance` decorator from performance_helpers
- TARGET: Reduce from 29KB to <15KB
- **VALIDATE**: `pytest python/tests/test_search_performance.py -v && wc -c python/tests/test_search_performance.py`

### UPDATE python/tests/test_menu_poc.py:

- REFACTOR: Extract menu test utilities to utils/menu_helpers.py (new file if needed)
- REMOVE: Duplicate mock setup code
- ADD: Import from mock_helpers and test_builders
- CONSOLIDATE: Merge similar test methods
- TARGET: Reduce from 26KB to <15KB
- **VALIDATE**: `pytest python/tests/test_menu_poc.py -v && wc -c python/tests/test_menu_poc.py`

### UPDATE python/tests/test_rag_integration.py:

- REFACTOR: Extract RAGTestDataManager to fixtures/rag_fixtures.py
- REMOVE: RAGTestDataManager class definition
- ADD: Import statement: `from tests.fixtures.rag_fixtures import RAGTestDataManager`
- EXTRACT: Common RAG test setup to rag_fixtures.py
- REMOVE: Duplicate fixture definitions
- TARGET: Reduce from 25KB to <15KB
- **VALIDATE**: `pytest python/tests/test_rag_integration.py -v && wc -c python/tests/test_rag_integration.py`

### UPDATE python/tests/test_menu_integration.py:

- REFACTOR: Extract menu integration utilities
- REMOVE: Duplicate mock and fixture code
- ADD: Import from fixtures and utils
- CONSOLIDATE: Merge redundant test cases
- TARGET: Reduce from 22KB to <15KB
- **VALIDATE**: `pytest python/tests/test_menu_integration.py -v && wc -c python/tests/test_menu_integration.py`

### UPDATE python/tests/test_async_embedding_service.py:

- REFACTOR: Extract AsyncContextManager to utils/mock_helpers.py
- REMOVE: AsyncContextManager class definition
- ADD: Import statement: `from tests.utils.mock_helpers import AsyncContextManager`
- EXTRACT: Common embedding test fixtures
- TARGET: Reduce from 22KB to <15KB
- **VALIDATE**: `pytest python/tests/test_async_embedding_service.py -v && wc -c python/tests/test_async_embedding_service.py`

### UPDATE python/tests/test_menu_handler.py:

- REFACTOR: Extract menu handler utilities
- REMOVE: Duplicate setup and teardown code
- ADD: Import from mock_helpers and test_builders
- TARGET: Reduce from 21KB to <15KB
- **VALIDATE**: `pytest python/tests/test_menu_handler.py -v && wc -c python/tests/test_menu_handler.py`

### UPDATE python/tests/test_async_llm_provider_service.py:

- REFACTOR: Extract AsyncContextManager and LLM mocks
- REMOVE: AsyncContextManager class, duplicate mock code
- ADD: Import from mock_helpers
- TARGET: Reduce from 20KB to <15KB
- **VALIDATE**: `pytest python/tests/test_async_llm_provider_service.py -v && wc -c python/tests/test_async_llm_provider_service.py`

### UPDATE python/tests/test_async_source_summary.py:

- REFACTOR: Extract source summary utilities
- REMOVE: Duplicate async test utilities
- ADD: Import from mock_helpers and performance_helpers
- TARGET: Reduce from 20KB to <15KB
- **VALIDATE**: `pytest python/tests/test_async_source_summary.py -v && wc -c python/tests/test_async_source_summary.py`

### UPDATE python/tests/test_rag_strategies.py:

- REFACTOR: Extract RAG strategy test utilities
- REMOVE: Duplicate RAG service mocks and fixtures
- ADD: Import from rag_fixtures
- TARGET: Reduce from 20KB to <15KB
- **VALIDATE**: `pytest python/tests/test_rag_strategies.py -v && wc -c python/tests/test_rag_strategies.py`

### Phase 5: Refactor Large Test Files (Subdirectories)

### UPDATE python/tests/auth/test_auth_security_owasp.py:

- REFACTOR: Extract security test vectors to fixtures/auth_fixtures.py
- REMOVE: Large inline security test data (OWASP vectors)
- ADD: Import from auth_fixtures
- EXTRACT: Auth helper functions to utils/auth_helpers.py (new file if needed)
- TARGET: Reduce from 59KB to <15KB
- **VALIDATE**: `pytest python/tests/auth/test_auth_security_owasp.py -v && wc -c python/tests/auth/test_auth_security_owasp.py`

### UPDATE python/tests/auth/test_auth_performance_benchmarks.py:

- REFACTOR: Extract performance benchmark utilities to utils/performance_helpers.py
- REMOVE: Duplicate performance measurement code
- ADD: Import from performance_helpers and auth_fixtures
- TARGET: Reduce from 40KB to <15KB
- **VALIDATE**: `pytest python/tests/auth/test_auth_performance_benchmarks.py -v && wc -c python/tests/auth/test_auth_performance_benchmarks.py`

### UPDATE python/tests/auth/test_auth_api_comprehensive.py:

- REFACTOR: Extract API test utilities
- REMOVE: Duplicate mock setup and test data
- ADD: Import from auth_fixtures and test_builders
- TARGET: Reduce from 39KB to <15KB
- **VALIDATE**: `pytest python/tests/auth/test_auth_api_comprehensive.py -v && wc -c python/tests/auth/test_auth_api_comprehensive.py`

### UPDATE python/tests/performance/test_correlation_generation_performance.py:

- REFACTOR: Extract correlation test utilities
- REMOVE: Duplicate performance measurement and correlation logic
- ADD: Import from performance_fixtures and performance_helpers
- TARGET: Reduce from 37KB to <15KB
- **VALIDATE**: `pytest python/tests/performance/test_correlation_generation_performance.py -v && wc -c python/tests/performance/test_correlation_generation_performance.py`

### UPDATE python/tests/performance/test_enhanced_search_performance.py:

- REFACTOR: Extract search performance utilities
- REMOVE: Duplicate performance benchmark code
- ADD: Import from performance_fixtures and performance_helpers
- TARGET: Reduce from 36KB to <15KB
- **VALIDATE**: `pytest python/tests/performance/test_enhanced_search_performance.py -v && wc -c python/tests/performance/test_enhanced_search_performance.py`

### UPDATE python/tests/unit/test_correlation_algorithms.py:

- REFACTOR: Extract correlation algorithm test utilities
- REMOVE: Large inline test data
- ADD: Import from fixtures/correlation_test_data.py (already exists)
- TARGET: Reduce from 28KB to <15KB
- **VALIDATE**: `pytest python/tests/unit/test_correlation_algorithms.py -v && wc -c python/tests/unit/test_correlation_algorithms.py`

### UPDATE python/tests/integration/test_circuit_breaker_validation.py:

- REFACTOR: Extract circuit breaker test utilities
- REMOVE: Duplicate integration test setup
- ADD: Import from integration conftest and mock_helpers
- TARGET: Reduce from 27KB to <15KB
- **VALIDATE**: `pytest python/tests/integration/test_circuit_breaker_validation.py -v && wc -c python/tests/integration/test_circuit_breaker_validation.py`

### UPDATE python/tests/integration/test_intelligence_api_endpoints.py:

- REFACTOR: Extract API endpoint test utilities
- REMOVE: Duplicate endpoint test setup
- ADD: Import from integration conftest and test_builders
- TARGET: Reduce from 27KB to <15KB
- **VALIDATE**: `pytest python/tests/integration/test_intelligence_api_endpoints.py -v && wc -c python/tests/integration/test_intelligence_api_endpoints.py`

### Phase 6: Update Main conftest.py

### UPDATE python/tests/conftest.py:

- ADD: Import from new utils and fixtures modules
- CONTENT: Add imports at end of file:
  ```python
  # Import utility modules for discovery
  from tests.utils import mock_helpers, test_builders, performance_helpers, analysis_helpers
  from tests.fixtures import auth_fixtures, rag_fixtures, performance_fixtures, mcp_fixtures
  ```
- PATTERN: Ensure all fixtures are discoverable by pytest
- GOTCHA: Don't break existing imports from intelligence_documents and correlation_test_data
- **VALIDATE**: `python -c "import tests.conftest; print('✓ Main conftest import successful')"`

---

## Validation Loop

### Level 1: Syntax & Style (Immediate Feedback)

```bash
# Run after creating each utils/fixtures module
ruff check python/tests/utils/ python/tests/fixtures/ --fix
mypy python/tests/utils/ python/tests/fixtures/
ruff format python/tests/utils/ python/tests/fixtures/

# Run after refactoring each test file
ruff check python/tests/test_*.py python/tests/*/test_*.py --fix
mypy python/tests/

# Expected: Zero errors
```

### Level 2: Unit Tests (Component Validation)

```bash
# Test each refactored file individually
pytest python/tests/test_coverage_optimization.py -v
pytest python/tests/test_search_performance.py -v
pytest python/tests/auth/test_auth_security_owasp.py -v
# ... repeat for each refactored file

# Expected: All tests pass with same results as before refactoring
```

### Level 3: Integration Testing (Full Suite Validation)

```bash
# Run full test suite to ensure no regressions
pytest python/tests/ -v --tb=short

# Run with coverage to ensure no dead code
pytest python/tests/ --cov=python/tests --cov-report=term-missing

# Expected: All tests pass, coverage maintained or improved
```

### Level 4: File Size Validation

```bash
# Verify all refactored files are now <15KB
find python/tests -name "test_*.py" -type f -exec wc -c {} + | awk '$1 > 15360 {print $1/1024 "KB", $2}' | sort -rn

# Expected: Zero files > 15KB (or only files not targeted for refactoring)
```

### Level 5: Import Validation

```bash
# Test that all imports work correctly
python -c "
from tests.utils.mock_helpers import *
from tests.utils.test_builders import *
from tests.utils.performance_helpers import *
from tests.utils.analysis_helpers import *
from tests.fixtures.auth_fixtures import *
from tests.fixtures.rag_fixtures import *
from tests.fixtures.performance_fixtures import *
from tests.fixtures.mcp_fixtures import *
print('✓ All imports successful')
"

# Expected: No import errors
```

---

## COMPLETION CHECKLIST

- [ ] All utility modules created (mock_helpers, test_builders, performance_helpers, analysis_helpers)
- [ ] All fixture modules created (auth_fixtures, rag_fixtures, performance_fixtures, mcp_fixtures)
- [ ] All category-specific conftest.py files created (auth, integration, performance, unit, mcp_server)
- [ ] All 31 large test files refactored to <15KB
- [ ] Full test suite passes with no regressions
- [ ] All linting and type checking passes
- [ ] File size validation shows 0 files >15KB (or only acceptable exceptions)
- [ ] Import validation successful for all new modules
- [ ] Coverage maintained or improved

---

## Notes

**Refactoring Strategy**: Incremental refactoring with validation at each step. Create infrastructure first (Phase 1-3), then refactor files one at a time (Phase 4-5), validating after each change.

**Backward Compatibility**: All refactored files should maintain 100% backward compatibility. Tests should pass without any changes to test logic.

**Performance**: Refactoring should not impact test execution time. Fixture sharing may actually improve performance by reducing redundant setup.

**Future Maintenance**: The new structure makes it easier to:
1. Add new test utilities (add to utils/)
2. Add new fixtures (add to fixtures/)
3. Find and reuse existing test helpers
4. Maintain consistent test patterns across the suite

**Success Metrics**:
- **Code Reduction**: 31 files reduced from ~1.2MB to <465KB (~61% reduction)
- **Maintainability**: Test utilities centralized and reusable
- **Discoverability**: Clear organization with utils/ and fixtures/ structure
- **Test Coverage**: Maintained or improved (no regressions)

<!-- EOF -->
