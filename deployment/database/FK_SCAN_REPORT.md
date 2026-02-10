# FK Scan Report — omniintelligence

**Ticket**: OMN-2067 (DB-SPLIT-03)
**Parent**: OMN-2054
**Date**: 2026-02-10
**Repo**: omniintelligence2

## Summary

**Result: All foreign keys are intra-service. No cross-service FK violations found.**

- Migrations scanned: 11
- Tables created: 8 (+ 1 materialized view)
- FK declarations found: 5
- Cross-service FKs: **0**

## Tables Owned by omniintelligence

| Table | Migration | Type |
|-------|-----------|------|
| `fsm_state` | 001 | Table |
| `fsm_state_history` | 002 | Table |
| `workflow_executions` | 003 | Table |
| `domain_taxonomy` | 004 | Table |
| `learned_patterns` | 005 | Table |
| `pattern_disable_events` | 006 | Table |
| `pattern_injections` | 006 | Table |
| `disabled_patterns_current` | 007 | Materialized View |
| `pattern_lifecycle_transitions` | 008 | Table |

## FK Declarations

| # | Migration | Source Table | FK Column | Target Table | Target Column | Cascade | Intra-Service |
|---|-----------|-------------|-----------|--------------|---------------|---------|---------------|
| 1 | 005 | `learned_patterns` | `domain_id` | `domain_taxonomy` | `domain_id` | ON DELETE RESTRICT ON UPDATE CASCADE | YES |
| 2 | 005 | `learned_patterns` | `supersedes` | `learned_patterns` | `id` | (default) | YES (self-ref) |
| 3 | 005 | `learned_patterns` | `superseded_by` | `learned_patterns` | `id` | (default) | YES (self-ref) |
| 4 | 006 | `pattern_disable_events` | `pattern_id` | `learned_patterns` | `id` | ON DELETE RESTRICT ON UPDATE CASCADE | YES |
| 5 | 008 | `pattern_lifecycle_transitions` | `pattern_id` | `learned_patterns` | `id` | ON DELETE RESTRICT | YES |

## Application-Level References (No FK Constraint)

| Source Table | Column | Referenced Table | Reason |
|-------------|--------|-----------------|--------|
| `pattern_injections` | `pattern_ids` (UUID[]) | `learned_patterns` | PostgreSQL does not support FK constraints on array columns. Referential integrity enforced at application layer. |

## Cross-Service FK Violations

**None.**

## Resolution Plans

No resolution plans needed — all FK targets are tables owned by omniintelligence.

## Notes

- The `fsm_state_history` table has a **trigger** relationship with `fsm_state` (records are inserted via `record_fsm_state_history()` trigger on `fsm_state`), but no FK constraint.
- The `workflow_executions` table reuses the `update_fsm_state_updated_at()` trigger function from migration 001, but has no FK to `fsm_state`.
- The `disabled_patterns_current` materialized view reads from `pattern_disable_events` but has no FK constraints (views cannot have FKs).
- Migration numbering has two instances of duplicate prefixes (two `006_*` files, two `008_*` files). This does not affect FK analysis but may warrant cleanup.
