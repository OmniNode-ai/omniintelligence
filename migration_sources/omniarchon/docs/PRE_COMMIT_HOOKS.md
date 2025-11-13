# Pre-Commit Hooks Configuration

**Status**: ✅ Active | **Created**: 2025-11-12 | **Purpose**: Prevent broken code commits

## Overview

Automated pre-commit hooks that run critical integration tests before allowing commits. Designed to catch vectorization pipeline bugs that would break the system in production.

## Installed Hooks

### 1. Formatting (Always Runs)
- **Black**: Python code formatting (88 char line length)
- **isort**: Import statement sorting
- **Trailing whitespace**: Remove trailing spaces
- **File checks**: End-of-file fixer, merge conflict detection, large file check

### 2. Unit Test Smoke Tests (Always Runs)
- **Location**: `tests/unit/intelligence` + `tests/unit/services`
- **Duration**: ~5-10 seconds
- **Behavior**: Always runs on every commit
- **Failure**: Blocks commit if tests fail

### 3. Critical Integration Test (Conditional)
- **Test**: `test_document_processing_creates_vector`
- **Location**: `tests/integration/test_post_deployment_smoke.py`
- **Duration**: ~30-60 seconds
- **Trigger**: Only runs when these paths change:
  - `services/intelligence/`
  - `services/search/`
  - `services/bridge/`
  - `tests/integration/`
- **Behavior**:
  - ✅ **Services DOWN**: Skips gracefully (allows commit)
  - ✅ **Services UP + Test PASS**: Allows commit
  - ❌ **Services UP + Test FAIL**: **BLOCKS commit** (bug detected!)

### 4. Incremental Tree Stamping (Always Runs)
- **Purpose**: Update ONEX metadata stamps
- **Duration**: ~1-2 seconds

## Installation

```bash
# Run setup script
./scripts/setup_pre_commit_hooks.sh

# Verify installation
pre-commit run --all-files
```

## Usage

### Normal Workflow (Automatic)

```bash
# Make changes
git add .

# Commit (hooks run automatically)
git commit -m "your message"

# Hooks execute:
# 1. Black/isort formatting (auto-fix)
# 2. Unit test smoke tests (~5-10s)
# 3. Critical integration test (~30-60s, if services running)
# 4. Tree stamping (~1-2s)
```

### Manual Hook Testing

```bash
# Test all hooks
pre-commit run --all-files

# Test only critical integration test
pre-commit run critical-integration-test --all-files

# Test on specific files
pre-commit run --files services/intelligence/src/main.py
```

### Bypassing Hooks (Emergency Only)

```bash
# Skip all hooks (NOT RECOMMENDED)
git commit --no-verify -m "emergency fix"

# When to use:
# - Production outage requiring immediate hotfix
# - CI/CD pipeline failure (not local code issue)
# - Services unavailable (though integration test skips gracefully)
```

## Critical Integration Test Details

### What It Tests

The `test_document_processing_creates_vector` test validates the complete vectorization pipeline:

1. ✅ POST `/process/document` accepts document
2. ✅ Endpoint returns 200 OK
3. ✅ Vector is **actually created** in Qdrant (not just claimed)
4. ✅ Vector has correct dimensions (1536)
5. ✅ Vector has correct metadata (document_id, project, etc.)

### Why This Test Matters

**Real Bug It Would Have Caught**:
```
❌ VECTORIZATION BUG (Production Issue)
└─ /process/document returned 200 OK
└─ Response claimed document was processed
└─ BUT: No vector was actually created in Qdrant
└─ Result: Silent data loss, broken search functionality
```

This test ensures that **success responses actually correspond to successful vectorization**, preventing silent failures.

### Test Execution Flow

```
┌─────────────────────────────────────────────────┐
│ 1. Check if services are running               │
│    curl http://localhost:8053/health            │
└─────────────────┬───────────────────────────────┘
                  │
                  ├─ Services DOWN ──> Skip (exit 0)
                  │
                  └─ Services UP ──> Continue
                                      │
┌─────────────────────────────────────▼───────────┐
│ 2. Run critical integration test                │
│    • Create unique test document                │
│    • POST /process/document                     │
│    • Wait 2 seconds for indexing                │
│    • Query Qdrant for vector                    │
└─────────────────┬───────────────────────────────┘
                  │
                  ├─ Vector EXISTS ──> PASS (exit 0)
                  │
                  └─ Vector MISSING ──> FAIL (exit 1)
                                        ↓
                              ❌ BLOCK COMMIT
```

### Service Requirements

**Required Services**:
- `archon-intelligence` (port 8053)
- `archon-search` (port 8055)
- `qdrant` (port 6333)

**Start Services**:
```bash
docker compose up -d

# Verify
curl http://localhost:8053/health
curl http://localhost:8055/health
curl http://localhost:6333/collections
```

## Performance Benchmarks

| Hook | Duration | Frequency | Skippable |
|------|----------|-----------|-----------|
| Black/isort | ~1-2s | Every commit | No (formatting) |
| Unit smoke tests | ~5-10s | Every commit | No (critical) |
| Integration test | ~30-60s | Service/test changes only | Yes (if services down) |
| Tree stamping | ~1-2s | Every commit | No (metadata) |

**Total Time** (services running, changes to services):
- **Fast path**: ~7-13s (no service changes)
- **Full path**: ~37-73s (service changes + integration test)

## Troubleshooting

### Hook Failed: "Services not running"

```bash
# Start services
docker compose up -d

# Verify services
docker compose ps

# Check health
curl http://localhost:8053/health
```

### Hook Failed: "Vectorization bug detected"

This means the test found a **real bug** in your code:

```bash
# 1. Check service logs
docker compose logs archon-intelligence

# 2. Verify Qdrant is working
curl http://localhost:6333/collections

# 3. Run test manually to debug
pytest tests/integration/test_post_deployment_smoke.py::TestPostDeploymentSmoke::test_document_processing_creates_vector -v

# 4. Fix the bug in your code
# 5. Retry commit
```

### Hook Timeout

```bash
# Increase timeout in wrapper script
# Edit: scripts/git_hooks/run_critical_integration_test.sh
# Change: --timeout=60 to --timeout=120
```

### False Positives

If the test is failing but you believe it's a false positive:

```bash
# 1. Run test manually with verbose output
pytest tests/integration/test_post_deployment_smoke.py::TestPostDeploymentSmoke::test_document_processing_creates_vector -vvv

# 2. Check if services are actually healthy
python3 scripts/verify_environment.py --verbose

# 3. Review recent changes to vectorization pipeline
git diff HEAD services/intelligence/src/services/document_processor.py
```

## Configuration Files

### Primary Configuration
- **`.pre-commit-config.yaml`**: Main hook configuration
- **`scripts/setup_pre_commit_hooks.sh`**: Installation script
- **`scripts/git_hooks/run_critical_integration_test.sh`**: Integration test runner

### Related Files
- **`tests/integration/test_post_deployment_smoke.py`**: Test implementation
- **`docs/VALIDATION_SCRIPT.md`**: Validation documentation
- **`docs/OBSERVABILITY.md`**: Monitoring guide

## Best Practices

### Development Workflow

1. **Start services first**:
   ```bash
   docker compose up -d
   ```

2. **Make changes and test locally**:
   ```bash
   pytest tests/unit/intelligence -v
   ```

3. **Commit (hooks run automatically)**:
   ```bash
   git add .
   git commit -m "feat: improve vectorization"
   ```

4. **If hooks fail, fix the issue**:
   - Don't bypass hooks unless absolutely necessary
   - Investigate why the test is failing
   - Fix the underlying bug

### When to Bypass Hooks

**✅ Acceptable**:
- Production emergency hotfix
- Reverting a broken commit
- CI/CD configuration changes

**❌ Not Acceptable**:
- "Test is too slow"
- "I'll fix it later"
- "It works on my machine"
- "CI will catch it"

### CI/CD Integration

Pre-commit hooks provide **immediate local feedback**. CI/CD runs the **full test suite**:

```
Local (pre-commit)          CI/CD Pipeline
├─ Unit smoke tests         ├─ Full unit test suite
├─ 1 critical test          ├─ Full integration test suite
└─ ~30-60s                  ├─ E2E tests
                            ├─ Performance benchmarks
                            └─ ~10-20 minutes
```

**Philosophy**: Catch critical bugs locally (fast), catch everything in CI (thorough).

## Maintenance

### Updating Hooks

```bash
# Update pre-commit tool
pip install --upgrade pre-commit

# Update hook repositories
pre-commit autoupdate

# Reinstall hooks
pre-commit install
```

### Adding New Tests

To add more integration tests to the pre-commit hook:

1. Add test to `tests/integration/test_post_deployment_smoke.py`
2. Mark with `@pytest.mark.smoke` and `@pytest.mark.critical`
3. Update `scripts/git_hooks/run_critical_integration_test.sh` to run additional test
4. Keep total execution time < 60 seconds

### Removing Hooks

```bash
# Uninstall hooks
pre-commit uninstall

# Remove from git
rm .git/hooks/pre-commit
```

## Success Metrics

**Target Metrics**:
- ✅ 0% of commits with known vectorization bugs
- ✅ <5% of commits bypassing hooks
- ✅ <60s average pre-commit time (with services running)
- ✅ >95% developer satisfaction with hook speed

**Monitor**:
```bash
# Check hook execution times
grep "duration:" .git/hooks/pre-commit.log

# Check bypass rate
git log --all --grep="--no-verify" --oneline | wc -l
```

---

**Questions?** See:
- `docs/VALIDATION_SCRIPT.md` - Data integrity validation
- `docs/OBSERVABILITY.md` - Monitoring guide
- `docs/SLACK_ALERTING.md` - Production alerts
- `CLAUDE.md` - Architecture overview
