-- Rollback: 008_create_disabled_patterns_current_view
-- Description: Drop disabled_patterns_current materialized view
-- Author: omniintelligence
-- Date: 2026-01-30
-- Ticket: OMN-1677

-- Drop materialized view (indexes are dropped automatically with the view)
DROP MATERIALIZED VIEW IF EXISTS disabled_patterns_current;
