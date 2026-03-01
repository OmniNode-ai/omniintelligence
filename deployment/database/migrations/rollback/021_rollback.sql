-- Rollback: 021_create_llm_routing_decisions
-- Description: Drop llm_routing_decisions table and all associated objects
-- Ticket: OMN-3298
--
-- WARNING: This rollback drops the table and all its data.
-- Only apply if node_llm_routing_decision_effect is not running.

-- Drop indexes first (CASCADE would handle these, but explicit is safer)
DROP INDEX IF EXISTS idx_llm_routing_decisions_agreement;
DROP INDEX IF EXISTS idx_llm_routing_decisions_processed_at;
DROP INDEX IF EXISTS idx_llm_routing_decisions_session_id;

-- Drop table (CASCADE removes all dependent objects)
DROP TABLE IF EXISTS llm_routing_decisions CASCADE;
