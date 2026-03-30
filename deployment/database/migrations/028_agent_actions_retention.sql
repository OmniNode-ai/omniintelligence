-- Migration: 028_agent_actions_retention
-- Purpose: Add index to support efficient retention cleanup on agent_actions [OMN-7013]

-- Ensure index exists for cleanup queries
CREATE INDEX IF NOT EXISTS idx_agent_actions_created_at ON agent_actions (created_at);

-- One-time purge of rows older than 30 days
DELETE FROM agent_actions
WHERE created_at < NOW() - INTERVAL '30 days';
