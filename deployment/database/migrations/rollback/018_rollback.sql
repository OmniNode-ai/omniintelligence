-- Rollback: 018_migrate_routing_feedback_scores_outcome_raw
-- Description: Revert routing_feedback_scores to pre-OMN-2935 schema
-- Ticket: OMN-2935

-- Drop new unique constraint
ALTER TABLE routing_feedback_scores
    DROP CONSTRAINT IF EXISTS uq_routing_feedback_scores_session;

-- Drop new indexes
DROP INDEX IF EXISTS idx_routing_feedback_scores_agent_selected;
DROP INDEX IF EXISTS idx_routing_feedback_scores_injection_occurred;

-- Drop new columns
ALTER TABLE routing_feedback_scores
    DROP COLUMN IF EXISTS injection_occurred,
    DROP COLUMN IF EXISTS patterns_injected_count,
    DROP COLUMN IF EXISTS tool_calls_count,
    DROP COLUMN IF EXISTS duration_ms,
    DROP COLUMN IF EXISTS agent_selected,
    DROP COLUMN IF EXISTS routing_confidence;

-- Restore deprecated columns
ALTER TABLE routing_feedback_scores
    ADD COLUMN IF NOT EXISTS correlation_id  UUID NOT NULL DEFAULT gen_random_uuid(),
    ADD COLUMN IF NOT EXISTS stage           TEXT NOT NULL DEFAULT 'session_end',
    ADD COLUMN IF NOT EXISTS outcome         TEXT NOT NULL DEFAULT 'success' CHECK (outcome IN ('success', 'failed'));

-- Restore composite unique constraint
ALTER TABLE routing_feedback_scores
    ADD CONSTRAINT uq_routing_feedback_scores_key
        UNIQUE (session_id, correlation_id, stage);
