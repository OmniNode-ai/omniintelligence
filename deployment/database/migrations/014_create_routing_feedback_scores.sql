-- Migration: 014_create_routing_feedback_scores
-- Description: Create routing_feedback_scores table for idempotent routing feedback processing
-- Author: omniintelligence
-- Date: 2026-02-20
-- Ticket: OMN-2366
--
-- This table receives routing.feedback events from omniclaude's session-end hook.
-- The composite unique key (session_id, correlation_id, stage) enforces idempotency
-- for at-least-once Kafka delivery semantics.
--
-- Idempotency contract:
--   ON CONFLICT (session_id, correlation_id, stage) DO UPDATE SET processed_at = EXCLUDED.processed_at
--   Re-processing the same event updates only the timestamp; all other fields are unchanged.
--
-- Dependencies: 000_extensions.sql (for uuid-ossp if needed)

-- ============================================================================
-- Create routing_feedback_scores table
-- ============================================================================

CREATE TABLE IF NOT EXISTS routing_feedback_scores (
    -- Surrogate primary key for FK references from future tables
    id                  UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- Idempotency key: composite unique constraint
    -- session_id: opaque string from omniclaude (may be UUID or short string)
    session_id          TEXT        NOT NULL,
    -- correlation_id: distributed tracing ID from the Kafka event envelope
    correlation_id      UUID        NOT NULL,
    -- stage: hook stage that emitted the event (currently always 'session_end')
    stage               TEXT        NOT NULL DEFAULT 'session_end',

    -- Feedback payload
    -- outcome: 'success' or 'failed' from omniclaude session outcome
    outcome             TEXT        NOT NULL CHECK (outcome IN ('success', 'failed')),

    -- Audit fields
    -- processed_at: when this node processed the event (updated on idempotent re-delivery)
    processed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- created_at: when the row was first inserted (immutable after creation)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_routing_feedback_scores PRIMARY KEY (id),
    CONSTRAINT uq_routing_feedback_scores_key
        UNIQUE (session_id, correlation_id, stage)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Index for querying all feedback for a session (analytics, debugging)
CREATE INDEX IF NOT EXISTS idx_routing_feedback_scores_session_id
    ON routing_feedback_scores(session_id);

-- Index for time-range queries (e.g., metrics dashboards, decay analysis)
CREATE INDEX IF NOT EXISTS idx_routing_feedback_scores_processed_at
    ON routing_feedback_scores(processed_at DESC);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE routing_feedback_scores IS
    'Idempotent routing feedback records from omniclaude session-end hook. '
    'Unique on (session_id, correlation_id, stage). OMN-2366.';

COMMENT ON COLUMN routing_feedback_scores.session_id IS
    'Session identifier from omniclaude (opaque string, not enforced as UUID).';

COMMENT ON COLUMN routing_feedback_scores.correlation_id IS
    'Distributed tracing correlation ID from the Kafka event envelope.';

COMMENT ON COLUMN routing_feedback_scores.stage IS
    'Hook stage that emitted the event. Currently always session_end.';

COMMENT ON COLUMN routing_feedback_scores.outcome IS
    'Session outcome: success or failed. Source: omniclaude routing guardrails.';

COMMENT ON COLUMN routing_feedback_scores.processed_at IS
    'When node_routing_feedback_effect processed this event. '
    'Updated on idempotent re-delivery (ON CONFLICT DO UPDATE).';

COMMENT ON COLUMN routing_feedback_scores.created_at IS
    'When the row was first inserted. Immutable after creation. '
    'Immutability is enforced at the application layer (ON CONFLICT DO UPDATE '
    'does not include created_at in the SET clause), not by a database constraint.';
