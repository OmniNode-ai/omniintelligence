-- Rollback: 006_create_pattern_disable_events
-- Description: Drop pattern_disable_events table and related objects
-- Author: omniintelligence
-- Date: 2026-01-30
-- Ticket: OMN-1676

-- Drop indexes (reverse order of creation)
DROP INDEX IF EXISTS idx_pattern_disable_events_event_at;
DROP INDEX IF EXISTS idx_pattern_disable_events_type;
DROP INDEX IF EXISTS idx_pattern_disable_events_actor_audit;
DROP INDEX IF EXISTS idx_pattern_disable_events_pattern_class_latest;
DROP INDEX IF EXISTS idx_pattern_disable_events_pattern_id_latest;
DROP INDEX IF EXISTS idx_pattern_disable_events_event_id;

-- Drop table
DROP TABLE IF EXISTS pattern_disable_events CASCADE;
