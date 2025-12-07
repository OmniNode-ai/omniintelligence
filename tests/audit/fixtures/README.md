# I/O Audit Test Fixtures

This directory contains test fixtures for the ONEX I/O audit system. These fixtures are used to verify that the audit correctly detects (or allows) various I/O patterns in Python code.

## Directory Structure

```
tests/audit/fixtures/
├── README.md           # This file
├── __init__.py         # Package marker
└── io/                 # I/O audit specific fixtures
    ├── __init__.py     # Package marker
    ├── good_node.py    # Clean node with no violations
    ├── bad_client.py   # Network/DB client violations
    ├── bad_env.py      # Environment variable violations
    ├── bad_file.py     # File I/O violations
    └── whitelisted_node.py  # Whitelist testing
```

## Fixture Summary

| Fixture | Expected Violations | Rule Tested | Purpose |
|---------|---------------------|-------------|---------|
| `good_node.py` | 0 | None | Clean baseline - pure compute node |
| `bad_client.py` | 17 | `net-client` | Network/DB client imports and usage |
| `bad_env.py` | 9 | `env-access` | Environment variable access patterns |
| `bad_file.py` | 11 | `file-io` | File system operations |
| `whitelisted_node.py` | 1-3 (varies) | `env-access`, `file-io` | Whitelist functionality testing |

## Detailed Fixture Documentation

### `good_node.py` - Clean Compute Node

**Expected Violations**: 0

A properly designed ONEX compute node that demonstrates the correct pattern:
- No direct infrastructure client imports
- No environment variable access
- No file I/O operations
- All configuration received via function parameters

This fixture serves as the baseline for what "clean" code looks like.

### `bad_client.py` - Network/DB Client Violations

**Expected Violations**: 17 (`net-client` rule)

Tests detection of forbidden network and database client imports:

| Violation Type | Count | Examples |
|----------------|-------|----------|
| Direct imports | 9 | `confluent_kafka`, `qdrant_client`, `neo4j`, `asyncpg`, `httpx`, `aiofiles` |
| Client usage | 6 | `Producer()`, `QdrantClient()`, `GraphDatabase.driver()` |
| Aliased imports | 2 | `import httpx as http_client`, `import confluent_kafka as ck` |

Forbidden modules tested:
- `confluent_kafka` - Kafka messaging
- `qdrant_client` - Vector database
- `neo4j` - Graph database
- `asyncpg` - PostgreSQL async driver
- `httpx` - HTTP client (including `AsyncClient`)
- `aiofiles` - Async file I/O

### `bad_env.py` - Environment Variable Violations

**Expected Violations**: 9 (`env-access` rule)

Tests detection of environment variable access patterns:

| Line | Pattern | Description |
|------|---------|-------------|
| 16 | `os.environ["API_KEY"]` | Direct subscript access |
| 19 | `os.environ.get("TIMEOUT")` | `.get()` method |
| 22 | `os.getenv("SERVICE_HOST")` | `getenv()` function |
| 34 | `os.putenv(key, value)` | Setting env vars |
| 40 | `"DEBUG_MODE" in os.environ` | Membership check |
| 46 | `os.environ.pop(key)` | Removing env vars |
| 52 | `os.environ.setdefault(key, default)` | Setting defaults |
| 58 | `os.environ.clear()` | Clearing all env vars |
| 64 | `os.environ.update(values)` | Bulk updates |

### `bad_file.py` - File I/O Violations

**Expected Violations**: 11 (`file-io` rule)

Tests detection of file system operations:

| Line | Pattern | Description |
|------|---------|-------------|
| 16 | `RotatingFileHandler` import | Logging handler import |
| 23 | `open(path)` | Built-in open for reading |
| 30 | `open(path, "w")` | Built-in open for writing |
| 37 | `path.read_text()` | Pathlib read text |
| 43 | `path.write_text()` | Pathlib write text |
| 49 | `path.read_bytes()` | Pathlib read bytes |
| 55 | `path.write_bytes()` | Pathlib write bytes |
| 61 | `path.open()` | Pathlib open method |
| 68 | `io.open(path)` | io module open |
| 77 | `logging.FileHandler()` | File logging handler |
| 88 | `RotatingFileHandler()` | Rotating file handler |

### `whitelisted_node.py` - Whitelist Testing

**Expected Violations**: Varies based on whitelist configuration

Tests the two-level whitelist system:

1. **YAML Whitelist** (`io_audit_whitelist.yaml`): File-level exceptions
2. **Inline Pragmas**: Line-level granularity (only work if file is in YAML)

Contains:
- `get_debug_config()` - Whitelisted via YAML (`env-access`)
- `read_local_debug_file()` - Whitelisted via inline pragma (`file-io`)
- `get_unwhitelisted_env()` - NOT whitelisted (should be caught)

## Adding New Test Fixtures

### Step 1: Create the Fixture File

Create a new Python file in `tests/audit/fixtures/io/` with intentional violations:

```python
"""A node with [specific violation type] violations.

This fixture demonstrates forbidden patterns:
- [Pattern 1]
- [Pattern 2]

NOTE: This file intentionally contains violations for testing.
"""

# ruff: noqa: F401  # Suppress unused import warnings

# VIOLATION: [description]
[code with violation]
```

### Step 2: Update the Test File

Add the expected violation count to `EXPECTED_VIOLATIONS` in `tests/audit/test_io_violations.py`:

```python
EXPECTED_VIOLATIONS = {
    # ... existing entries ...
    "new_fixture.py": {
        "rule": EnumIOAuditRule.RULE_NAME,
        "count": N,
        "description": "Description of violations",
    },
}
```

### Step 3: Add Verification Test

Add a test in `TestFixtureViolationCounts`:

```python
def test_new_fixture_violation_count(self) -> None:
    """Verify new_fixture.py has exactly N [rule] violations."""
    expected = EXPECTED_VIOLATIONS["new_fixture.py"]
    violations = audit_file(fixture_path("new_fixture.py"))
    rule_violations = [v for v in violations if v.rule == expected["rule"]]
    assert len(rule_violations) == expected["count"], (
        f"Expected {expected['count']} {expected['rule'].value} violations, "
        f"got {len(rule_violations)}. See EXPECTED_VIOLATIONS for details."
    )
```

### Step 4: Update This README

Add the new fixture to the summary table and detailed documentation section.

## Why Specific Violations Are Included

### Network Client Violations (`net-client`)

ONEX compute nodes must not directly interact with external services. Instead:
- Effect nodes handle external I/O
- Compute nodes receive data via function parameters
- This enables testing without infrastructure dependencies

### Environment Variable Violations (`env-access`)

Configuration should be injected, not read from environment:
- Enables deterministic testing
- Supports multiple environments without code changes
- Centralizes configuration management

### File I/O Violations (`file-io`)

Compute nodes should not perform file operations:
- Enables pure function testing
- Supports containerized deployments
- Prevents side effects during computation

## Updating Violation Counts

When fixture files are modified:

1. **Run the audit** to get actual counts:
   ```bash
   uv run python -m omniintelligence.audit.io_audit tests/audit/fixtures/io/bad_client.py
   ```

2. **Update `EXPECTED_VIOLATIONS`** in `test_io_violations.py`

3. **Update the comment** at lines 44-49 of `test_io_violations.py`

4. **Update this README** with the new counts

5. **Run tests** to verify:
   ```bash
   pytest tests/audit/test_io_violations.py -v
   ```

## Related Documentation

- [I/O Audit Tool](../../../src/omniintelligence/audit/io_audit.py) - Main audit implementation
- [Whitelist Configuration](../io_audit_whitelist.yaml) - YAML whitelist for test fixtures
- [Tools README](../../../src/omniintelligence/tools/README.md) - CLI tool documentation
