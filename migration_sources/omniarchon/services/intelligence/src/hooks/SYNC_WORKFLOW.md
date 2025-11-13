# Phase 4 Pattern Tracking - Sync Workflow

## 🔄 Development Workflow

### Working Location
**Primary Development**: `/Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks/`

This is the source of truth. All development happens here first.

### Deployment Location
**Claude Code Hooks**: `/Users/jonah/.claude/hooks/`

This is where Claude Code reads the hooks for execution.

## 📋 Sync Process

### 1. After Making Changes in Archon

```bash
# Run the sync script
cd /Volumes/PRO-G40/Code/Archon
./scripts/sync-hooks.sh

# Or with options:
./scripts/sync-hooks.sh --dry-run    # Preview changes
./scripts/sync-hooks.sh --force      # Skip confirmation
```

### 2. What Gets Synced

The sync script copies these files from Archon → Claude:

```
Archon Source                                    → Claude Target
────────────────────────────────────────────────────────────────
/services/intelligence/src/hooks/
├── lib/tracing/                                 → ~/.claude/hooks/lib/tracing/
├── lib/quality_enforcer.py                      → ~/.claude/hooks/lib/quality_enforcer.py
├── lib/pattern_tracker.py                       → ~/.claude/hooks/lib/pattern_tracker.py
├── lib/pattern_id_system.py                     → ~/.claude/hooks/lib/pattern_id_system.py
├── lib/phase4_api_client.py                     → ~/.claude/hooks/lib/phase4_api_client.py
├── lib/resilience.py                            → ~/.claude/hooks/lib/resilience.py
└── pre-tool-use-quality.sh                      → ~/.claude/hooks/pre-tool-use-quality.sh
```

### 3. Verification After Sync

```bash
# Check sync was successful
ls -lh ~/.claude/hooks/lib/ | grep pattern

# Test imports
cd ~/.claude/hooks
python3 -c "import sys; sys.path.insert(0, 'lib'); from pattern_tracker import PatternTracker; print('✓ Works')"

# Check Phase 4 API connectivity
curl http://localhost:8053/health
```

## 🎯 Phase 4 Integration Components

### Core Files (Now in Archon)

1. **pattern_tracker.py** (19KB)
   - Core PatternTracker class
   - Session management
   - Pattern creation/execution tracking
   - Integration with Phase 4 APIs

2. **pattern_id_system.py** (23KB)
   - SHA256-based pattern ID generation
   - Code normalization for consistency
   - Similarity detection (70-90% threshold)
   - Semantic versioning

3. **phase4_api_client.py** (33KB)
   - HTTP client for 7 Phase 4 endpoints
   - Retry logic with exponential backoff
   - 2-second timeout, graceful errors
   - Async/await architecture

4. **resilience.py** (33KB)
   - Fire-and-forget execution
   - Circuit breaker pattern
   - Local cache fallback
   - Health checking

### Integration Points

**quality_enforcer.py** (lines 31-36):
```python
try:
    from pattern_tracker import PatternTracker
    PATTERN_TRACKING_AVAILABLE = True
except ImportError:
    PATTERN_TRACKING_AVAILABLE = False
```

## 🚀 Quick Start (First Time)

```bash
# 1. Ensure Phase 4 is running
docker ps | grep intelligence

# 2. Sync Archon → Claude
cd /Volumes/PRO-G40/Code/Archon
./scripts/sync-hooks.sh

# 3. Test in Claude Code
# Generate some code and check:
tail -f ~/.claude/hooks/logs/pattern-tracking.log
```

## 🔍 Troubleshooting

### Sync Failed
```bash
# Check source exists
ls /Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks/lib/pattern_tracker.py

# Try dry-run first
./scripts/sync-hooks.sh --dry-run
```

### Import Errors After Sync
```bash
# Verify Python can find modules
cd ~/.claude/hooks
python3 -c "import sys; print(sys.path)"

# Check file permissions
ls -la ~/.claude/hooks/lib/pattern*.py
```

### Pattern Tracking Not Working
```bash
# Check Phase 4 API
curl http://localhost:8053/api/pattern-traceability/health

# Check logs
tail -f ~/.claude/hooks/logs/pattern-tracking.log
tail -f ~/.claude/hooks/logs/quality_enforcer.log
```

## 📊 Migration History

**October 3, 2025**:
- ✅ Migrated pattern_tracker.py from .claude → Archon
- ✅ Migrated pattern_id_system.py from .claude → Archon
- ✅ Migrated phase4_api_client.py from .claude → Archon
- ✅ Migrated resilience.py from .claude → Archon
- ✅ Verified integration with quality_enforcer.py
- ✅ Established Archon as source of truth

## 🎓 Best Practices

1. **Always develop in Archon first**
2. **Use sync script for deployment**
3. **Test in Archon before syncing**
4. **Keep backup before major changes** (sync script does this automatically)
5. **Document breaking changes** in this file

## 🔗 Related Documentation

- Phase 4 API docs: `/Volumes/PRO-G40/Code/Archon/services/intelligence/PHASE4_API_DOCUMENTATION.md`
- Hook system: `README.md` (this directory)
- Sync script: `/Volumes/PRO-G40/Code/Archon/scripts/sync-hooks.sh`
