-- Migration: 006_create_pattern_disable_events
-- Description: Create event-sourced table for pattern disable/enable events with audit trail
-- Author: omniintelligence
-- Date: 2026-01-30
-- Ticket: OMN-1676
--
-- Dependencies: 005_create_learned_patterns.sql (foreign key to learned_patterns)
-- Note: This is an EVENT-SOURCED table (immutable log). Events are never updated or deleted.
--       The runtime kill switch queries the latest event per pattern_id or pattern_class
--       to determine current disabled/enabled state. A materialized view will optimize this.

-- ============================================================================
-- Pattern Disable Events Table (Event-Sourced / Immutable)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pattern_disable_events (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Idempotency key (prevents duplicate event processing)
    event_id UUID NOT NULL UNIQUE,

    -- Event type: disabled or re_enabled
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('disabled', 're_enabled')),

    -- Target: either a specific pattern OR a pattern class (at least one required)
    -- FK Cascade: RESTRICT prevents accidental pattern deletion while disable events reference it;
    --             CASCADE propagates pattern_id renames to maintain referential integrity.
    pattern_id UUID REFERENCES learned_patterns(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    pattern_class VARCHAR(100),

    -- Reason for disable/enable action (required for audit trail)
    reason TEXT NOT NULL,

    -- Event timestamp (when the disable/enable occurred)
    event_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Actor who performed the action (user, system, or automated process)
    actor VARCHAR(100) NOT NULL,

    -- Audit timestamp (when the record was inserted - distinct from event_at)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Data integrity: at least one of pattern_id or pattern_class must be specified
    CONSTRAINT check_target_specified CHECK (pattern_id IS NOT NULL OR pattern_class IS NOT NULL)
);

-- ============================================================================
-- Indexes for Runtime Queries
-- ============================================================================

-- Index on event_id for idempotency lookups (fast duplicate detection)
CREATE UNIQUE INDEX IF NOT EXISTS idx_pattern_disable_events_event_id
    ON pattern_disable_events(event_id);

-- Composite index for latest event per pattern_id (event_at DESC for efficient MAX query)
-- Used by runtime kill switch to get current state of specific patterns
CREATE INDEX IF NOT EXISTS idx_pattern_disable_events_pattern_id_latest
    ON pattern_disable_events(pattern_id, event_at DESC)
    WHERE pattern_id IS NOT NULL;

-- Composite index for latest event per pattern_class (event_at DESC for efficient MAX query)
-- Used by runtime kill switch to get current state of pattern classes
CREATE INDEX IF NOT EXISTS idx_pattern_disable_events_pattern_class_latest
    ON pattern_disable_events(pattern_class, event_at DESC)
    WHERE pattern_class IS NOT NULL;

-- Index for time-ordered audit queries by actor
-- Supports: "Show all actions by actor X in time range"
CREATE INDEX IF NOT EXISTS idx_pattern_disable_events_actor_audit
    ON pattern_disable_events(actor, event_at DESC);

-- Index for event_type filtering (useful for aggregations)
CREATE INDEX IF NOT EXISTS idx_pattern_disable_events_type
    ON pattern_disable_events(event_type);

-- Index for temporal queries (event timeline)
CREATE INDEX IF NOT EXISTS idx_pattern_disable_events_event_at
    ON pattern_disable_events(event_at DESC);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE pattern_disable_events IS 'Event-sourced immutable log of pattern disable/enable actions. Runtime kill switch for patterns. Query latest event per pattern_id or pattern_class to determine current state.';

-- Primary key
COMMENT ON COLUMN pattern_disable_events.id IS 'Unique event record identifier';

-- Idempotency
COMMENT ON COLUMN pattern_disable_events.event_id IS 'Idempotency key to prevent duplicate event processing. Callers must provide a unique UUID per logical event.';

-- Event type
COMMENT ON COLUMN pattern_disable_events.event_type IS 'Event type: disabled (pattern cannot be used) or re_enabled (pattern restored to active use)';

-- Target
COMMENT ON COLUMN pattern_disable_events.pattern_id IS 'Specific pattern UUID to disable/enable. NULL if targeting by pattern_class instead.';
COMMENT ON COLUMN pattern_disable_events.pattern_class IS 'Pattern class name to disable/enable all patterns of that class. NULL if targeting specific pattern_id.';

-- Audit fields
COMMENT ON COLUMN pattern_disable_events.reason IS 'Required explanation for the disable/enable action (audit trail)';
COMMENT ON COLUMN pattern_disable_events.event_at IS 'Timestamp when the disable/enable action occurred (business time)';
COMMENT ON COLUMN pattern_disable_events.actor IS 'Identity of who/what performed the action (user email, system name, or automated process identifier)';
COMMENT ON COLUMN pattern_disable_events.created_at IS 'Timestamp when this event record was inserted into the database (system time)';

-- Constraints
COMMENT ON CONSTRAINT check_target_specified ON pattern_disable_events IS 'Ensures at least one target is specified: either pattern_id (specific pattern) or pattern_class (all patterns of that class)';
