# Multi-Repository Tree Stamping Setup Guide

**Version**: 1.0.0
**Last Updated**: 2025-10-27
**Status**: Production Ready

## Overview

This guide explains how to configure and manage multiple repositories for automated tree stamping, intelligence generation, and vector indexing using the Archon Intelligence Platform.

**Key Features**:
- ✅ Centralized configuration for multiple repositories
- ✅ Per-repository settings with global defaults
- ✅ File filtering (include/exclude patterns)
- ✅ Git hooks for incremental stamping
- ✅ Bulk ingestion for initial indexing
- ✅ Repository discovery and auto-detection
- ✅ Configuration validation and testing
- ✅ Team-shareable configuration

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration Structure](#configuration-structure)
3. [Setup Instructions](#setup-instructions)
4. [Repository Configuration](#repository-configuration)
5. [File Filtering](#file-filtering)
6. [Git Hooks Integration](#git-hooks-integration)
7. [Bulk Ingestion](#bulk-ingestion)
8. [Repository Discovery](#repository-discovery)
9. [Configuration Management](#configuration-management)
10. [Advanced Features](#advanced-features)
11. [Troubleshooting](#troubleshooting)
12. [Best Practices](#best-practices)

---

## Quick Start

### 1. Copy Example Configuration

```bash
# Configuration file location
cp config/tree_stamping_repos.yaml config/my_repos.yaml
```

### 2. Edit Configuration

Edit `config/my_repos.yaml` and add your repositories:

```yaml
repositories:
  - name: "my-project"
    enabled: true
    path: "/path/to/my/project"
    filters:
      include: ["**/*.py", "**/*.md"]
      exclude: ["**/venv/**", "**/.git/**"]
```

### 3. Validate Configuration

```bash
python scripts/tree_stamping_config_cli.py validate --config config/my_repos.yaml
```

### 4. Test Repository

```bash
python scripts/tree_stamping_config_cli.py test my-project --config config/my_repos.yaml
```

### 5. Run Bulk Ingestion

```bash
python scripts/bulk_ingest_repositories.py --config config/my_repos.yaml
```

---

## Configuration Structure

The configuration file is structured in YAML format with the following main sections:

```yaml
schema_version: "1.0.0"
config_type: "tree_stamping_repositories"

global:          # Global settings (apply to all repositories)
  kafka:         # Event bus configuration
  qdrant:        # Vector database configuration
  processing:    # Processing settings
  intelligence:  # Intelligence generation settings
  indexing:      # Indexing settings
  logging:       # Logging configuration

repositories:    # List of repository configurations
  - name: "..."
    enabled: true
    path: "..."
    filters: {...}
    # ... repository-specific settings

discovery:       # Repository auto-discovery (optional)
validation:      # Validation rules
performance:     # Performance tuning
error_handling:  # Error handling configuration
monitoring:      # Monitoring and metrics
integration:     # Archon service integration
security:        # Security settings
features:        # Feature flags
```

### Configuration Hierarchy

Settings are applied in this order (later overrides earlier):

1. **Global defaults** (hardcoded in code)
2. **Global configuration** (from `global:` section)
3. **Repository-specific overrides** (from individual repository config)

Example:

```yaml
global:
  processing:
    batch_size: 50  # Global default

repositories:
  - name: "large-repo"
    processing:
      batch_size: 200  # Override for this repo only
```

---

## Setup Instructions

### Prerequisites

1. **Archon Intelligence Platform** running (Docker Compose)
2. **Python 3.11+** installed
3. **Poetry** (optional, for dependency management)
4. **Git** installed (for git hooks)

### Step-by-Step Setup

#### 1. Install Dependencies

```bash
# Using Poetry (recommended)
poetry install

# Or using pip
pip install pyyaml pydantic
```

#### 2. Create Configuration File

```bash
# Copy example configuration
cp config/tree_stamping_repos.yaml config/my_repos.yaml

# Edit configuration
vim config/my_repos.yaml
```

#### 3. Configure Global Settings

Edit the `global:` section to match your environment:

```yaml
global:
  # Kafka/Event Bus (usually no changes needed)
  kafka:
    bootstrap_servers: "omninode-bridge-redpanda:9092"  # Docker internal
    # bootstrap_servers: "localhost:29092"              # Host machine

  # Qdrant Vector Database
  qdrant:
    url: "http://qdrant:6333"        # Docker internal
    # url: "http://localhost:6333"   # Host machine
    collection: "file_locations"

  # Processing settings
  processing:
    batch_size: 50
    max_workers: 4
    timeout_seconds: 300
```

#### 4. Add Repositories

Add your repositories to the `repositories:` section:

```yaml
repositories:
  - name: "my-project"
    enabled: true
    description: "My awesome project"
    path: "/Volumes/PRO-G40/Code/my-project"
    path_type: "absolute"

    filters:
      include:
        - "**/*.py"
        - "**/*.md"
        - "**/*.yaml"
      exclude:
        - "**/node_modules/**"
        - "**/venv/**"
        - "**/__pycache__/**"
        - "**/.git/**"
      max_file_size: 1048576  # 1MB

    git_hooks:
      enabled: true
      pre_commit: true
      incremental: true

    metadata:
      team: "backend"
      language: "python"
      priority: "high"
```

#### 5. Validate Configuration

```bash
python scripts/tree_stamping_config_cli.py validate --config config/my_repos.yaml
```

Expected output:

```
================================================================================
                          Configuration Validation
================================================================================

ℹ Configuration loaded successfully from: config/my_repos.yaml
ℹ Schema version: 1.0.0
ℹ Config type: tree_stamping_repositories

ℹ Running validation checks...

Validation Checks:
  ✓ Repository path exists: my-project

Summary:
  Total repositories: 1
  Enabled repositories: 1
  Validation checks: 1
  Warnings: 0
  Errors: 0

✓ Configuration is valid!
```

#### 6. Test Repository Configuration

```bash
python scripts/tree_stamping_config_cli.py test my-project --config config/my_repos.yaml
```

Expected output:

```
================================================================================
                       Testing Repository: my-project
================================================================================

ℹ Test 1: Path exists...
✓   Path exists: /Volumes/PRO-G40/Code/my-project

ℹ Test 2: Is directory...
✓   Path is a directory

ℹ Test 3: Is git repository...
✓   Git repository detected

ℹ Test 4: File count estimation...
✓   Total files: 1,234

ℹ Test 5: Filter matching...
ℹ   Include patterns: 3
    - **/*.py
    - **/*.md
    - **/*.yaml

ℹ Test 6: Effective configuration...
✓   Configuration merged successfully
ℹ   Batch size: 50
ℹ   Max workers: 4

✓ All tests passed!
```

---

## Repository Configuration

### Required Fields

```yaml
repositories:
  - name: "my-repo"       # Required: Unique identifier
    path: "/path/to/repo" # Required: Absolute path to repository
```

### Optional Fields

```yaml
repositories:
  - name: "my-repo"
    enabled: true                     # Enable/disable (default: true)
    description: "My repository"      # Human-readable description
    path_type: "absolute"             # "absolute" or "relative"

    filters:                          # File filtering (see below)
      include: ["**/*.py"]
      exclude: ["**/venv/**"]
      max_file_size: 1048576
      min_file_size: 10

    processing:                       # Override global processing settings
      batch_size: 100
      max_workers: 6
      timeout_seconds: 600

    intelligence:                     # Override global intelligence settings
      quality_scoring: true
      onex_classification: true
      semantic_analysis: true

    indexing:                         # Override global indexing settings
      vector_indexing: true
      graph_indexing: true
      cache_warming: true

    git_hooks:                        # Git hooks configuration
      enabled: true
      pre_commit: true
      pre_push: false
      incremental: true
      fail_on_error: false

    schedule:                         # Periodic re-indexing (optional)
      enabled: false
      cron: "0 2 * * *"              # Daily at 2 AM
      force_reindex: false

    metadata:                         # Custom metadata
      team: "backend"
      language: "python"
      framework: "fastapi"
      priority: "high"
```

### Path Configuration

#### Absolute Paths (Recommended)

```yaml
repositories:
  - name: "my-repo"
    path: "/Volumes/PRO-G40/Code/my-repo"
    path_type: "absolute"
```

#### Environment Variables

Use environment variable interpolation for flexibility:

```yaml
repositories:
  - name: "my-repo"
    path: "${CODE_DIR}/my-repo"  # Expands to value of $CODE_DIR
    path: "${HOME}/Code/my-repo" # Expands to user home directory
```

Set environment variables:

```bash
export CODE_DIR="/Volumes/PRO-G40/Code"
```

#### Home Directory Expansion

Tilde (`~`) is automatically expanded:

```yaml
repositories:
  - name: "my-repo"
    path: "~/Code/my-repo"  # Expands to /Users/username/Code/my-repo
```

---

## File Filtering

### Include Patterns

Glob patterns to include files:

```yaml
filters:
  include:
    # Python files
    - "**/*.py"

    # Documentation
    - "**/*.md"
    - "**/*.rst"

    # Configuration
    - "**/*.yaml"
    - "**/*.yml"
    - "**/*.json"
    - "**/*.toml"

    # TypeScript/JavaScript
    - "**/*.ts"
    - "**/*.tsx"
    - "**/*.js"
    - "**/*.jsx"
```

### Exclude Patterns

Glob patterns to exclude files/directories:

```yaml
filters:
  exclude:
    # Dependencies
    - "**/node_modules/**"
    - "**/venv/**"
    - "**/.venv/**"
    - "**/vendor/**"

    # Build artifacts
    - "**/dist/**"
    - "**/build/**"
    - "**/__pycache__/**"
    - "**/*.pyc"
    - "**/*.pyo"
    - "**/.pytest_cache/**"

    # Version control
    - "**/.git/**"
    - "**/.github/**"
    - "**/.gitlab/**"

    # IDE
    - "**/.vscode/**"
    - "**/.idea/**"
    - "**/*.swp"

    # Coverage
    - "**/coverage/**"
    - "**/.coverage"
    - "**/htmlcov/**"
```

### File Size Limits

Prevent processing overly large or small files:

```yaml
filters:
  max_file_size: 1048576   # 1MB in bytes (adjust as needed)
  min_file_size: 10        # 10 bytes (exclude empty files)
```

### Pattern Syntax

Uses standard glob syntax:

- `*` - Matches any characters except `/`
- `**` - Matches any characters including `/` (recursive)
- `?` - Matches any single character
- `[abc]` - Matches any character in brackets
- `[!abc]` - Matches any character not in brackets

**Examples**:

```yaml
filters:
  include:
    - "**/*.py"                    # All Python files recursively
    - "src/**/*.py"                # Python files under src/ only
    - "tests/test_*.py"            # Test files in tests/ directory
    - "**/{models,schemas}/*.py"   # Files in models/ or schemas/ directories
```

---

## Git Hooks Integration

### Overview

Git hooks enable automatic incremental stamping when code changes:

- **Pre-commit**: Stamp files before commit
- **Pre-push**: Stamp files before push
- **Post-commit**: Stamp files after commit

### Enabling Git Hooks

```yaml
repositories:
  - name: "my-repo"
    git_hooks:
      enabled: true           # Enable git hooks
      pre_commit: true        # Enable pre-commit hook
      pre_push: false         # Disable pre-push hook
      post_commit: false      # Disable post-commit hook
      hooks_path: ".git/hooks"
      incremental: true       # Only process changed files
      fail_on_error: false    # Don't fail commit on errors
```

### Installation

#### Automatic Installation (Recommended)

```bash
python scripts/install_git_hooks.py --config config/my_repos.yaml
```

This will:
1. Create hook scripts in `.git/hooks/`
2. Make them executable
3. Configure them to use your configuration

#### Manual Installation

1. Create pre-commit hook:

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Get list of changed files
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

if [ -z "$CHANGED_FILES" ]; then
    exit 0
fi

# Run tree stamping on changed files
python scripts/stamp_changed_files.py --config config/my_repos.yaml --files "$CHANGED_FILES"

exit $?
```

2. Make executable:

```bash
chmod +x .git/hooks/pre-commit
```

### Incremental Mode

When `incremental: true`, only changed files are processed:

```yaml
git_hooks:
  incremental: true  # Only process git diff files
```

**Benefits**:
- ⚡ Fast commits (only process changed files)
- 📉 Reduced load on Archon services
- ✅ Always up-to-date intelligence

### Error Handling

Control whether commits fail on stamping errors:

```yaml
git_hooks:
  fail_on_error: false  # Allow commits even if stamping fails
```

**Recommendations**:
- `fail_on_error: false` - For development (don't block commits)
- `fail_on_error: true` - For CI/CD (enforce quality gates)

---

## Bulk Ingestion

### Overview

Bulk ingestion indexes entire repositories in batches, useful for:

- Initial indexing of new repositories
- Re-indexing after configuration changes
- Full refresh of vector database

### Running Bulk Ingestion

#### Basic Usage

```bash
# Ingest all enabled repositories
python scripts/bulk_ingest_repositories.py --config config/my_repos.yaml
```

#### Ingest Specific Repository

```bash
python scripts/bulk_ingest_repositories.py \
  --config config/my_repos.yaml \
  --repository my-project
```

#### Force Re-index

```bash
python scripts/bulk_ingest_repositories.py \
  --config config/my_repos.yaml \
  --force
```

#### Dry Run

```bash
python scripts/bulk_ingest_repositories.py \
  --config config/my_repos.yaml \
  --dry-run
```

### Performance Tuning

Adjust batch size and workers for optimal performance:

```yaml
repositories:
  - name: "large-repo"
    processing:
      batch_size: 200      # Larger batches = fewer Kafka events
      max_workers: 8       # More workers = faster processing
      timeout_seconds: 600 # Longer timeout for large repos
```

**Guidelines**:
- **Small repos** (<1,000 files): batch_size=50, max_workers=4
- **Medium repos** (1,000-10,000 files): batch_size=100, max_workers=6
- **Large repos** (>10,000 files): batch_size=200, max_workers=8

### Monitoring Progress

Enable progress reporting:

```yaml
performance:
  progress:
    enabled: true
    report_interval: 10  # Report every 10 files
```

Output:

```
Processing repository: my-project
[=====>    ] 50% (500/1000 files) - ETA: 2m 30s
```

---

## Repository Discovery

### Overview

Automatically discover git repositories in specified directories.

### Enabling Discovery

```yaml
discovery:
  enabled: true

  # Directories to scan
  scan_paths:
    - "/Volumes/PRO-G40/Code"
    - "/Users/jonah/Code"

  # Discovery filters
  filters:
    required_markers:
      - ".git"              # Must be git repository
      - "pyproject.toml"    # Must have pyproject.toml (Python projects)

    exclude_patterns:
      - "**/archived/**"
      - "**/deprecated/**"
      - "**/temp/**"

    max_depth: 3           # Max recursion depth

  # Auto-add discovered repositories
  auto_add: false          # Require manual enablement

  # Default settings for discovered repos
  defaults:
    enabled: false
    filters:
      include: ["**/*.py", "**/*.md"]
      exclude: ["**/venv/**", "**/.git/**"]
    git_hooks:
      enabled: false
```

### Running Discovery

```bash
python scripts/tree_stamping_config_cli.py discover --config config/my_repos.yaml
```

Output:

```
================================================================================
                          Repository Discovery
================================================================================

ℹ Scanning for repositories...
ℹ Scan paths: /Volumes/PRO-G40/Code, /Users/jonah/Code

✓ Discovered 5 repositories:

  ● my-project-1
    Path: /Volumes/PRO-G40/Code/my-project-1
    Discovered from: /Volumes/PRO-G40/Code

  ● my-project-2
    Path: /Volumes/PRO-G40/Code/my-project-2
    Discovered from: /Volumes/PRO-G40/Code

  ...
```

### Auto-Add Discovered Repositories

Set `auto_add: true` to automatically add discovered repositories to configuration:

```yaml
discovery:
  auto_add: true  # Automatically add discovered repos
```

**Warning**: Discovered repositories are added as **disabled** by default. You must manually enable them.

---

## Configuration Management

### CLI Commands

The configuration CLI provides comprehensive management:

```bash
# Validate configuration
python scripts/tree_stamping_config_cli.py validate --config config/my_repos.yaml

# List repositories
python scripts/tree_stamping_config_cli.py list --config config/my_repos.yaml

# Show repository details
python scripts/tree_stamping_config_cli.py show my-project --config config/my_repos.yaml

# Show effective configuration (with overrides)
python scripts/tree_stamping_config_cli.py show my-project --effective --config config/my_repos.yaml

# Discover repositories
python scripts/tree_stamping_config_cli.py discover --config config/my_repos.yaml

# Test repository
python scripts/tree_stamping_config_cli.py test my-project --config config/my_repos.yaml

# Export configuration
python scripts/tree_stamping_config_cli.py export --output exported.yaml --config config/my_repos.yaml
```

### Validation

Configuration validation checks:

✅ **Path validation** - Paths exist and are directories
✅ **Path conflicts** - No duplicate paths
✅ **Repository names** - Unique repository names
✅ **File filters** - Valid glob patterns
✅ **File size ranges** - max_file_size > min_file_size
✅ **Cron expressions** - Valid cron syntax (if scheduling enabled)

Run validation:

```bash
python scripts/tree_stamping_config_cli.py validate --config config/my_repos.yaml
```

### Testing

Test individual repository configurations:

```bash
python scripts/tree_stamping_config_cli.py test my-project --config config/my_repos.yaml
```

Tests performed:

1. ✅ Path exists
2. ✅ Is directory
3. ✅ Is git repository (warning if not)
4. ✅ File count estimation
5. ✅ Filter matching
6. ✅ Effective configuration merging

### Exporting/Importing

#### Export Configuration

```bash
python scripts/tree_stamping_config_cli.py export \
  --output backup.yaml \
  --config config/my_repos.yaml
```

#### Import Configuration

Simply use the exported file:

```bash
python scripts/tree_stamping_config_cli.py validate --config backup.yaml
```

---

## Advanced Features

### Environment Variable Interpolation

Use environment variables in configuration:

```yaml
global:
  kafka:
    bootstrap_servers: "${KAFKA_SERVERS:omninode-bridge-redpanda:9092}"
  qdrant:
    url: "${QDRANT_URL:http://qdrant:6333}"

repositories:
  - name: "my-repo"
    path: "${CODE_DIR}/my-repo"
```

Set environment variables:

```bash
export KAFKA_SERVERS="localhost:29092"
export QDRANT_URL="http://localhost:6333"
export CODE_DIR="/Volumes/PRO-G40/Code"
```

### Repository-Specific Overrides

Override global settings per repository:

```yaml
global:
  processing:
    batch_size: 50
    max_workers: 4

repositories:
  # Small repository - use defaults
  - name: "small-repo"
    path: "/path/to/small"

  # Large repository - override settings
  - name: "large-repo"
    path: "/path/to/large"
    processing:
      batch_size: 200   # Override: larger batches
      max_workers: 8    # Override: more workers
```

### Scheduled Re-indexing

Schedule periodic full re-indexing:

```yaml
repositories:
  - name: "my-repo"
    schedule:
      enabled: true
      cron: "0 2 * * *"      # Daily at 2 AM
      force_reindex: true    # Force full reindex
```

Cron syntax:

```
┌─────── minute (0-59)
│ ┌───── hour (0-23)
│ │ ┌─── day of month (1-31)
│ │ │ ┌─ month (1-12)
│ │ │ │ ┌ day of week (0-6, Sunday=0)
│ │ │ │ │
* * * * *
```

Examples:

```yaml
cron: "0 2 * * *"       # Daily at 2 AM
cron: "0 2 * * 0"       # Weekly on Sunday at 2 AM
cron: "0 2 1 * *"       # Monthly on 1st at 2 AM
cron: "*/15 * * * *"    # Every 15 minutes
```

### Custom Metadata

Add custom metadata for organization:

```yaml
repositories:
  - name: "my-repo"
    metadata:
      team: "backend"
      language: "python"
      framework: "fastapi"
      priority: "high"
      contact: "team@example.com"
      slack_channel: "#backend-team"
      jira_project: "BACK"
      cost_center: "ENG-001"
```

Use metadata for:
- Filtering/querying repositories
- Team ownership tracking
- Priority-based processing
- Integration with other tools

### Feature Flags

Enable/disable features globally:

```yaml
features:
  enable_bulk_ingestion: true
  enable_git_hooks: true
  enable_incremental_stamping: true
  enable_cache_warming: true
  enable_quality_scoring: true
  enable_onex_classification: true
  enable_semantic_analysis: true
  enable_graph_indexing: true

  experimental:
    enable_parallel_stamping: true      # Safe to enable
    enable_smart_batching: false        # Experimental
    enable_predictive_caching: false    # Experimental
```

---

## Troubleshooting

### Configuration Not Loading

**Problem**: Configuration file not found or invalid

**Solution**:

1. Check file path:

```bash
ls -la config/tree_stamping_repos.yaml
```

2. Validate YAML syntax:

```bash
python -c "import yaml; yaml.safe_load(open('config/tree_stamping_repos.yaml'))"
```

3. Run validation:

```bash
python scripts/tree_stamping_config_cli.py validate --config config/tree_stamping_repos.yaml
```

### Repository Path Not Found

**Problem**: "Repository path does not exist" error

**Solution**:

1. Check path exists:

```bash
ls -la /path/to/repository
```

2. Check for typos in configuration
3. Use absolute paths (recommended)
4. Expand environment variables: `${CODE_DIR}/repo`
5. Expand home directory: `~/Code/repo`

### File Filters Not Working

**Problem**: Files not being included/excluded correctly

**Solution**:

1. Test glob patterns:

```python
from pathlib import Path
import fnmatch

pattern = "**/*.py"
files = list(Path("/path/to/repo").rglob("*.py"))
print(f"Matched {len(files)} files")
```

2. Check pattern syntax (use `**` for recursive)
3. Check exclude patterns (exclude takes precedence)
4. Verify file extensions match

### Git Hooks Not Triggering

**Problem**: Git hooks not running on commit

**Solution**:

1. Check hooks are installed:

```bash
ls -la .git/hooks/pre-commit
```

2. Check hooks are executable:

```bash
chmod +x .git/hooks/pre-commit
```

3. Test hook manually:

```bash
.git/hooks/pre-commit
```

4. Check hook configuration:

```yaml
git_hooks:
  enabled: true
  pre_commit: true
```

### Kafka Connection Failed

**Problem**: "Failed to connect to Kafka" error

**Solution**:

1. Check Kafka is running:

```bash
docker ps | grep redpanda
```

2. Check Kafka connectivity:

```bash
docker exec omninode-bridge-redpanda rpk cluster info
```

3. Verify bootstrap servers:

```yaml
global:
  kafka:
    bootstrap_servers: "omninode-bridge-redpanda:9092"  # Docker
    # bootstrap_servers: "localhost:29092"              # Host
```

4. Check network (Docker network vs host network)

### Qdrant Connection Failed

**Problem**: "Failed to connect to Qdrant" error

**Solution**:

1. Check Qdrant is running:

```bash
docker ps | grep qdrant
```

2. Check Qdrant health:

```bash
curl http://localhost:6333/health
```

3. Verify Qdrant URL:

```yaml
global:
  qdrant:
    url: "http://qdrant:6333"       # Docker
    # url: "http://localhost:6333"  # Host
```

### Performance Issues

**Problem**: Bulk ingestion too slow

**Solution**:

1. Increase batch size:

```yaml
processing:
  batch_size: 200  # Larger batches = fewer events
```

2. Increase workers:

```yaml
processing:
  max_workers: 8  # More parallelism
```

3. Reduce file filters:

```yaml
filters:
  max_file_size: 524288  # 512KB (exclude large files)
```

4. Disable features:

```yaml
intelligence:
  semantic_analysis: false  # Disable expensive analysis
```

---

## Best Practices

### Configuration Organization

✅ **DO**:
- Use separate config files per environment (dev/staging/prod)
- Use environment variables for sensitive data
- Use absolute paths for reliability
- Document custom metadata fields
- Version control configuration files
- Use descriptive repository names

❌ **DON'T**:
- Hardcode credentials in configuration
- Use relative paths (unless necessary)
- Mix repositories from different environments
- Leave disabled repositories in configuration
- Share configuration with hardcoded paths

### File Filtering

✅ **DO**:
- Exclude build artifacts (`dist/`, `build/`)
- Exclude dependencies (`node_modules/`, `venv/`)
- Exclude version control (`.git/`)
- Exclude IDE files (`.vscode/`, `.idea/`)
- Set reasonable file size limits
- Include only relevant file types

❌ **DON'T**:
- Include binary files (images, executables)
- Include generated files
- Include large data files
- Include temporary files
- Use overly broad patterns

### Git Hooks

✅ **DO**:
- Enable incremental mode for speed
- Set `fail_on_error: false` for development
- Test hooks before committing to main
- Document hook behavior in README
- Use pre-commit for incremental updates

❌ **DON'T**:
- Block commits with `fail_on_error: true` in dev
- Process entire repository on every commit
- Ignore hook errors silently
- Use hooks without testing first

### Performance

✅ **DO**:
- Tune batch size based on repository size
- Increase workers for large repositories
- Enable cache warming for frequent queries
- Monitor performance metrics
- Schedule bulk ingestion during off-hours

❌ **DON'T**:
- Use small batches (< 20 files)
- Use too many workers (> 16)
- Run bulk ingestion during peak hours
- Process unchanged files repeatedly

### Team Collaboration

✅ **DO**:
- Share configuration in git repository
- Document configuration in README
- Use environment variables for local paths
- Add comments explaining custom settings
- Review configuration changes in PRs

❌ **DON'T**:
- Hardcode absolute paths
- Commit local configuration overrides
- Change global settings without discussion
- Skip validation before committing

---

## Example Configurations

### Minimal Configuration

```yaml
schema_version: "1.0.0"
config_type: "tree_stamping_repositories"

global:
  kafka:
    bootstrap_servers: "omninode-bridge-redpanda:9092"
  qdrant:
    url: "http://qdrant:6333"
    collection: "file_locations"

repositories:
  - name: "my-project"
    enabled: true
    path: "/path/to/my/project"
    filters:
      include: ["**/*.py"]
      exclude: ["**/venv/**"]
```

### Full-Featured Configuration

```yaml
schema_version: "1.0.0"
config_type: "tree_stamping_repositories"

global:
  kafka:
    bootstrap_servers: "omninode-bridge-redpanda:9092"
  qdrant:
    url: "http://qdrant:6333"
    collection: "file_locations"
  processing:
    batch_size: 50
    max_workers: 4
  intelligence:
    quality_scoring: true
    onex_classification: true
    semantic_analysis: true

repositories:
  - name: "backend-api"
    enabled: true
    description: "Backend API service"
    path: "${CODE_DIR}/backend-api"

    filters:
      include: ["**/*.py", "**/*.md", "**/*.yaml"]
      exclude: ["**/venv/**", "**/.git/**", "**/dist/**"]
      max_file_size: 1048576

    processing:
      batch_size: 100
      max_workers: 6

    git_hooks:
      enabled: true
      pre_commit: true
      incremental: true
      fail_on_error: false

    metadata:
      team: "backend"
      language: "python"
      framework: "fastapi"
      priority: "high"

  - name: "frontend-app"
    enabled: true
    description: "Frontend React application"
    path: "${CODE_DIR}/frontend-app"

    filters:
      include: ["**/*.ts", "**/*.tsx", "**/*.json"]
      exclude: ["**/node_modules/**", "**/dist/**"]

    git_hooks:
      enabled: true
      pre_commit: true

    metadata:
      team: "frontend"
      language: "typescript"
      framework: "react"
      priority: "high"

validation:
  require_absolute_paths: true
  validate_path_exists: true
  check_path_conflicts: true

monitoring:
  enabled: true
  metrics:
    enabled: true
    export_interval_seconds: 60
```

---

## Support

### Resources

- **Documentation**: `/docs/guides/MULTI_REPO_SETUP.md` (this file)
- **Configuration Reference**: `config/tree_stamping_repos.yaml`
- **CLI Help**: `python scripts/tree_stamping_config_cli.py --help`
- **Archon Documentation**: `CLAUDE.md`

### Getting Help

1. Check [Troubleshooting](#troubleshooting) section
2. Validate configuration: `tree_stamping_config_cli.py validate`
3. Test repository: `tree_stamping_config_cli.py test <repo-name>`
4. Check service health: `curl http://localhost:8053/health`

---

**Happy Stamping! 🚀**
