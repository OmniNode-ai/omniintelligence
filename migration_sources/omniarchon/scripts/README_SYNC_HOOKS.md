# Intelligence Hook System Sync Script

## Overview

The `sync-hooks.sh` script synchronizes the Intelligence Hook System from the Archon repository to the Claude Code hooks directory (`~/.claude/hooks`). This enables centralized development and version control of the hook system while deploying to the active hooks location.

## Features

- **Validation**: Syntax checking for Python and Bash files before copying
- **Backup**: Automatic backup of original files (first run only)
- **Rollback**: Quick restoration from backup if needed
- **Dry-Run**: Preview changes without modifying files
- **Safety**: Confirmation prompts and error handling
- **Verification**: Post-sync installation verification

## Directory Structure

```
Source (Archon Repo):
/Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks/
├── lib/
│   ├── tracing/
│   │   ├── __init__.py
│   │   ├── tracer.py
│   │   └── models.py
│   └── quality_enforcer.py
└── pre-tool-use-quality.sh

Target (Claude Hooks):
/Users/jonah/.claude/hooks/
├── lib/
│   ├── tracing/           # Synced from source
│   │   └── *.py
│   └── quality_enforcer.py # Synced from source
├── pre-tool-use-quality.sh # Synced from source
└── .backups/              # Created by script
    └── ...                # Original files
```

## Usage

### Basic Sync

```bash
# Preview changes (recommended first run)
./scripts/sync-hooks.sh --dry-run

# Perform sync with confirmation
./scripts/sync-hooks.sh

# Force sync without confirmation
./scripts/sync-hooks.sh --force
```

### Advanced Options

```bash
# Rollback to original files
./scripts/sync-hooks.sh --rollback

# Verbose output for debugging
./scripts/sync-hooks.sh --verbose

# Combine options
./scripts/sync-hooks.sh --dry-run --verbose
```

### Help

```bash
./scripts/sync-hooks.sh --help
```

## Workflow

### 1. Initial Setup

```bash
# Create source directory structure (if not exists)
mkdir -p /Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks/lib/tracing

# Preview what would be synced
./scripts/sync-hooks.sh --dry-run

# Perform initial sync (creates backup)
./scripts/sync-hooks.sh
```

### 2. Regular Development

```bash
# Edit files in Archon repo:
# /Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks/

# Preview changes
./scripts/sync-hooks.sh --dry-run

# Sync to active hooks
./scripts/sync-hooks.sh

# Test in Claude Code
# (hooks are now active)

# If issues found, rollback
./scripts/sync-hooks.sh --rollback
```

### 3. Testing Changes

```bash
# After syncing, test hooks:
cd ~/.claude/hooks

# Test Python syntax
python3 -m py_compile lib/quality_enforcer.py
python3 -m py_compile lib/tracing/*.py

# Test bash syntax
bash -n pre-tool-use-quality.sh

# Test imports
python3 -c "from lib.quality_enforcer import QualityEnforcer"
python3 -c "from lib.tracing.tracer import ExecutionTracer"

# View logs during testing
tail -f ~/.claude/hooks/logs/quality_enforcer.log
```

## Validation

The script performs automatic validation:

### Python Files
- **Syntax Check**: `python3 -m py_compile`
- **Import Test**: Attempts to import modules
- **Error Reporting**: Lists files with issues

### Bash Files
- **Syntax Check**: `bash -n`
- **Executable Permissions**: Sets +x on hook scripts

### Post-Sync Verification
- File existence checks
- Import validation
- Detailed status reporting

## Backup System

### Automatic Backup

On first run, the script creates a backup:

```
~/.claude/hooks/.backups/
├── pre-tool-use-quality.sh
└── lib/
    ├── quality_enforcer.py
    └── tracing/
        └── *.py
```

### Backup Marker

A marker file tracks backup status:
```
~/.claude/hooks/.originals-backed-up
```

Contains timestamp of backup creation.

### Rollback Process

```bash
# Restore original files
./scripts/sync-hooks.sh --rollback

# Verify restoration
ls -la ~/.claude/hooks/

# Backup remains at ~/.claude/hooks/.backups
```

## Error Handling

### Source Directory Missing

```bash
$ ./scripts/sync-hooks.sh
✗ Source directory not found: /Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks

The Intelligence Hook System source directory doesn't exist yet.
...
```

**Solution**: Create the source directory structure first.

### Validation Failures

```bash
$ ./scripts/sync-hooks.sh
→ Validating: quality_enforcer.py
✗   Syntax FAILED
✗ 1 of 3 files failed validation
Validation failed. Cannot proceed with sync.
```

**Solution**: Fix syntax errors in source files before syncing.

### Missing Dependencies

```bash
⚠  Quality enforcer import test failed (may need dependencies)
```

**Solution**: Install required Python packages:
```bash
cd ~/.claude/hooks
pip install -r requirements.txt  # if exists
```

## Integration with Existing Sync Scripts

The Claude hooks directory already has sync scripts:

- `sync-to-live.sh`: Syncs hooks repo → live directory (rsync-based)
- `sync-from-live.sh`: Syncs live directory → hooks repo (reverse)

This new script (`sync-hooks.sh`) is complementary:

```
Archon Repo (Intelligence Service)
         ↓ (sync-hooks.sh)
Claude Hooks Directory (Active)
         ↓ (sync-to-live.sh)
Claude Hooks Backup/Repo
         ↑ (sync-from-live.sh)
Claude Hooks Directory (Active)
```

## Safety Features

### 1. Dry-Run Mode
- No files are modified
- Shows what would be copied
- Safe for testing

### 2. Confirmation Prompts
- Requires explicit confirmation (unless `--force`)
- Shows file count before syncing
- Prevents accidental overwrites

### 3. Backup Protection
- Automatic backup on first run
- Preserves original files
- One-command rollback

### 4. Validation Gates
- Syntax validation before copying
- Import testing (optional)
- Installation verification

### 5. Error Recovery
- Detailed error messages
- Safe rollback mechanism
- Preserves backup after rollback

## Troubleshooting

### Script Won't Execute

```bash
# Make executable
chmod +x /Volumes/PRO-G40/Code/Archon/scripts/sync-hooks.sh

# Run from Archon repo root
cd /Volumes/PRO-G40/Code/Archon
./scripts/sync-hooks.sh
```

### Permission Denied

```bash
# Check permissions
ls -la ~/.claude/hooks/

# Fix if needed
chmod +w ~/.claude/hooks/
```

### Files Not Syncing

```bash
# Check source exists
ls -la /Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks/

# Use verbose mode
./scripts/sync-hooks.sh --verbose

# Check for validation errors
./scripts/sync-hooks.sh --dry-run
```

### Backup Already Exists

```bash
# Use --force to create new backup
./scripts/sync-hooks.sh --force

# Or remove marker to reset
rm ~/.claude/hooks/.originals-backed-up
```

## Development Workflow

### Step 1: Create Source Structure

```bash
cd /Volumes/PRO-G40/Code/Archon

# Create directories
mkdir -p services/intelligence/src/hooks/lib/tracing

# Create/edit files
# - services/intelligence/src/hooks/pre-tool-use-quality.sh
# - services/intelligence/src/hooks/lib/quality_enforcer.py
# - services/intelligence/src/hooks/lib/tracing/*.py
```

### Step 2: Validate Locally

```bash
# Validate Python syntax
python3 -m py_compile services/intelligence/src/hooks/lib/quality_enforcer.py

# Validate Bash syntax
bash -n services/intelligence/src/hooks/pre-tool-use-quality.sh
```

### Step 3: Preview Sync

```bash
./scripts/sync-hooks.sh --dry-run
```

### Step 4: Sync to Hooks

```bash
./scripts/sync-hooks.sh
```

### Step 5: Test in Claude Code

```bash
# Use Claude Code to trigger hooks
# Monitor logs
tail -f ~/.claude/hooks/logs/quality_enforcer.log
```

### Step 6: Iterate

```bash
# Make changes in Archon repo
# Re-sync
./scripts/sync-hooks.sh --force

# Test again
```

### Step 7: Commit Changes

```bash
cd /Volumes/PRO-G40/Code/Archon
git add services/intelligence/src/hooks/
git commit -m "feat(intelligence): update hook system"
```

## Future Enhancements

Potential improvements for the script:

1. **Version Tracking**: Track synced versions
2. **Delta Sync**: Only copy changed files
3. **Checksum Validation**: Verify file integrity
4. **Multi-Environment**: Support dev/staging/prod targets
5. **Auto-Reload**: Trigger hook reload after sync
6. **Dependency Check**: Verify Python package requirements
7. **Rollback History**: Support multiple backup versions
8. **CI/CD Integration**: Automate sync in pipelines

## See Also

- **Hook Development**: `~/.claude/hooks/DEVELOPMENT_WORKFLOW.md`
- **Quality Enforcer**: `~/.claude/hooks/quality_enforcer_README.md`
- **Implementation Guide**: `~/.claude/hooks/IMPLEMENTATION_COMPLETE.md`
- **Existing Sync Scripts**: `~/.claude/hooks/sync-to-live.sh`

## Support

For issues or questions:

1. Check validation output: `./scripts/sync-hooks.sh --dry-run --verbose`
2. Review logs: `~/.claude/hooks/logs/`
3. Test source files: Python/Bash syntax validation
4. Try rollback: `./scripts/sync-hooks.sh --rollback`

---

**Version**: 1.0.0
**Created**: 2025-10-02
**Location**: `/Volumes/PRO-G40/Code/Archon/scripts/`
