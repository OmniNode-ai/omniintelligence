# Task Breakdown: Fix wire_dispatchers Error Handler Cleanup

**Ticket**: OMN-2210 (Wire intelligence nodes into registration / pattern extraction)
**Branch**: `jonahgabriel/omn-2210-wire-intelligence-nodes-into-registration-pattern-extraction`
**Status**: Fix already applied, validation required
**Date**: 2026-02-14

## Overview

The major issue identified in local code review has been addressed: the `wire_dispatchers` exception handler in `PluginIntelligence.wire_dispatchers()` now properly cleans up introspection resources when failures occur after `publish_intelligence_introspection()` succeeds.

**What was broken**: If an exception occurred after publishing introspection events but before the method returned, the old code would:
- Set `self._introspection_proxies = []` without stopping heartbeat tasks (memory leak / orphaned async tasks)
- Not reset the `_introspection_published` guard (permanently blocking retry)

**What was fixed**: The exception handler now:
1. Stops heartbeat asyncio tasks on each proxy via `await proxy.stop_introspection_tasks()`
2. Calls `reset_introspection_guard()` to allow retry
3. Clears all references (`_event_bus`, `_introspection_nodes`, `_introspection_proxies`)

---

## Fix Location

**File**: `src/omniintelligence/runtime/plugin.py`
**Method**: `PluginIntelligence.wire_dispatchers()`
**Exception Handler**: Lines 544-586

### Code Changes

```python
except Exception as e:
    duration = time.time() - start_time
    logger.exception(
        "Failed to wire intelligence dispatch engine (correlation_id=%s)",
        correlation_id,
    )
    # Clean up partially-captured state to avoid stale references.
    # If the failure occurred after capturing event_bus or after
    # introspection publishing, these references would dangle and
    # could cause shutdown to operate on stale/inconsistent state.
    #
    # Stop heartbeat tasks on any introspection proxies that were
    # started before the failure, then reset the single-call guard
    # so a retry is not permanently blocked (follows the same
    # pattern as _do_shutdown).
    for proxy in self._introspection_proxies:
        try:
            await proxy.stop_introspection_tasks()
        except Exception as stop_error:
            sanitized = get_log_sanitizer().sanitize(str(stop_error))
            logger.debug(
                "Error stopping introspection tasks for %s during "
                "wire_dispatchers cleanup: %s (correlation_id=%s)",
                proxy.name,
                sanitized,
                correlation_id,
            )

    from omniintelligence.runtime.introspection import (
        reset_introspection_guard,
    )

    reset_introspection_guard()

    self._event_bus = None
    self._introspection_nodes = []
    self._introspection_proxies = []
    self._dispatch_engine = None
    return ModelDomainPluginResult.failed(...)
```

**Key Points**:
- Lines 559-570: Loop through proxies and stop each one (with error handling)
- Line 563: Sanitize errors before logging (prevents secret leakage)
- Line 564: Log at DEBUG level (not ERROR, to avoid noise on benign timeouts)
- Lines 572-576: Import and unconditionally call `reset_introspection_guard()`
- Lines 578-581: Clear all state references

---

## Validation Tasks

### Parallel Tasks (Can Run in Parallel)

#### T1: Verify Fix Application
- **Description**: Confirm all required cleanup steps are present in exception handler
- **File**: `src/omniintelligence/runtime/plugin.py` (lines 544-586)
- **Validation Criteria**:
  - [ ] Exception handler has loop `for proxy in self._introspection_proxies`
  - [ ] Loop calls `await proxy.stop_introspection_tasks()`
  - [ ] Exceptions in loop are caught and sanitized
  - [ ] `reset_introspection_guard()` is imported and called unconditionally
  - [ ] All references cleared: `_event_bus`, `_introspection_nodes`, `_introspection_proxies`, `_dispatch_engine`

#### T2: Verify Error Sanitization
- **Description**: Confirm error messages are sanitized before logging
- **File**: `src/omniintelligence/runtime/plugin.py` (lines 563)
- **Validation Criteria**:
  - [ ] `get_log_sanitizer().sanitize()` is called on `stop_error` before logging
  - [ ] Sanitized error is logged, not raw exception
  - [ ] No secrets/credentials appear in debug logs

#### T3: Verify Introspection Guard Reset
- **Description**: Confirm reset_introspection_guard() is properly imported and called
- **File**: `src/omniintelligence/runtime/plugin.py` (lines 572-576)
- **Validation Criteria**:
  - [ ] `reset_introspection_guard` is imported from `omniintelligence.runtime.introspection`
  - [ ] Call is unconditional (not inside conditional block)
  - [ ] Import is inside except block (late binding to avoid circular imports)

#### T4: Verify Consistency with _do_shutdown
- **Description**: Confirm exception handler follows same cleanup pattern as _do_shutdown
- **Files**: `src/omniintelligence/runtime/plugin.py` (lines 748-844)
- **Validation Criteria**:
  - [ ] Both call `stop_introspection_tasks()` on proxies
  - [ ] Both reset guard before clearing references
  - [ ] Both clear references in same order: `_event_bus`, `_introspection_nodes`, `_introspection_proxies`
  - [ ] Error handling patterns are similar (try/except + sanitize + log)

### Sequential Tasks (Must Run in Order)

#### T5: Run Unit Tests (Depends on T1-T4)
- **Description**: Execute plugin-specific unit tests for exception handling
- **Files**:
  - `src/omniintelligence/runtime/plugin.py`
  - `tests/unit/runtime/test_plugin_intelligence.py`
  - `src/omniintelligence/runtime/introspection.py`
- **Test Cases**:
  - [ ] Test: Exception after `publish_intelligence_introspection()` succeeds
  - [ ] Verify: All proxies' `stop_introspection_tasks()` called
  - [ ] Verify: `reset_introspection_guard()` called and effective
  - [ ] Verify: All state references cleared
  - [ ] Verify: Retry of `wire_dispatchers()` is not permanently blocked
  - [ ] Verify: Log entries don't contain secrets (check sanitization)
  - [ ] Verify: No orphaned asyncio tasks remain
- **Execution**: `uv run pytest tests/unit/runtime/test_plugin_intelligence.py -xvs`

#### T6: Code Quality & Type Checking (Depends on T5)
- **Description**: Validate code quality, formatting, and type safety
- **Files**: `src/omniintelligence/runtime/plugin.py`
- **Checks**:
  - [ ] Linting: `uv run ruff check src/omniintelligence/runtime/plugin.py`
  - [ ] Formatting: `uv run ruff format src/omniintelligence/runtime/plugin.py`
  - [ ] Type checking: `uv run mypy src/omniintelligence/runtime/plugin.py --strict`
  - [ ] No new violations introduced
- **Execution**:
  ```bash
  uv run ruff check --fix src/omniintelligence/runtime/plugin.py
  uv run ruff format src/omniintelligence/runtime/plugin.py
  uv run mypy src/omniintelligence/runtime/plugin.py --strict
  ```

#### T7: Audit Tests (Depends on T6)
- **Description**: Run I/O purity and architectural enforcement tests
- **Files**:
  - `tests/audit/test_io_violations.py`
  - `src/omniintelligence/runtime/plugin.py`
- **Checks**:
  - [ ] No new logging imports in node classes (if applicable)
  - [ ] No new try/except in node methods (if applicable)
  - [ ] No new `container.get()` at runtime (if applicable)
  - [ ] Kafka non-blocking contract maintained (if applicable)
  - [ ] All exceptions properly handled or re-raised (invariant check)
- **Execution**: `uv run pytest tests/audit/test_io_violations.py -xvs -m audit`

#### T8: Create Commit (Depends on T7)
- **Description**: Commit validated changes with detailed explanation
- **Files**: `src/omniintelligence/runtime/plugin.py`
- **Commit Message**:
  ```
  fix(runtime): [major] clean up introspection proxies on wire_dispatchers failure

  Prevent memory leaks and permanently-blocked retry on exception after
  publish_intelligence_introspection() succeeds but before return.

  Changes:
  - Stop heartbeat asyncio tasks on each introspection proxy
  - Reset _introspection_published single-call guard for retry
  - Clear all state references: _event_bus, _introspection_nodes, _introspection_proxies, _dispatch_engine
  - Sanitize error messages before logging (prevent secret leakage)
  - Match _do_shutdown cleanup pattern for consistency

  Fixes: OMN-2210 (Wire intelligence nodes into registration)
  ```
- **Execution**:
  ```bash
  git add src/omniintelligence/runtime/plugin.py
  git commit -m "fix(runtime): [major] clean up introspection proxies on wire_dispatchers failure..."
  git log --oneline -1
  ```

---

## Risk Assessment

### High Severity

1. **Memory Leak**: If `proxy.stop_introspection_tasks()` is not properly awaited
   - Impact: Orphaned heartbeat tasks consume memory/CPU
   - Mitigation: Verify `await` keyword present; test orphan detection

2. **Permanent Retry Block**: If `reset_introspection_guard()` is not called
   - Impact: Any subsequent `wire_dispatchers()` call permanently fails
   - Mitigation: Verify unconditional call in exception handler; test retry scenario

3. **State Inconsistency**: If exception handler and `_do_shutdown` differ
   - Impact: One code path leaks resources; cleanup behavior unpredictable
   - Mitigation: Compare both methods line-by-line; test both paths

### Medium Severity

4. **Secret Leakage**: If error messages not sanitized before logging
   - Impact: Credentials/tokens exposed in logs
   - Mitigation: Verify `get_log_sanitizer().sanitize()` called; audit all log statements

5. **Race Condition**: Partial introspection list if publishing interrupted
   - Impact: Some proxies remain unstopped
   - Mitigation: Error handling loop validates all proxies stopped regardless of partial state

6. **Circular Import**: Late binding of `reset_introspection_guard` import
   - Impact: Misleading error on circular dependency
   - Mitigation: Import placed inside except block (correct); no static import of introspection module

### Low Severity

7. **Log Noise**: Debug-level logging of cleanup errors
   - Impact: Logs become verbose on benign timeouts
   - Mitigation: DEBUG level appropriate; use only for operational diagnostics

---

## Success Criteria

All of the following must be true:

1. **Code Review** (T1-T4):
   - [ ] Exception handler has all three cleanup steps (stop tasks, reset guard, clear refs)
   - [ ] Error sanitization applied
   - [ ] Consistency with `_do_shutdown` confirmed
   - [ ] No secrets in log output

2. **Tests Pass** (T5):
   - [ ] All unit tests pass
   - [ ] Test coverage for exception scenario complete
   - [ ] Retry behavior verified not permanently blocked
   - [ ] No orphaned tasks detected

3. **Quality Gates** (T6-T7):
   - [ ] ruff check: 0 violations
   - [ ] ruff format: 0 changes needed
   - [ ] mypy --strict: 0 errors
   - [ ] audit tests: 0 violations

4. **Commit** (T8):
   - [ ] Changes committed with detailed message
   - [ ] Commit message references ticket (OMN-2210)
   - [ ] Branch ready for PR

---

## File Manifest

| File | Purpose | Change Type |
|------|---------|------------|
| `src/omniintelligence/runtime/plugin.py` | Main fix location | MODIFIED |
| `src/omniintelligence/runtime/introspection.py` | Reset guard function | NO CHANGE (reference only) |
| `tests/unit/runtime/test_plugin_intelligence.py` | Unit tests | VALIDATE (no changes) |
| `tests/audit/test_io_violations.py` | Audit tests | VALIDATE (no changes) |

---

## Execution Plan

```
PHASE 1: Code Verification (Parallel - ~10 min)
├─ T1: Verify fix application
├─ T2: Verify error sanitization
├─ T3: Verify introspection guard reset
└─ T4: Verify consistency with _do_shutdown

PHASE 2: Validation (Sequential - ~20 min)
├─ T5: Run unit tests [Depends on T1-T4]
├─ T6: Code quality checks [Depends on T5]
├─ T7: Audit tests [Depends on T6]
└─ T8: Create commit [Depends on T7]

TOTAL ESTIMATED TIME: ~30 minutes
```

---

## Related Documentation

- **CLAUDE.md**: Repository-specific architecture and standards
- **OMN-2210**: Wire intelligence nodes into registration
- **Plugin Pattern**: `PluginIntelligence` follows `ProtocolDomainPlugin` from omnibase_infra
- **Introspection System**: `src/omniintelligence/runtime/introspection.py`
- **Error Handling**: Sanitization via `LogSanitizer` from `omniintelligence.utils.log_sanitizer`
