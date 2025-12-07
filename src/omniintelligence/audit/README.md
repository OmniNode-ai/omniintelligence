# I/O Audit - ONEX Node Purity Enforcement

## Overview

The I/O audit tool enforces the **"pure compute / no I/O"** architectural invariant for ONEX nodes. It uses AST-based static analysis to detect forbidden I/O patterns in Python source files.

ONEX architecture separates nodes into distinct types:
- **Compute nodes**: Pure data transformation with no side effects
- **Effect nodes**: Handle all external I/O (Kafka, databases, HTTP, files)

This tool ensures compute nodes remain pure by detecting any I/O operations that should be delegated to effect nodes.

## Forbidden Patterns

| Rule ID | Description | Examples |
|---------|-------------|----------|
| `net-client` | Network/DB client imports | `confluent_kafka`, `httpx`, `asyncpg`, `qdrant_client`, `neo4j`, `aiofiles` |
| `env-access` | Environment variable access | `os.environ`, `os.getenv()`, `os.putenv()`, `os.environ.get()` |
| `file-io` | File system operations | `open()`, `Path.read_text()`, `Path.write_bytes()`, `FileHandler`, `RotatingFileHandler` |

## Usage

### Command Line

```bash
# Run audit on default targets (src/omniintelligence/nodes)
python -m omniintelligence.audit.io_audit

# Run with custom whitelist
python -m omniintelligence.audit.io_audit --whitelist tests/audit/io_audit_whitelist.yaml

# Run on specific directories
python -m omniintelligence.audit.io_audit src/omniintelligence/nodes src/other/path

# Using uv (recommended)
uv run python -m omniintelligence.audit.io_audit
```

### Pre-commit Integration

The I/O audit runs automatically as a pre-commit hook. Configuration in `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: io-audit
      name: I/O Audit (ONEX Node Purity)
      entry: uv run python -m omniintelligence.audit.io_audit
      language: system
      pass_filenames: false
      files: ^src/omniintelligence/nodes/.*\.py$
```

### CI Integration

The audit runs in GitHub Actions CI as part of the validation pipeline. See `.github/workflows/ci.yaml` for the CI job configuration.

## Whitelist Configuration

The I/O audit uses a **two-tier whitelist system** with a strict hierarchy:

1. **YAML Whitelist** (Primary) - Central configuration file
2. **Inline Pragmas** (Secondary) - Line-level granularity within whitelisted files

### YAML Whitelist Format

Location: `tests/audit/io_audit_whitelist.yaml`

```yaml
schema_version: "1.0.0"

files:
  # Specific file exception
  - path: "src/omniintelligence/nodes/my_effect_node.py"
    reason: "Effect node requires Kafka client for event publishing"
    allowed_rules:
      - "net-client"

  # Glob pattern for multiple files
  - path: "src/omniintelligence/nodes/legacy_*.py"
    reason: "Legacy nodes pending refactor - tracked in OMN-XXX"
    allowed_rules:
      - "env-access"
      - "file-io"
```

### Inline Pragma Format

```python
# io-audit: ignore-next-line <rule-id>
```

Where `<rule-id>` is one of: `net-client`, `env-access`, `file-io`

### CRITICAL: Pragma Prerequisite

**Inline pragmas ONLY work for files already listed in the YAML whitelist.** This is by design.

If you add a pragma to a file NOT in the YAML whitelist, **it will be silently ignored**.

### Example: Correct Two-Tier Usage

**Step 1**: Add file to YAML whitelist

```yaml
# tests/audit/io_audit_whitelist.yaml
files:
  - path: "src/omniintelligence/nodes/intelligence_adapter_effect.py"
    reason: "Effect node requires Kafka client"
    allowed_rules:
      - "net-client"
```

**Step 2**: Use inline pragma for specific lines

```python
# src/omniintelligence/nodes/intelligence_adapter_effect.py

# io-audit: ignore-next-line net-client
from confluent_kafka import Producer  # Whitelisted by pragma

# io-audit: ignore-next-line net-client
from confluent_kafka import Consumer  # Whitelisted by pragma
```

### Example: INCORRECT Usage (Pragma Ignored)

```python
# File NOT in YAML whitelist - pragma has NO effect!
# io-audit: ignore-next-line net-client
from confluent_kafka import Producer  # VIOLATION STILL REPORTED
```

## Adding Exceptions

Follow these steps to whitelist a file:

### Step 1: Evaluate the Exception

Before adding an exception, verify:
- Is this truly an effect node that requires I/O?
- Can the I/O be delegated to a dedicated effect node instead?
- Is the exception documented with a ticket number if it's technical debt?

### Step 2: Add to YAML Whitelist

Edit `tests/audit/io_audit_whitelist.yaml`:

```yaml
files:
  - path: "src/omniintelligence/nodes/your_node.py"
    reason: "Brief explanation - include ticket number if applicable"
    allowed_rules:
      - "net-client"  # Only include rules actually needed
```

### Step 3: Add Inline Pragmas (Optional)

For fine-grained control, add pragmas to specific lines:

```python
# io-audit: ignore-next-line net-client
from httpx import AsyncClient
```

### Step 4: Verify

Run the audit to confirm the exception works:

```bash
uv run python -m omniintelligence.audit.io_audit
```

### Security Considerations

- **Minimize exceptions**: Only whitelist what is strictly necessary
- **Document reasons**: Every exception must have a documented reason
- **Use specific rules**: Don't whitelist all rules when only one is needed
- **Prefer YAML over pragmas**: YAML changes are visible in code review
- **Track technical debt**: Include ticket numbers for legacy exceptions

## Architecture

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

### Key Components

| Component | Description |
|-----------|-------------|
| `IOAuditVisitor` | AST visitor that collects violations |
| `ModelIOAuditViolation` | Data class representing a single violation |
| `ModelWhitelistConfig` | Parsed YAML whitelist configuration |
| `audit_file()` | Audit a single Python file |
| `run_audit()` | Run full audit on target directories |
| `apply_whitelist()` | Filter violations against whitelist |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - no violations found |
| `1` | Violations detected |
| `2` | File/configuration error |

## Related Documentation

- [CLAUDE.md](../../../CLAUDE.md) - Project-level I/O audit section
- [NAMING_CONVENTIONS.md](../../../docs/conventions/NAMING_CONVENTIONS.md) - ONEX naming standards
