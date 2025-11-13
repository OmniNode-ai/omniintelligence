# Migration Scripts Archive

**Purpose**: Historical one-time migration scripts that have been executed and are preserved for reference only.

## Overview

This directory contains temporary fix scripts that were used during major codebase refactoring efforts. These scripts have already been executed and should **NOT** be run again in production.

## Scripts Inventory

### Import Path Migrations (PR #20)

These scripts were used to standardize import paths and remove sys.path manipulations during the test infrastructure cleanup:

| Script | Purpose | Executed |
|--------|---------|----------|
| `fix_all_src_imports.py` | Global src prefix import fixes | ✅ Complete |
| `fix_archon_services_intelligence_imports.py` | Fixed archon.services.intelligence import paths | ✅ Complete |
| `fix_imports.py` | General import path corrections | ✅ Complete |
| `fix_source_imports_for_pytest.py` | pytest-specific import path fixes | ✅ Complete |
| `fix_src_imports.py` | Additional src prefix fixes | ✅ Complete |
| `fix_test_imports.py` | Test file import standardization | ✅ Complete |
| `remove_syspath_manipulations.py` | Removed sys.path.insert/append hacks | ✅ Complete |
| `revert_src_prefix.py` | Reverted incorrect src prefixes | ✅ Complete |

## Historical Context

### Problem
The codebase had inconsistent import patterns:
- Some files used `from src.services...`
- Others used `from services...`
- sys.path manipulations in test files
- pytest configuration issues

### Solution
These migration scripts systematically:
1. Standardized all imports to use consistent paths
2. Removed sys.path manipulations
3. Fixed pytest discovery issues
4. Ensured ONEX compliance

### Result
- 100% of imports standardized
- Zero sys.path hacks remaining
- pytest runs cleanly without path manipulation
- All 118 tests passing

## Important Notes

⚠️ **DO NOT RE-RUN THESE SCRIPTS**
- They have already been executed
- Re-running may introduce bugs or inconsistencies
- The codebase is now in the desired state

📋 **Why Preserved?**
- Historical reference for future refactoring efforts
- Documentation of migration approach
- Debugging reference if import issues resurface

🔍 **If You Need to Modify Imports**
- Use standard Python import conventions
- Follow ONEX patterns in CLAUDE.md
- Do NOT use sys.path manipulation
- Ensure pytest can discover tests without path hacks

## Related Documentation

- **PR #20**: Test infrastructure cleanup and coverage improvement
- **CLAUDE.md**: ONEX import patterns and conventions
- **pytest.ini**: Current pytest configuration (no path manipulation needed)

---

**Last Updated**: 2025-11-04
**Migration Wave**: Import Standardization (PR #20)
**Status**: Archive - Historical artifacts only
