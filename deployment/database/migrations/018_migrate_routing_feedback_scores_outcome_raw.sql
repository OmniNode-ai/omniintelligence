-- Migration: 018_migrate_routing_feedback_scores_outcome_raw
-- Description: Migrate routing_feedback_scores to consume routing-outcome-raw.v1 (OMN-2935)
-- Author: omniintelligence
-- Date: 2026-02-27
-- Ticket: OMN-2935
--
-- OMN-2935: The routing feedback loop was broken because node_routing_feedback_effect
-- subscribed to the deprecated onex.evt.omniclaude.routing-feedback.v1 topic. This
-- migration updates the table schema to store the new payload fields from
-- onex.evt.omniclaude.routing-outcome-raw.v1.
--
-- Changes:
--   1. Add new columns for raw signal fields from ModelSessionRawOutcomePayload
--   2. Drop the old (session_id, correlation_id, stage) composite unique constraint
--   3. Add new (session_id) unique constraint (correlation_id no longer in payload)
--   4. Drop deprecated columns: correlation_id, stage, outcome (not in new payload)
--
-- The old rows (from the deprecated topic, if any) remain but will no longer be
-- updated since the node now subscribes to the new topic.
--
-- Rollback: 018_rollback.sql

-- ============================================================================
-- Step 1: Add new columns for raw signal fields
-- ============================================================================

ALTER TABLE routing_feedback_scores
    ADD COLUMN IF NOT EXISTS injection_occurred       BOOLEAN     NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS patterns_injected_count  INTEGER     NOT NULL DEFAULT 0    CHECK (patterns_injected_count >= 0),
    ADD COLUMN IF NOT EXISTS tool_calls_count         INTEGER     NOT NULL DEFAULT 0    CHECK (tool_calls_count >= 0),
    ADD COLUMN IF NOT EXISTS duration_ms              INTEGER     NOT NULL DEFAULT 0    CHECK (duration_ms >= 0),
    ADD COLUMN IF NOT EXISTS agent_selected           TEXT        NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS routing_confidence       FLOAT       NOT NULL DEFAULT 0.0  CHECK (routing_confidence >= 0.0 AND routing_confidence <= 1.0);

-- ============================================================================
-- Step 2: Drop the old composite unique constraint
-- ============================================================================

ALTER TABLE routing_feedback_scores
    DROP CONSTRAINT IF EXISTS uq_routing_feedback_scores_key;

-- ============================================================================
-- Step 3: Add the new (session_id) unique constraint
-- ============================================================================

ALTER TABLE routing_feedback_scores
    ADD CONSTRAINT uq_routing_feedback_scores_session
        UNIQUE (session_id);

-- ============================================================================
-- Step 4: Drop deprecated columns (correlation_id, stage, outcome)
--
-- These were part of the old routing-feedback.v1 payload and are no longer
-- emitted by omniclaude in routing-outcome-raw.v1.
-- ============================================================================

ALTER TABLE routing_feedback_scores
    DROP COLUMN IF EXISTS correlation_id,
    DROP COLUMN IF EXISTS stage,
    DROP COLUMN IF EXISTS outcome;

-- ============================================================================
-- Step 5: Add indexes for new query patterns
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_routing_feedback_scores_agent_selected
    ON routing_feedback_scores(agent_selected)
    WHERE agent_selected <> '';

CREATE INDEX IF NOT EXISTS idx_routing_feedback_scores_injection_occurred
    ON routing_feedback_scores(injection_occurred);

-- ============================================================================
-- Step 6: Update comments
-- ============================================================================

COMMENT ON TABLE routing_feedback_scores IS
    'Idempotent routing-outcome-raw records from omniclaude session-end hook. '
    'Unique on (session_id). OMN-2366, OMN-2935.';

COMMENT ON COLUMN routing_feedback_scores.injection_occurred IS
    'Whether context injection happened during the session. Source: omniclaude routing-outcome-raw.v1';

COMMENT ON COLUMN routing_feedback_scores.patterns_injected_count IS
    'Number of patterns injected this session (0 if injection_occurred is false).';

COMMENT ON COLUMN routing_feedback_scores.tool_calls_count IS
    'Total tool calls observed during the session.';

COMMENT ON COLUMN routing_feedback_scores.duration_ms IS
    'Session duration in milliseconds (0 if unknown).';

COMMENT ON COLUMN routing_feedback_scores.agent_selected IS
    'Agent name selected by routing (empty string if none selected).';

COMMENT ON COLUMN routing_feedback_scores.routing_confidence IS
    'Routing confidence score from the router (0.0-1.0).';
