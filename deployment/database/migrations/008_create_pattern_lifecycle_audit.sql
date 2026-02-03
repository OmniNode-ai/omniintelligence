-- Migration: 008_create_pattern_lifecycle_audit
-- Description: Create pattern_lifecycle_transitions table for auditing pattern status changes
-- Author: omniintelligence
-- Date: 2026-02-02
-- Ticket: OMN-1805
--
-- Dependencies: 005_create_learned_patterns.sql (pattern_id references learned_patterns)
-- Note: This audit table tracks all pattern status transitions as part of the reducer-first
--       state machine implementation. The unique constraint on (request_id, pattern_id)
--       ensures idempotent transition recording.

-- ============================================================================
-- Pattern Lifecycle Transitions Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS pattern_lifecycle_transitions (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Request tracking (for idempotency)
    request_id UUID NOT NULL,

    -- Pattern reference
    -- NOTE: Using ON DELETE RESTRICT (not CASCADE) to preserve audit trail.
    -- Audit records must never be silently deleted when parent patterns are removed.
    -- If a pattern needs deletion, audit history should be explicitly archived first.
    pattern_id UUID NOT NULL REFERENCES learned_patterns(id) ON DELETE RESTRICT,

    -- State transition
    from_status VARCHAR(20) NOT NULL,
    to_status VARCHAR(20) NOT NULL,
    trigger VARCHAR(50) NOT NULL,

    -- Tracing and attribution
    correlation_id UUID,
    actor VARCHAR(100),
    reason TEXT,

    -- Snapshot of gate conditions at transition time
    gate_snapshot JSONB,

    -- Timing
    transition_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Idempotency constraint: same request can only transition same pattern once
    CONSTRAINT unique_request_pattern_transition UNIQUE (request_id, pattern_id)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Primary lookup: find transitions for a pattern
CREATE INDEX IF NOT EXISTS idx_pattern_lifecycle_pattern_id
    ON pattern_lifecycle_transitions(pattern_id);

-- Time-based queries (analytics, cleanup, audit trails)
CREATE INDEX IF NOT EXISTS idx_pattern_lifecycle_transition_at
    ON pattern_lifecycle_transitions(transition_at);

-- Correlation tracing
CREATE INDEX IF NOT EXISTS idx_pattern_lifecycle_correlation_id
    ON pattern_lifecycle_transitions(correlation_id)
    WHERE correlation_id IS NOT NULL;

-- Query by trigger type (for metrics on promotion/demotion rates)
CREATE INDEX IF NOT EXISTS idx_pattern_lifecycle_trigger
    ON pattern_lifecycle_transitions(trigger);

-- Query by status transition (for analyzing transition patterns)
CREATE INDEX IF NOT EXISTS idx_pattern_lifecycle_from_to_status
    ON pattern_lifecycle_transitions(from_status, to_status);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE pattern_lifecycle_transitions IS 'Audit table tracking all pattern status transitions for the reducer-first state machine';

COMMENT ON COLUMN pattern_lifecycle_transitions.id IS 'Primary key - unique identifier for this transition record';
COMMENT ON COLUMN pattern_lifecycle_transitions.request_id IS 'Request ID for idempotent transition tracking';
COMMENT ON COLUMN pattern_lifecycle_transitions.pattern_id IS 'Reference to the pattern that transitioned. Uses ON DELETE RESTRICT to preserve audit trail.';
COMMENT ON COLUMN pattern_lifecycle_transitions.from_status IS 'Previous status before transition (candidate, provisional, validated, deprecated)';
COMMENT ON COLUMN pattern_lifecycle_transitions.to_status IS 'New status after transition (candidate, provisional, validated, deprecated)';
COMMENT ON COLUMN pattern_lifecycle_transitions.trigger IS 'Event or condition that triggered the transition';
COMMENT ON COLUMN pattern_lifecycle_transitions.correlation_id IS 'Distributed tracing ID for linking across services';
COMMENT ON COLUMN pattern_lifecycle_transitions.actor IS 'Entity that initiated the transition (system, user, agent)';
COMMENT ON COLUMN pattern_lifecycle_transitions.reason IS 'Human-readable explanation for the transition';
COMMENT ON COLUMN pattern_lifecycle_transitions.gate_snapshot IS 'JSONB snapshot of gate conditions at transition time (metrics, thresholds)';
COMMENT ON COLUMN pattern_lifecycle_transitions.transition_at IS 'When the transition occurred';

COMMENT ON CONSTRAINT unique_request_pattern_transition ON pattern_lifecycle_transitions IS 'Ensures idempotent transition recording - same request can only transition same pattern once';
