-- Migration: 024_add_agent_name_to_objective_evaluations
-- Description: Add agent_name column to objective_evaluations for dashboard grouping
-- Author: omniintelligence
-- Date: 2026-03-15
-- Ticket: OMN-5048
--
-- The omnidash /objective page groups evaluations by agent_name. This column
-- was missing from the original 017 migration. Backfills existing rows with
-- 'unknown' (matching the ModelRunEvaluatedEvent default).

ALTER TABLE objective_evaluations
    ADD COLUMN IF NOT EXISTS agent_name TEXT NOT NULL DEFAULT 'unknown';

-- Index for agent-level queries (dashboard grouping)
CREATE INDEX IF NOT EXISTS idx_objective_evaluations_agent_name
    ON objective_evaluations(agent_name);

COMMENT ON COLUMN objective_evaluations.agent_name IS
    'Agent name that executed the run (e.g. agent-api, agent-frontend). '
    'Used by omnidash to group evaluations in the /objective dashboard. '
    'Defaults to ''unknown'' for events produced before OMN-5048.';
