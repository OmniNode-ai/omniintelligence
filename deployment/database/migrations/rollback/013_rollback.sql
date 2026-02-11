-- Rollback: 013_add_run_id_to_pattern_injections
-- Description: Remove run_id column from pattern_injections
-- Author: omniintelligence
-- Date: 2026-02-11
-- Ticket: OMN-2133

-- Drop index first
DROP INDEX IF EXISTS idx_pattern_injections_run_id;

-- Drop column
ALTER TABLE pattern_injections DROP COLUMN IF EXISTS run_id;
