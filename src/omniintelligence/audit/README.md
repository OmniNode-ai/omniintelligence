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
| `--whitelist PATH` | `-w PATH` | Path to whitelist YAML file (default: `tests/audit/io_audit_whitelist.yaml`) |
| `--verbose` | `-v` | Enable verbose output with additional context |
| `--json` | - | Output in JSON format for CI integration |
| `--dry-run` | `-n` | Show what files would be scanned without running the audit |
| `--metrics` | `-m` | Include detailed metrics (timing, whitelist stats, violations by rule) |

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
      "message": "Forbidden import: confluent_kafka",
      "suggestion": "Create a separate Effect node for Kafka operations:\n  # node_kafka_publisher_effect.py\n  class NodeKafkaPublisherEffect:\n      def __init__(self, producer: Producer) -> None:\n          self._producer = producer  # Injected dependency"
    },
    {
      "file": "src/omniintelligence/nodes/bad_node.py",
      "line": 12,
      "column": 4,
      "rule": "env-access",
      "message": "Forbidden call: os.getenv()",
      "suggestion": "Inject configuration via constructor:\n  from pydantic_settings import BaseSettings\n\n  class YourConfig(BaseSettings):\n      your_setting: str\n\n  class NodeYourCompute:\n      def __init__(self, config: YourConfig) -> None:\n          self._config = config  # Injected, not read from env"
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

### Dry-Run Output

```
DRY RUN - No audit performed

Target directories: src/omniintelligence/nodes

Files that would be scanned (15 files):
  - /path/to/node1.py
  - /path/to/node2.py
  ...

Whitelist entries loaded (2 entries):
  - tests/audit/fixtures/io/whitelisted_node.py [env-access, file-io]
  - src/omniintelligence/nodes/legacy_*.py [env-access]
```

### Metrics Output

```
src/omniintelligence/nodes/bad_node.py:
  Line 5: [net-client] Forbidden import: confluent_kafka
  -> Hints: Move to an Effect node or inject client via dependency injection.

Summary: 1 violation(s) in 1 file(s) (15 files scanned)

Metrics:
  Files scanned: 15
  Duration: 0.05s
  Violations found: 3
  Whitelisted (YAML): 1
  Whitelisted (pragma): 1
  Final violations: 1
  By rule:
    net-client: 2
    env-access: 1
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

## Troubleshooting

This section covers common issues and their solutions.

### Inline Pragmas Being Ignored

**Problem**: You added an inline pragma (`# io-audit: ignore-next-line <rule>`) but the violation is still reported.

**Cause**: The file is not listed in the YAML whitelist. Pragmas are ONLY honored for files already in the YAML whitelist.

**Solution**:
1. Add the file to `tests/audit/io_audit_whitelist.yaml`:
   ```yaml
   files:
     - path: "path/to/your/file.py"
       reason: "Document why this file needs I/O exceptions"
       allowed_rules:
         - "net-client"  # Add only the rules you need
   ```
2. Now your inline pragma will be honored

**Why this design**: This ensures all I/O exceptions are centrally tracked and visible in code reviews.

### Invalid Rule ID Error

**Problem**: Error when loading whitelist: `Invalid rule ID 'xxx' in whitelist entry`

**Cause**: Typo in rule ID or using an unsupported rule.

**Solution**: Use only valid rule IDs:
- `net-client` - Network/DB client imports
- `env-access` - Environment variable access
- `file-io` - File system operations

### Empty Reason Field Error

**Problem**: Whitelist validation fails with: `Empty 'reason' field in whitelist entry`

**Cause**: Missing or empty `reason` field in a whitelist entry.

**Solution**: All whitelist entries require a non-empty `reason` field:
```yaml
# WRONG - will fail validation
- path: "some_file.py"
  allowed_rules: ["net-client"]

# CORRECT
- path: "some_file.py"
  reason: "Effect node for Kafka publishing"
  allowed_rules: ["net-client"]
```

### False Positive on Custom Class Method

**Problem**: Audit reports a violation on a method like `my_obj.read_text()` that is not pathlib.

**Cause**: The audit uses heuristics to detect Path-like objects.

**How detection works**: The audit only flags `read_text`/`write_text` etc. when:
1. `pathlib` or `Path` is imported in the file, AND
2. The receiver looks like a Path object (variable named `path`, `file_path`, `*_path`, etc.)

**Solutions**:
- Rename your variable to avoid Path-like names (e.g., `reader` instead of `file_path`)
- If the heuristic still triggers, add to whitelist with documented reason

### Syntax Error in File

**Problem**: Audit fails with Python syntax error.

**Cause**: The file has invalid Python syntax that prevents AST parsing.

**Solution**: Fix the syntax error in the file first. Run `python -m py_compile your_file.py` to check for syntax errors.

### File Not Found Error

**Problem**: `Error: File not found: /path/to/missing.py`

**Cause**: The specified file or directory does not exist.

**Solution**: Verify the path exists:
```bash
ls -la /path/to/file.py
```

### Unicode Decode Error

**Problem**: `File 'x.py' contains non-UTF8 characters`

**Cause**: The file uses an encoding other than UTF-8.

**Solution**: Convert the file to UTF-8 encoding:
```bash
# Check current encoding
file -i your_file.py

# Convert to UTF-8
iconv -f ORIGINAL_ENCODING -t UTF-8 your_file.py > your_file_utf8.py
mv your_file_utf8.py your_file.py
```

### Dry Run Shows Unexpected Files

**Problem**: `--dry-run` shows files you didn't expect to be scanned.

**Cause**: The default target directories include more files than expected.

**Solution**: Explicitly specify the directories to scan:
```bash
python -m omniintelligence.audit src/omniintelligence/nodes --dry-run
```

### Whitelist Not Being Applied

**Problem**: Violations are reported even though you added a whitelist entry.

**Possible causes**:
1. **Path mismatch**: The path pattern doesn't match the file
2. **Wrong rules**: The `allowed_rules` list doesn't include the violated rule
3. **Glob pattern issue**: Your pattern syntax is incorrect

**Solution**:
1. Run with `--dry-run` to see whitelist entries loaded
2. Check that the path matches exactly (use glob patterns like `**/file.py` for flexibility)
3. Verify the rule ID in `allowed_rules` matches the violation

### Performance Issues

**Problem**: Audit takes too long on large codebases.

**Solution**:
1. Narrow the target directories:
   ```bash
   python -m omniintelligence.audit src/specific/path
   ```
2. Use `--dry-run` first to see file count:
   ```bash
   python -m omniintelligence.audit --dry-run
   ```
3. Check for symlink loops (the audit handles these gracefully but they may affect discovery time)

## Auto-Remediation Suggestions

When violations are found, the audit provides context-specific suggestions with code examples.

### Network Client Suggestions

For Kafka client violations:
```
Forbidden import: confluent_kafka
  -> Hint: Move to an Effect node or inject client via dependency injection.
  -> Suggestion:
     Create a separate Effect node for Kafka operations:
       # node_kafka_publisher_effect.py
       class NodeKafkaPublisherEffect:
           def __init__(self, producer: Producer) -> None:
               self._producer = producer  # Injected dependency
```

For HTTP client violations:
```
Forbidden import: httpx
  -> Suggestion:
     Create a separate Effect node for HTTP operations:
       # node_http_client_effect.py
       class NodeHttpClientEffect:
           def __init__(self, client: httpx.AsyncClient) -> None:
               self._client = client  # Injected dependency
```

### Environment Variable Suggestions

For `os.getenv()` or `os.environ` access:
```
Forbidden call: os.getenv()
  -> Hint: Pass configuration via constructor parameters instead of reading env vars.
  -> Suggestion:
     Inject configuration via constructor:
       from pydantic_settings import BaseSettings

       class YourConfig(BaseSettings):
           your_setting: str

       class NodeYourCompute:
           def __init__(self, config: YourConfig) -> None:
               self._config = config  # Injected, not read from env
```

### File I/O Suggestions

For `open()` violations:
```
Forbidden call: open()
  -> Hint: Move file I/O to an Effect node or pass file content as input parameter.
  -> Suggestion:
     Pass file content as a parameter instead of reading directly:
       # Before (violation):
       def process(self, file_path: str) -> Result:
           with open(file_path) as f:
               content = f.read()

       # After (pure compute):
       def process(self, content: str) -> Result:
           # Content passed in, no I/O in compute node
```

For `Path.read_text()` violations:
```
Forbidden call: Path.read_text()
  -> Suggestion:
     Pass file content as a parameter instead of using Path.read_text():
       # Before (violation):
       def process(self, path: Path) -> Result:
           content = path.read_text()

       # After (pure compute):
       def process(self, content: str) -> Result:
           # Content passed in, no I/O in compute node
```

For logging FileHandler violations:
```
Forbidden call: FileHandler()
  -> Suggestion:
     Use structured logging without file handlers in compute nodes:
       # Configure logging in Effect node or entry point, not in compute
       # Compute nodes should use standard logging without file handlers:
       import logging
       logger = logging.getLogger(__name__)
       logger.info('Message')  # Handler configured externally
```

## FAQ

### Q: Why are my inline pragmas being ignored?

A: Inline pragmas only work for files listed in the YAML whitelist. Add your file to `tests/audit/io_audit_whitelist.yaml` first, then the pragmas will take effect. See the Troubleshooting section for details.

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
Or in JSON output, check the `files_scanned` field. Use `--dry-run` to preview files without running the audit.

### Q: Can I exclude entire directories?

A: The audit only scans directories specified in targets (default: `IO_AUDIT_TARGETS`). Files with violations can be whitelisted in the YAML file using glob patterns like `path/to/excluded/**/*.py`.

### Q: Why is pathlib I/O detection heuristic-based?

A: The audit uses heuristics (variable naming patterns like `*_path`, import detection) to reduce false positives from custom objects that have methods named `read_text()` or `write_text()`. If pathlib is not imported in the file, these methods are not flagged. See Troubleshooting for handling false positives.

### Q: What happens if the whitelist YAML has invalid rule IDs?

A: The audit will raise a `ValueError` with a message indicating the invalid rule ID and listing valid options (`net-client`, `env-access`, `file-io`).

### Q: What if a file has a syntax error?

A: The audit will raise a `SyntaxError` with the file path and error details. Fix the syntax error before running the audit.

## Related Documentation

- [CLAUDE.md](../../../CLAUDE.md) - Project-level I/O audit section
- [NAMING_CONVENTIONS.md](../../../docs/conventions/NAMING_CONVENTIONS.md) - ONEX naming standards
- [io_audit_whitelist.yaml](../../../../tests/audit/io_audit_whitelist.yaml) - Whitelist configuration
