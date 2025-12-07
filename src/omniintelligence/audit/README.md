# I/O Audit Module

ONEX Node Purity Enforcement through AST-Based Static Analysis.

## Overview

The I/O audit module enforces the **"pure compute / no I/O"** architectural invariant for ONEX nodes. It uses Python's Abstract Syntax Tree (AST) to statically analyze source files and detect forbidden I/O patterns that violate node purity constraints.

**Key Principle**: Compute nodes must be pure - they should not perform network calls, file I/O, or environment variable access directly. These operations belong in Effect nodes or should be passed via dependency injection.

ONEX architecture separates nodes into distinct types:
- **Compute nodes**: Pure data transformation with no side effects
- **Effect nodes**: Handle all external I/O (Kafka, databases, HTTP, files)

This tool ensures compute nodes remain pure by detecting any I/O operations that should be delegated to effect nodes.

## Forbidden Patterns

The audit detects three categories of I/O violations:

### `net-client` - Network/Database Client Imports

Detects imports of external client libraries that perform network or database I/O:

| Library | Purpose |
|---------|---------|
| `confluent_kafka` | Kafka client |
| `qdrant_client` | Vector database client |
| `neo4j` | Graph database client |
| `asyncpg` | PostgreSQL async client |
| `httpx` | HTTP client |
| `aiofiles` | Async file I/O |

**Remediation**: Move to an Effect node or inject client via dependency injection.

### `env-access` - Environment Variable Access

Detects direct environment variable reads and mutations:

- `os.environ[...]` - Dictionary-style access
- `os.getenv()` - Environment getter
- `os.putenv()` - Environment setter
- `os.environ.get()`, `.pop()`, `.setdefault()`, `.clear()`, `.update()` - Dict methods
- `"key" in os.environ` - Membership checks

**Remediation**: Pass configuration via constructor parameters instead of reading env vars.

### `file-io` - File System Operations

Detects file system read/write operations:

- `open()` - Built-in file open
- `io.open()` - IO module open
- `Path.read_text()`, `.write_text()`, `.read_bytes()`, `.write_bytes()`, `.open()` - Pathlib I/O
- `FileHandler`, `RotatingFileHandler`, `TimedRotatingFileHandler`, `WatchedFileHandler` - Logging handlers

**Remediation**: Move file I/O to an Effect node or pass file content as input parameter.

## CLI Usage

### Basic Usage

```bash
# Run audit on default targets (src/omniintelligence/nodes)
python -m omniintelligence.audit

# Run audit on specific directory
python -m omniintelligence.audit src/omniintelligence/nodes

# Run audit on multiple directories
python -m omniintelligence.audit src/myproject/nodes src/other/nodes
```

### With Whitelist

```bash
# Use custom whitelist file
python -m omniintelligence.audit --whitelist tests/audit/io_audit_whitelist.yaml

# Short form
python -m omniintelligence.audit -w tests/audit/io_audit_whitelist.yaml
```

### Output Options

```bash
# Verbose output with whitelist usage hints
python -m omniintelligence.audit --verbose
python -m omniintelligence.audit -v

# JSON output for CI/CD integration
python -m omniintelligence.audit --json
```

### Combined Examples

```bash
# Full audit with custom whitelist and verbose output
python -m omniintelligence.audit \
    src/omniintelligence/nodes \
    --whitelist tests/audit/io_audit_whitelist.yaml \
    --verbose

# CI/CD pipeline with JSON output
python -m omniintelligence.audit \
    --whitelist tests/audit/io_audit_whitelist.yaml \
    --json

# Using uv (recommended for development)
uv run python -m omniintelligence.audit
uv run python -m omniintelligence.audit --json
```

### CLI Options Reference

| Option | Short | Description |
|--------|-------|-------------|
| `targets` | - | Directories to scan (positional, default: `src/omniintelligence/nodes`) |
| `--whitelist PATH` | `-w PATH` | Path to whitelist YAML file |
| `--verbose` | `-v` | Enable verbose output with additional context |
| `--json` | - | Output in JSON format for CI integration |

## Exit Codes

| Code | Meaning | Description |
|------|---------|-------------|
| `0` | Success | No I/O violations found |
| `1` | Violations | One or more files contain forbidden I/O patterns |
| `2` | Error | CLI usage error or unexpected failure |

### CI/CD Integration Example

```bash
# In GitHub Actions or other CI
python -m omniintelligence.audit --json --whitelist tests/audit/io_audit_whitelist.yaml
exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "I/O audit passed"
elif [ $exit_code -eq 1 ]; then
    echo "I/O violations detected"
    exit 1
else
    echo "Audit error"
    exit 2
fi
```

## Output Examples

### Text Output (Clean)

```
No I/O violations found. (42 files scanned)
```

### Text Output (Violations)

```
src/omniintelligence/nodes/bad_node.py:
  Line 5: [net-client] Forbidden import: confluent_kafka
  Line 12: [env-access] Forbidden call: os.getenv()
  -> Hints: Move to Effect node or inject client via dependency injection.; Pass configuration via constructor parameters instead of reading env vars.

Summary: 2 violation(s) in 1 file(s) (42 files scanned)
```

### Verbose Output (Violations)

```
src/omniintelligence/nodes/bad_node.py:
  Line 5: [net-client] Forbidden import: confluent_kafka
  Line 12: [env-access] Forbidden call: os.getenv()
  -> Hints: Move to Effect node or inject client via dependency injection.; Pass configuration via constructor parameters instead of reading env vars.

Summary: 2 violation(s) in 1 file(s) (42 files scanned)

Use --whitelist to specify allowed exceptions.
See CLAUDE.md for whitelist hierarchy documentation.
```

### JSON Output

```json
{
  "violations": [
    {
      "file": "src/omniintelligence/nodes/bad_node.py",
      "line": 5,
      "column": 0,
      "rule": "net-client",
      "message": "Forbidden import: confluent_kafka"
    },
    {
      "file": "src/omniintelligence/nodes/bad_node.py",
      "line": 12,
      "column": 4,
      "rule": "env-access",
      "message": "Forbidden call: os.getenv()"
    }
  ],
  "files_scanned": 42,
  "is_clean": false
}
```

### JSON Output (Error)

```json
{
  "error": "File not found: /path/to/missing.py",
  "error_type": "file_not_found"
}
```

## Whitelist Hierarchy

The I/O audit uses a **two-level whitelist system** with a strict hierarchy. This design ensures central visibility and code review coverage for all I/O exceptions.

### Level 1: YAML Whitelist (Primary Source of Truth)

Located at `tests/audit/io_audit_whitelist.yaml`, this file defines which files are allowed to have I/O exceptions.

```yaml
schema_version: "1.0.0"

files:
  - path: "src/omniintelligence/nodes/my_effect_node.py"
    reason: "Effect node requires Kafka client for event publishing"
    allowed_rules:
      - "net-client"
      - "env-access"
```

**Required fields**:
- `path`: File path or glob pattern (e.g., `nodes/legacy_*.py`)
- `reason`: Non-empty documentation explaining why the exception is needed
- `allowed_rules`: List of rule IDs (`net-client`, `env-access`, `file-io`)

### Level 2: Inline Pragmas (Secondary, Line-Level Granularity)

Format: `# io-audit: ignore-next-line <rule>`

Provides fine-grained control for specific lines within whitelisted files.

```python
# io-audit: ignore-next-line net-client
from confluent_kafka import Producer  # Whitelisted by pragma
```

### CRITICAL: Pragmas Require YAML Entry

**Inline pragmas ONLY work for files that are already listed in the YAML whitelist.** If you add a pragma to a file not in the whitelist, it will be **silently ignored**.

This is by design to ensure:
- Central visibility of all I/O exceptions in one YAML file
- Code review coverage for any new exceptions (YAML changes are visible in PRs)
- Developers cannot silently add I/O to pure compute nodes

### Correct Workflow

**Step 1**: Add the file to the YAML whitelist:

```yaml
files:
  - path: "src/omniintelligence/nodes/my_effect_node.py"
    reason: "Effect node requires Kafka client"
    allowed_rules:
      - "net-client"
```

**Step 2**: Use inline pragmas in the whitelisted file:

```python
# io-audit: ignore-next-line net-client
from confluent_kafka import Producer  # Now correctly whitelisted
```

### Incorrect Workflow (Pragma Ignored)

```python
# This pragma is IGNORED because file is not in YAML whitelist!
# io-audit: ignore-next-line net-client
from confluent_kafka import Producer  # VIOLATION STILL REPORTED
```

## Adding Whitelist Exceptions

### When to Add an Exception

Add a whitelist exception when:
- The file is an **Effect node** that legitimately needs I/O
- The file is a **legacy node** pending refactor (track with ticket)
- The file is a **test fixture** for testing I/O audit functionality

Do NOT add exceptions for:
- Compute nodes that should be refactored
- Quick fixes to bypass the audit
- Files without documented reasons

### Step-by-Step Process

**Step 1: Evaluate the Exception**

Before adding an exception, verify:
- Is this truly an effect node that requires I/O?
- Can the I/O be delegated to a dedicated effect node instead?
- Is the exception documented with a ticket number if it's technical debt?

**Step 2: Add to YAML Whitelist**

Edit `tests/audit/io_audit_whitelist.yaml`:

```yaml
files:
  - path: "src/omniintelligence/nodes/new_effect_node.py"
    reason: "Effect node for external API integration - handles HTTP calls"
    allowed_rules:
      - "net-client"
```

**Step 3: Add Inline Pragmas (Optional)**

For fine-grained control, add pragmas to specific lines:

```python
# io-audit: ignore-next-line net-client
from httpx import AsyncClient  # Whitelisted

# io-audit: ignore-next-line env-access
api_key = os.environ["API_KEY"]  # Whitelisted
```

**Step 4: Verify**

Run the audit to confirm the exception works:

```bash
python -m omniintelligence.audit
```

**Step 5: Commit Both Changes**

Commit the YAML whitelist and code changes together for code review visibility.

### Glob Pattern Examples

```yaml
files:
  # Single file
  - path: "src/omniintelligence/nodes/kafka_effect.py"
    reason: "Kafka effect node"
    allowed_rules:
      - "net-client"

  # All legacy nodes (glob pattern)
  - path: "src/omniintelligence/nodes/legacy_*.py"
    reason: "Legacy nodes pending refactor - tracked in OMN-123"
    allowed_rules:
      - "env-access"
      - "file-io"

  # All files in a directory
  - path: "src/omniintelligence/adapters/*.py"
    reason: "Adapter layer handles external integrations"
    allowed_rules:
      - "net-client"
      - "env-access"
```

### Security Considerations

- **Minimize exceptions**: Only whitelist what is strictly necessary
- **Document reasons**: Every exception must have a documented reason
- **Use specific rules**: Don't whitelist all rules when only one is needed
- **Prefer YAML over pragmas**: YAML changes are visible in code review
- **Track technical debt**: Include ticket numbers for legacy exceptions

## Integration with CI/Pre-commit

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: io-audit
        name: ONEX I/O Audit
        entry: uv run python -m omniintelligence.audit --whitelist tests/audit/io_audit_whitelist.yaml
        language: system
        types: [python]
        pass_filenames: false
        files: ^src/omniintelligence/nodes/.*\.py$
```

### GitHub Actions

Add to your CI workflow (`.github/workflows/ci.yaml`):

```yaml
jobs:
  io-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run I/O Audit
        run: |
          python -m omniintelligence.audit \
            --whitelist tests/audit/io_audit_whitelist.yaml
```

## Programmatic API

The module exports functions for programmatic use:

```python
from pathlib import Path
from omniintelligence.audit import (
    run_audit,
    audit_file,
    audit_files,
    load_whitelist,
    apply_whitelist,
    EnumIOAuditRule,
    ModelAuditResult,
    ModelIOAuditViolation,
)

# Run full audit on directories
result = run_audit(
    targets=["src/omniintelligence/nodes"],
    whitelist_path=Path("tests/audit/io_audit_whitelist.yaml"),
)

print(f"Files scanned: {result.files_scanned}")
print(f"Clean: {result.is_clean}")

for violation in result.violations:
    print(f"{violation.file}:{violation.line} [{violation.rule.value}] {violation.message}")

# Audit single file
violations = audit_file(Path("src/mynode.py"))

# Audit multiple files
all_violations = audit_files([Path("node1.py"), Path("node2.py")])

# Load and apply whitelist manually
whitelist = load_whitelist(Path("tests/audit/io_audit_whitelist.yaml"))
remaining = apply_whitelist(violations, whitelist, file_path, source_lines)
```

### Exported Symbols

| Symbol | Type | Description |
|--------|------|-------------|
| `run_audit()` | Function | Main entry point for running audits |
| `audit_file()` | Function | Audit a single Python file |
| `audit_files()` | Function | Audit multiple Python files |
| `load_whitelist()` | Function | Load and parse whitelist YAML |
| `apply_whitelist()` | Function | Filter violations based on whitelist |
| `parse_inline_pragma()` | Function | Parse inline pragma comments |
| `EnumIOAuditRule` | Enum | Rule identifiers (`NET_CLIENT`, `ENV_ACCESS`, `FILE_IO`) |
| `ModelAuditResult` | Dataclass | Audit result with violations and metadata |
| `ModelIOAuditViolation` | Dataclass | Single violation with file, line, rule, message |
| `ModelWhitelistConfig` | Dataclass | Parsed whitelist configuration |
| `ModelWhitelistEntry` | Dataclass | Single whitelist entry |
| `ModelInlinePragma` | Dataclass | Parsed inline pragma |
| `IOAuditVisitor` | Class | AST visitor that detects I/O patterns |
| `IO_AUDIT_TARGETS` | List | Default target directories |

## Architecture

### Module Structure

```
audit/
  __init__.py          # Public API exports
  __main__.py          # CLI entry point
  io_audit.py          # Core implementation
  README.md            # This documentation
```

### AST Visitor Pattern

The audit uses Python's `ast` module to parse source files into Abstract Syntax Trees. The `IOAuditVisitor` class walks the tree and detects:

- **Import statements**: Checks for forbidden module imports
- **Function calls**: Detects `open()`, `os.getenv()`, `Path.read_text()`, etc.
- **Subscript access**: Catches `os.environ[...]` patterns
- **Comparisons**: Detects `"key" in os.environ` checks

### Why Two-Tier Whitelist?

The two-tier design serves specific purposes:

| Tier | Purpose | Visibility |
|------|---------|------------|
| **YAML Whitelist** | Central registry of all exceptions | High - visible in PRs, easy to audit |
| **Inline Pragmas** | Line-level granularity within approved files | Lower - scattered through code |

**Benefits**:
- **Central visibility**: All exceptions are documented in one YAML file
- **Code review coverage**: YAML changes require explicit approval
- **Prevents silent bypasses**: Developers cannot add pragmas without YAML approval
- **Convenience for approved files**: Once a file is approved, pragmas allow precise control

## FAQ

### Q: Why are my inline pragmas being ignored?

A: Inline pragmas only work for files listed in the YAML whitelist. Add your file to `tests/audit/io_audit_whitelist.yaml` first, then the pragmas will take effect.

### Q: What if I need to add I/O to a compute node temporarily?

A: Add a whitelist entry with a documented reason and reference a tracking ticket:
```yaml
- path: "src/nodes/my_compute_node.py"
  reason: "Temporary - pending refactor to Effect pattern - OMN-456"
  allowed_rules:
    - "env-access"
```

### Q: How do I see how many files are being scanned?

A: The output shows the files_scanned count:
```
No I/O violations found. (42 files scanned)
```
Or in JSON output, check the `files_scanned` field.

### Q: Can I exclude entire directories?

A: The audit only scans directories specified in targets (default: `IO_AUDIT_TARGETS`). Files with violations can be whitelisted in the YAML file using glob patterns like `path/to/excluded/*.py`.

### Q: Why is pathlib I/O detection heuristic-based?

A: The audit uses heuristics (variable naming patterns like `*_path`, import detection) to reduce false positives from custom objects that have methods named `read_text()` or `write_text()`. If pathlib is not imported in the file, these methods are not flagged.

### Q: What happens if the whitelist YAML has invalid rule IDs?

A: The audit will raise a `ValueError` with a message indicating the invalid rule ID and listing valid options (`net-client`, `env-access`, `file-io`).

### Q: What if a file has a syntax error?

A: The audit will raise a `SyntaxError` with the file path and error details. Fix the syntax error before running the audit.

## Related Documentation

- [CLAUDE.md](../../../CLAUDE.md) - Project-level I/O audit section
- [NAMING_CONVENTIONS.md](../../../docs/conventions/NAMING_CONVENTIONS.md) - ONEX naming standards
- [io_audit_whitelist.yaml](../../../../tests/audit/io_audit_whitelist.yaml) - Whitelist configuration
