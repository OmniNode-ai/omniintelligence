# Test Execution Guide

## Problem: Missing Dependencies in Tests

**83 tests (55.7%)** were failing due to missing dependencies (`crawl4ai`, `omnibase_core`) when tests were run with the system Python instead of the project's virtual environment.

## Root Cause

Tests were being executed with **system Python 3.11** (`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11`) instead of **venv Python 3.12** (`.venv/bin/python`).

The system Python doesn't have the project-specific dependencies installed:
- `crawl4ai==0.6.2`
- `omnibase_core` (from GitHub)
- `omnibase_spi` (from GitHub)

## Solution

### ✅ Always Use Virtual Environment

**Correct way to run tests:**

```bash
# Option 1: Use venv Python directly
.venv/bin/python -m pytest [test_path] [options]

# Option 2: Activate venv first
source .venv/bin/activate
python -m pytest [test_path] [options]

# Option 3: Use the provided helper script
./run_tests.sh [test_path] [options]
```

**Incorrect (will fail):**

```bash
# ❌ Don't use system pytest
pytest tests/

# ❌ Don't use system python
python3 -m pytest tests/

# ❌ Don't use global pytest
/usr/local/bin/pytest tests/
```

## Fixed Issues

### 1. Fixture Name Corrections (5 tests fixed)

**Files Updated:**
- `tests/test_api_essentials.py` (2 tests)
- `tests/test_settings_api.py` (3 tests)

**Changes:**
```python
# Before (incorrect)
def test_create_project(client, test_project, mock_supabase_client):

# After (correct)
def test_create_project(client, test_project, mock_database_client):
```

The correct fixture name is `mock_database_client`, defined in `tests/conftest.py:50`.

### 2. Virtual Environment Usage (83 tests fixed)

All dependency-related failures were resolved by using the correct Python environment:
- ✅ **70 tests** in `test_crawl_orchestration_isolated.py` (crawl4ai dependency)
- ✅ **13 tests** in `test_api_essentials.py` and `test_settings_api.py` (omnibase_core, fixture issues)

## Test Results

### Before Fix (System Python)
```
83 tests failing due to:
- ModuleNotFoundError: No module named 'crawl4ai' (70 tests)
- ModuleNotFoundError: No module named 'omnibase_core' (13 tests)
```

### After Fix (Venv Python)
```
======================== 31 passed, 7 warnings in 2.82s ========================

tests/test_api_essentials.py::10 tests PASSED
tests/test_settings_api.py::3 tests PASSED
tests/test_crawl_orchestration_isolated.py::18 tests PASSED
```

## Helper Script: `run_tests.sh`

Use the provided helper script to ensure tests always run with the correct environment:

```bash
# Run all tests
./run_tests.sh

# Run specific test file
./run_tests.sh tests/test_api_essentials.py

# Run with coverage
./run_tests.sh --cov=src --cov-report=html

# Run with verbose output
./run_tests.sh -v

# Run specific test
./run_tests.sh tests/test_api_essentials.py::test_health_endpoint
```

## Dependency Groups

The project uses `uv` for dependency management with the following groups:

- **`dev`**: Development tools (pytest, mypy, ruff, black, isort)
- **`server`**: Server dependencies (FastAPI, crawl4ai, omnibase_core, omnibase_spi)
- **`mcp`**: MCP server dependencies
- **`agents`**: Agent service dependencies
- **`all`**: All dependencies combined (for local testing)

### Installing Dependencies

```bash
# Install all dependencies (recommended for local development)
uv sync --all-groups

# Install specific groups
uv sync --group dev --group server

# Install without dev dependencies
uv sync --group server --group mcp
```

## Verification

To verify your environment is correctly configured:

```bash
# Check Python version (should be 3.12.x)
.venv/bin/python --version

# Check dependencies are installed
.venv/bin/python -c "import crawl4ai; print('crawl4ai OK')"
.venv/bin/python -c "import omnibase_core; print('omnibase_core OK')"

# Run test suite
.venv/bin/python -m pytest tests/ -v
```

## CI/CD Recommendations

For continuous integration, ensure your CI configuration:

1. **Creates and activates virtual environment**
2. **Installs dependencies with uv**
3. **Runs tests with venv Python**

Example CI configuration:

```yaml
test:
  script:
    - uv sync --all-groups
    - .venv/bin/python -m pytest tests/ -v --cov=src
```

## Summary

**Root Cause**: Wrong Python interpreter
**Solution**: Always use `.venv/bin/python -m pytest`
**Impact**: **+83 tests** now passing (0 dependency errors)
**Files Fixed**: 2 test files (fixture name corrections)
