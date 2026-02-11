-- Rollback: 012_create_pattern_measured_attributions
-- Description: Drop pattern_measured_attributions table
-- Author: omniintelligence
-- Date: 2026-02-11
-- Ticket: OMN-2133

-- Drop table (indexes and constraints are dropped automatically with the table)
DROP TABLE IF EXISTS pattern_measured_attributions;
