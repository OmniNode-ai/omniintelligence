# Test Coverage Setup Guide

This document provides examples and reference material for the newly configured test coverage reporting system.

## Quick Reference

### Running Tests with Coverage

```bash
# Default: Run all tests with coverage
cd /Volumes/PRO-G40/Code/omniarchon/python
./run_tests.sh

# Run specific test file
./run_tests.sh tests/test_my_module.py

# Run without coverage (faster for development)
./run_tests.sh --no-cov

# Run with verbose output
./run_tests.sh -v

# Run specific test class/method
./run_tests.sh tests/test_my_module.py::TestMyClass::test_method -v
```

## Example Coverage Output

### Terminal Output

```
==================== test session starts ====================
platform darwin -- Python 3.12.0, pytest-8.4.2, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: /Volumes/PRO-G40/Code/omniarchon/python
configfile: pyproject.toml
plugins: asyncio-0.21.0, cov-7.0.0, mock-3.12.0, timeout-2.3.0
collected 156 items

tests/test_api_essentials.py .....                    [  3%]
tests/test_business_logic.py .........                [  9%]
tests/test_intelligence_service.py ..............     [ 18%]
tests/unit/test_cache_service.py .................    [ 29%]
...

---------- coverage: platform darwin, python 3.12.0 -----------
Name                                      Stmts   Miss  Cover   Missing
-----------------------------------------------------------------------
src/server/api_routes/health.py             12      0   100%
src/server/api_routes/projects.py           45      3    93%   78-80
src/server/services/cache_service.py         67      8    88%   45, 89-95
src/mcp_server/features/quality.py          123     15    88%   67-71, 145-152
src/intelligence/quality_assessment.py       89     12    87%   34, 56-62, 134
src/intelligence/pattern_learning.py        156     42    73%   45-52, 89-102, 178-185
-----------------------------------------------------------------------
TOTAL                                       3456    287    92%

Coverage reports generated:
  → Terminal output (above)
  → HTML: htmlcov/index.html
  → XML: coverage.xml

View HTML report: open htmlcov/index.html

==================== 156 passed in 45.2s ====================
```

### HTML Report

The HTML report (`htmlcov/index.html`) provides:

**Index Page**:
- List of all modules with coverage percentages
- Sortable by coverage, statements, missing lines
- Color coding: green (>80%), yellow (60-80%), red (<60%)

**Module Detail Pages**:
```
src/intelligence/pattern_learning.py                    Coverage: 73%

   1 | """Pattern learning and matching service."""
   2 | from typing import List, Dict, Optional
   3 | import logging
   4 |
   5 | class PatternLearningService:
   6 |     """Service for pattern learning and matching."""
   7 |
   8 |     def __init__(self):
   9 |         self.logger = logging.getLogger(__name__)
  10 |         self.patterns = []
  11 |
  12 |     def match_pattern(self, code: str) -> Optional[Dict]:
  13 |         """Match code against known patterns."""
  14 |         if not code:
  15 |             return None
  16 |
  17 |         for pattern in self.patterns:
  18 |             if self._fuzzy_match(code, pattern):
  19 |                 return pattern
  20 |
  21 |         return None
  22 |
  23 |     def _fuzzy_match(self, code: str, pattern: Dict) -> bool:
  24 |         """Perform fuzzy matching."""
  25 |         # Implementation
  26 |         return True
  27 |
  28 | !!! def _experimental_feature(self):  # Lines 45-52 NOT COVERED
  29 | !!!     """Experimental feature not yet tested."""
  30 | !!!     # TODO: Add tests for this branch
  31 | !!!     if self.patterns:
  32 | !!!         return self._analyze_patterns()
  33 | !!!     return None

Green = covered, Red (!!! prefix) = not covered
```

### XML Report

The XML report (`coverage.xml`) is used by CI/CD and Codecov:

```xml
<?xml version="1.0" ?>
<coverage version="7.0.0" timestamp="1729449182" line-rate="0.9170" branch-rate="0.8520">
  <sources>
    <source>/Volumes/PRO-G40/Code/omniarchon/python/src</source>
  </sources>
  <packages>
    <package name="intelligence" line-rate="0.8650" branch-rate="0.8210">
      <classes>
        <class name="pattern_learning.py" filename="intelligence/pattern_learning.py" line-rate="0.7308">
          <methods/>
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="1"/>
            ...
            <line number="45" hits="0"/>
            <line number="46" hits="0"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
```

## Configuration Files

### .coveragerc

Located at: `/Volumes/PRO-G40/Code/omniarchon/python/.coveragerc`

Key configurations:
- **Minimum threshold**: 80% (build fails below)
- **Branch coverage**: Enabled
- **Exclusions**: tests/, migrations/, __init__.py
- **Parallel mode**: Enabled for concurrent test execution
- **Reports**: Terminal, HTML, XML

### pyproject.toml

`pytest-cov` is already configured in:
- `tool.poetry.group.dev.dependencies` (line 39)
- `dependency-groups.dev` (line 113)

No additional configuration needed in pyproject.toml.

## CI/CD Integration

### GitHub Actions (Existing)

The `.github/workflows/ci.yml` already includes:

1. **Install pytest-cov**: `uv add pytest-cov` (line 51)
2. **Run tests with coverage**: `--cov=src --cov-report=xml --cov-report=html` (lines 76-79)
3. **Upload to Codecov**: `codecov/codecov-action@v4` (lines 92-99)

**Codecov Setup**:
1. Sign up at https://codecov.io
2. Add repository
3. Copy Codecov token
4. Add as GitHub secret: `CODECOV_TOKEN`
5. Badge will auto-update on commits

### Coverage Badge

Added to `/Volumes/PRO-G40/Code/omniarchon/README.md`:

```markdown
[![codecov](https://codecov.io/gh/OmniNode-ai/omniarchon/branch/main/graph/badge.svg?token=YOUR_CODECOV_TOKEN)](https://codecov.io/gh/OmniNode-ai/omniarchon)
```

**Note**: Replace `YOUR_CODECOV_TOKEN` with actual token from Codecov dashboard.

## Common Use Cases

### 1. Running Tests During Development

```bash
# Fast iteration (no coverage)
./run_tests.sh --no-cov tests/test_my_feature.py -v

# With coverage (slower but comprehensive)
./run_tests.sh tests/test_my_feature.py -v
```

### 2. Pre-Commit Coverage Check

```bash
# Run all tests with coverage
./run_tests.sh

# Check that coverage meets threshold (80%+)
# Script will fail if below threshold
echo $?  # 0 = passed, 1 = failed
```

### 3. Investigating Low Coverage

```bash
# Step 1: Run tests and generate reports
./run_tests.sh

# Step 2: View terminal output for quick overview
# Look for modules with <80% coverage

# Step 3: Open HTML report for detailed view
open htmlcov/index.html

# Step 4: Click on low-coverage modules
# Red lines = not covered, add tests for these

# Step 5: Write tests for uncovered lines
vim tests/test_my_module.py

# Step 6: Verify improvement
./run_tests.sh tests/test_my_module.py
open htmlcov/index.html
```

### 4. Coverage for Specific Module

```bash
# Run only tests for specific module
./run_tests.sh tests/intelligence/ -v

# View coverage report (will show only tested modules)
open htmlcov/index.html
```

### 5. Excluding Code from Coverage

**Permanent exclusion** (in `.coveragerc`):
```ini
[report]
exclude_lines =
    pragma: no cover
    def __repr__
    if TYPE_CHECKING:
    @abstractmethod
```

**Inline exclusion**:
```python
def experimental_feature():  # pragma: no cover
    """Not yet tested, excluded from coverage."""
    pass

if TYPE_CHECKING:
    # Type-only imports, excluded automatically
    from typing import Protocol
```

## Troubleshooting

### Issue: Coverage report missing modules

**Symptom**: Some modules don't appear in coverage report

**Solution**:
1. Ensure modules are in `src/` directory
2. Check `.coveragerc` for correct `source` path
3. Verify modules are imported by tests

```bash
# Debug: Show which files are being measured
pytest tests/ --cov=src --cov-report=term-missing -v
```

### Issue: Coverage percentage too low

**Symptom**: Total coverage below 80%, build fails

**Solution**:
1. Run `./run_tests.sh` and view terminal output
2. Identify modules with low coverage
3. Open `htmlcov/index.html` and click on low-coverage files
4. Add tests for red (uncovered) lines
5. Focus on critical business logic first

**Example**:
```bash
# Terminal shows: src/my_module.py  73%   45-52, 89-102

# View HTML report
open htmlcov/index.html
# Click on my_module.py
# Lines 45-52 and 89-102 are red (uncovered)

# Add tests for those lines
# tests/test_my_module.py
def test_missing_branch():
    result = my_module.special_case(edge_case_input)
    assert result == expected_output

# Re-run and verify
./run_tests.sh tests/test_my_module.py
# Coverage should increase
```

### Issue: Tests pass locally but fail in CI on coverage

**Symptom**: Local coverage is 85%, CI shows 75%

**Possible causes**:
1. Different test files run in CI vs locally
2. Different Python version
3. Missing test dependencies in CI

**Solution**:
```bash
# Ensure CI runs all tests
# Check .github/workflows/ci.yml

# Run exact same command as CI
uv run pytest tests/ --cov=src --cov-report=xml --cov-report=html --cov-report=term-missing

# Check which tests are skipped
pytest tests/ --collect-only
```

### Issue: Branch coverage too low

**Symptom**: Line coverage is 90%, but branch coverage is 65%

**Solution**: Add tests for both branches of conditionals

```python
# Original code (2 branches)
def process(value):
    if value > 0:
        return positive_case()
    return negative_case()

# Need 2 tests to cover both branches
def test_positive_case():
    assert process(5) == expected_positive

def test_negative_case():
    assert process(-5) == expected_negative
```

## Best Practices

### 1. Run Coverage Regularly

```bash
# Before committing
./run_tests.sh

# During development (faster, no coverage)
./run_tests.sh --no-cov tests/test_my_feature.py

# Before pushing (full suite with coverage)
./run_tests.sh
```

### 2. Focus on Critical Code

Not all code needs 100% coverage:
- **Critical**: Business logic, API endpoints (90%+ target)
- **Important**: Utilities, helpers (80%+ target)
- **Low priority**: Debug code, type stubs (can use `pragma: no cover`)

### 3. Use Coverage to Find Dead Code

```bash
# If coverage shows a module is 0%, it might be unused
# Consider removing or ensuring it's properly tested
```

### 4. Don't Game the Metrics

**Bad**:
```python
def test_just_for_coverage():
    # Calls function but doesn't verify behavior
    my_function()  # ❌ No assertions
```

**Good**:
```python
def test_actual_behavior():
    result = my_function(input_data)
    assert result == expected_output  # ✅ Verifies correctness
    assert result.status == "success"
```

### 5. Review Coverage in PRs

```bash
# Check coverage impact of changes
git diff main...feature-branch

# Run tests for changed files
./run_tests.sh tests/test_changed_module.py

# Ensure coverage doesn't decrease
```

## Integration with Development Workflow

### Pre-commit Hook (Optional)

Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Run tests with coverage before committing
cd python
./run_tests.sh || {
    echo "Tests failed or coverage below 80%"
    exit 1
}
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

### VS Code Integration

Add to `.vscode/settings.json`:
```json
{
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": [
    "tests",
    "--cov=src",
    "--cov-report=html",
    "--cov-report=term"
  ],
  "coverage-gutters.coverageFileNames": [
    "coverage.xml"
  ],
  "coverage-gutters.showGutterCoverage": true,
  "coverage-gutters.showLineCoverage": true
}
```

Install VS Code extension: **Coverage Gutters**

## Summary

**Configuration Files Created**:
- ✅ `/Volumes/PRO-G40/Code/omniarchon/python/.coveragerc` - Coverage configuration
- ✅ `/Volumes/PRO-G40/Code/omniarchon/python/run_tests.sh` - Updated with coverage flags

**Documentation Updated**:
- ✅ `/Volumes/PRO-G40/Code/omniarchon/README.md` - Added coverage badge
- ✅ `/Volumes/PRO-G40/Code/omniarchon/python/tests/README.md` - Enhanced coverage section

**CI/CD Integration**:
- ✅ `.github/workflows/ci.yml` - Already configured with Codecov upload

**Key Features**:
- 80% minimum coverage threshold (enforced)
- Branch coverage enabled
- Three report formats: Terminal, HTML, XML
- Automatic coverage on every test run (can disable with `--no-cov`)
- Codecov integration for coverage tracking over time

**Next Steps**:
1. Set up Codecov account and add `CODECOV_TOKEN` to GitHub secrets
2. Replace `YOUR_CODECOV_TOKEN` in README.md badge with actual token
3. Run `./run_tests.sh` to generate initial coverage report
4. Review `htmlcov/index.html` and improve coverage for low-coverage modules
5. Monitor coverage trends in Codecov dashboard

---

**Archon Test Coverage** | Version 1.0.0 | Coverage Target: 80%+
