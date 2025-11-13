# Intelligence Hook System Sync - Quick Reference

## One-Line Commands

```bash
# Most Common Commands
./scripts/sync-hooks.sh --dry-run    # Preview what will sync
./scripts/sync-hooks.sh              # Sync with confirmation
./scripts/sync-hooks.sh --force      # Sync without confirmation
./scripts/sync-hooks.sh --rollback   # Restore from backup
./scripts/test-sync-hooks.sh         # Run test suite
```

## Directory Map

```
SOURCE:  /Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks/
TARGET:  /Users/jonah/.claude/hooks/
BACKUP:  /Users/jonah/.claude/hooks/.backups/
```

## Files Synced

```
✓ lib/tracing/*.py           → Execution tracing library
✓ lib/quality_enforcer.py    → Quality enforcement engine
✓ pre-tool-use-quality.sh    → Hook entry point
```

## Typical Workflow

```bash
# 1. Edit in Archon repo
vim services/intelligence/src/hooks/lib/tracing/tracer.py

# 2. Preview
./scripts/sync-hooks.sh --dry-run

# 3. Sync
./scripts/sync-hooks.sh

# 4. Test
# Use Claude Code (hooks active)

# 5. Monitor
tail -f ~/.claude/hooks/logs/quality_enforcer.log

# 6. Rollback if needed
./scripts/sync-hooks.sh --rollback

# 7. Commit when stable
git add services/intelligence/src/hooks/
git commit -m "feat(intelligence): update hooks"
```

## Options Reference

| Option | Effect |
|--------|--------|
| `--dry-run` | Preview without changes |
| `--force` | Skip confirmations |
| `--rollback` | Restore from backup |
| `--verbose` | Show detailed output |
| `--help` | Show help message |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation failed or error |

## Emergency Recovery

```bash
# If something goes wrong
./scripts/sync-hooks.sh --rollback

# Manual recovery
cp ~/.claude/hooks/.backups/* ~/.claude/hooks/
```

## Test Status Check

```bash
./scripts/test-sync-hooks.sh
# Look for: "ALL TESTS PASSED SUCCESSFULLY!"
```

## Common Issues

### Source not found
```bash
# Create the directory structure
mkdir -p /Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks/lib/tracing
```

### Validation failed
```bash
# Check Python syntax
python3 -m py_compile <file>

# Check Bash syntax
bash -n <file>
```

### Backup exists warning
```bash
# Use --force to overwrite
./scripts/sync-hooks.sh --force
```

## File Locations

```
Script:  /Volumes/PRO-G40/Code/Archon/scripts/sync-hooks.sh
Docs:    /Volumes/PRO-G40/Code/Archon/scripts/README_SYNC_HOOKS.md
Tests:   /Volumes/PRO-G40/Code/Archon/scripts/test-sync-hooks.sh
Summary: /Volumes/PRO-G40/Code/Archon/scripts/SYNC_HOOKS_SUMMARY.md
```

## Feature Checklist

- [x] Syntax validation (Python & Bash)
- [x] Automatic backup (first run)
- [x] One-command rollback
- [x] Dry-run preview
- [x] Force mode
- [x] Colorized output
- [x] Error handling
- [x] Post-sync verification
- [x] Comprehensive tests

## Quick Help

```bash
./scripts/sync-hooks.sh --help
```

---
**Version**: 1.0.0 | **Status**: Production Ready | **Tests**: 12/12 Passed
