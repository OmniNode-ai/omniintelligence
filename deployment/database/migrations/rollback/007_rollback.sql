-- Rollback: 007_create_pattern_injections
-- Description: Drop pattern_injections table and its trigger function
-- Author: omniintelligence
-- Date: 2026-01-30
-- Ticket: OMN-1670

-- Drop trigger function (trigger is dropped automatically with the table)
DROP FUNCTION IF EXISTS update_pattern_injections_updated_at();

-- Drop table (indexes are dropped automatically with the table)
DROP TABLE IF EXISTS pattern_injections;
