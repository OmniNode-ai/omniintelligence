-- Migration: 007_create_disabled_patterns_current_view
-- Description: Materialized view computing current disabled patterns from event log
-- Author: omniintelligence
-- Date: 2026-01-30
-- Ticket: OMN-1677
--
-- Dependencies: 006_create_pattern_disable_events.sql (source event table)
--
-- Purpose: This materialized view computes the current disabled state for each pattern
-- by finding the latest event per pattern_id or pattern_class. Only patterns whose
-- latest event is 'disabled' appear in this view.
--
-- Precedence Rules:
--   1. Each unique (pattern_id, pattern_class) combination is tracked independently
--   2. The latest event_at timestamp wins for determining current state
--   3. Only 'disabled' events appear in the view; 're_enabled' events remove patterns
--   4. COALESCE(pattern_id::text, pattern_class) creates a unique partition key
--      ensuring patterns with pattern_id are distinct from class-only disables
--
-- Refresh Strategy:
--   - This view must be refreshed by application code after inserting events
--   - Refresh command: REFRESH MATERIALIZED VIEW CONCURRENTLY disabled_patterns_current;
--   - CONCURRENTLY allows reads during refresh (requires unique index)
--   - Recommended: Refresh after each INSERT or in batch after bulk inserts
--   - Note: No automatic triggers - caller is responsible for refresh timing
--
-- Performance Characteristics:
--   - View is small (only currently-disabled patterns)
--   - Refresh is fast (single pass over event table with window function)
--   - Lookups are O(1) with unique indexes

-- ============================================================================
-- Materialized View: Current Disabled Patterns
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS disabled_patterns_current AS
WITH ranked_events AS (
    SELECT
        id,
        event_id,
        event_type,
        pattern_id,
        pattern_class,
        reason,
        event_at,
        actor,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY COALESCE(pattern_id::text, pattern_class)
            ORDER BY event_at DESC
        ) AS rn
    FROM pattern_disable_events
)
SELECT
    id,
    event_id,
    event_type,
    pattern_id,
    pattern_class,
    reason,
    event_at,
    actor,
    created_at
FROM ranked_events
WHERE rn = 1
  AND event_type = 'disabled';

-- ============================================================================
-- Unique Indexes for CONCURRENTLY Refresh Support
-- ============================================================================
-- REFRESH MATERIALIZED VIEW CONCURRENTLY requires at least one unique index.
-- Since (pattern_id, pattern_class) can have NULL values and we partition by
-- COALESCE(pattern_id::text, pattern_class), we need two partial indexes:

-- Unique index for pattern_id-based disables (pattern_id is NOT NULL)
-- This covers disables targeting specific patterns
CREATE UNIQUE INDEX IF NOT EXISTS idx_disabled_patterns_current_pattern_id_unique
    ON disabled_patterns_current(pattern_id)
    WHERE pattern_id IS NOT NULL;

-- Unique index for pattern_class-only disables (pattern_id IS NULL)
-- This covers disables targeting entire pattern classes
CREATE UNIQUE INDEX IF NOT EXISTS idx_disabled_patterns_current_pattern_class_unique
    ON disabled_patterns_current(pattern_class)
    WHERE pattern_id IS NULL;

-- ============================================================================
-- Regular Indexes for Fast Lookups
-- ============================================================================

-- Index for fast lookup by pattern_id (most common query)
-- Used by: "Is pattern X currently disabled?"
CREATE INDEX IF NOT EXISTS idx_disabled_patterns_current_pattern_id
    ON disabled_patterns_current(pattern_id)
    WHERE pattern_id IS NOT NULL;

-- Index for fast lookup by pattern_class
-- Used by: "Is pattern class Y currently disabled?"
CREATE INDEX IF NOT EXISTS idx_disabled_patterns_current_pattern_class
    ON disabled_patterns_current(pattern_class)
    WHERE pattern_class IS NOT NULL;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON MATERIALIZED VIEW disabled_patterns_current IS 'Current disabled patterns computed from pattern_disable_events. Refresh with: REFRESH MATERIALIZED VIEW CONCURRENTLY disabled_patterns_current;';

COMMENT ON COLUMN disabled_patterns_current.id IS 'ID of the disable event that established current state';
COMMENT ON COLUMN disabled_patterns_current.event_id IS 'Idempotency key of the disable event';
COMMENT ON COLUMN disabled_patterns_current.event_type IS 'Always ''disabled'' in this view (re_enabled events are filtered out)';
COMMENT ON COLUMN disabled_patterns_current.pattern_id IS 'Specific pattern UUID that is disabled, or NULL for class-wide disable';
COMMENT ON COLUMN disabled_patterns_current.pattern_class IS 'Pattern class that is disabled, used when pattern_id is NULL';
COMMENT ON COLUMN disabled_patterns_current.reason IS 'Reason provided when the pattern was disabled';
COMMENT ON COLUMN disabled_patterns_current.event_at IS 'Timestamp when the pattern was disabled';
COMMENT ON COLUMN disabled_patterns_current.actor IS 'Who disabled the pattern';
COMMENT ON COLUMN disabled_patterns_current.created_at IS 'When the disable event was recorded';
