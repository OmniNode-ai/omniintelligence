# Broken Links Report

**Generated**: 2025-10-20
**Tool**: `scripts/validation/validate_markdown_links.py`
**Status**: 105 broken links found across 100 markdown files

## Summary

- **Files scanned**: 608 markdown files
- **Files with broken links**: 30 files
- **Total links checked**: 796 links
- **Broken links found**: 105 broken links

## Categories of Issues

### 1. Missing Historical/Planning Documents (23 links)
Files referenced in README.md and planning docs that appear to have been moved or removed:
- `BASE_ARCHON_AUDIT.md`, `BASE_ARCHON_SUMMARY.md`
- `ARCHON_FUNCTIONALITY_INVENTORY.md`, `INCOMPLETE_FEATURES.md`
- `EVENT_BUS_ARCHITECTURE.md`, `EXTERNAL_GATEWAY_QUICK_REFERENCE.md`
- `SECURE_BUILD_GUIDE.md`, `MVP_IMPLEMENTATION_STATUS.md`

### 2. Absolute Path References (18 links)
Links using absolute paths (starting with `/`) that should be relative:
- `/docs/onex/ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md`
- `/docs/testing/KAFKA_TEST_SETUP.md`
- `/docs/PHASE_4_*.md` (multiple files)
- `/services/*/README.md` references

### 3. Missing Guide/Reference Documents (20 links)
Documentation referenced but not found:
- `docs/guides/onex-standards.md`, `code-review-checklist.md`
- `docs/guides/ARCHON_INTEGRATION.md`, `AGENT_FRAMEWORK.md`
- `docs/architecture/PRODUCTION_ROLLOUT_PROCEDURES.md`
- `services/intelligence/docs/PERFORMANCE_TUNING.md`

### 4. Invalid Link Patterns (8 links)
Regex patterns or code snippets incorrectly parsed as links:
- `[^"\']+` in CLAUDE_CODE_HOOKS_STRATEGY.md
- `[container]` in MIGRATION_GUIDE.md
- Function signatures in OMNIBASE_CORE_NODE_ARCHITECTURE.md

### 5. Cross-Project References (4 links)
Links to external projects that shouldn't be checked:
- `file:///Volumes/PRO-G40/Code/zen-mcp-server/server.py`

### 6. Service-Specific Missing Docs (15 links)
- Bridge service: `services/bridge/README.md`
- Search service: `services/search/README.md`
- Intelligence service documentation gaps

## Key Files with Most Broken Links

1. **README.md** - 15 broken links (mostly historical documentation)
2. **docs/guides/PR_WORKFLOW_GUIDE.md** - 8 broken links
3. **docs/planning/INCOMPLETE_FEATURES.md** - 6 broken links
4. **Pattern Traceability docs** - 9 broken links (absolute paths)
5. **Intelligence service docs** - 12 broken links

## Recommendations

### High Priority
1. **Fix README.md links**: Update or remove references to moved/deleted docs
2. **Convert absolute to relative paths**: Fix all `/docs/*` references
3. **Create missing service READMEs**: Add documentation for bridge/search services

### Medium Priority
4. **Fix guide cross-references**: Update broken links in PR_WORKFLOW_GUIDE.md
5. **Update pattern traceability docs**: Fix absolute path references
6. **Clean up planning docs**: Remove or update references to incomplete features

### Low Priority
7. **Fix regex patterns**: Escape or reformat code examples parsed as links
8. **Add missing ONEX docs**: Create referenced standard documentation files

## How to Run

```bash
# Run link checker
python3 scripts/validation/validate_markdown_links.py

# View full output
python3 scripts/validation/validate_markdown_links.py 2>&1 | tee link_report.txt
```

## Next Steps

1. Create tracking issues for each category
2. Fix high-priority broken links first (README.md, absolute paths)
3. Add link checker to CI/CD pipeline to prevent future issues
4. Consider adding `.linkcheck-ignore` for valid external references

---

**Note**: This report was generated after copying the link checker from `omnibase_core`. The tool should be run regularly to maintain documentation quality.
