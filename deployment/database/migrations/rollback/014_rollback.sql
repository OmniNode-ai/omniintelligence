-- Rollback: 014_create_routing_feedback_scores
-- Description: Drop routing_feedback_scores table and all associated objects
-- Author: omniintelligence
-- Date: 2026-02-20
-- Ticket: OMN-2366

-- Drop indexes first (CASCADE would handle these, but explicit is safer)
DROP INDEX IF EXISTS idx_routing_feedback_scores_processed_at;
DROP INDEX IF EXISTS idx_routing_feedback_scores_session_id;

-- Drop table (CASCADE removes all dependent objects)
DROP TABLE IF EXISTS routing_feedback_scores CASCADE;
