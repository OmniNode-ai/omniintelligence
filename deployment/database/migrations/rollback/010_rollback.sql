-- Rollback: 010_create_pattern_lifecycle_audit
-- Description: Drop pattern_lifecycle_transitions table
-- Author: omniintelligence
-- Date: 2026-02-02
-- Ticket: OMN-1805

-- Drop table (indexes and constraints are dropped automatically with the table)
DROP TABLE IF EXISTS pattern_lifecycle_transitions;
