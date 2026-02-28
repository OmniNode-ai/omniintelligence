-- Migration: 019_agent_actions_and_workflow_steps
-- Description: Formalize agent_actions and workflow_steps tables (OMN-2985)
-- Author: omniintelligence
-- Date: 2026-02-28
-- Ticket: OMN-2985
--
-- Context:
--   These tables were created manually via raw DDL on 2026-02-28. This migration
--   formalizes them so they exist in all environments (fresh deploys, CI, DB wipes).
--
--   agent_actions: per-tool-call records written by the PostToolUse handler.
--     Read by dispatch_handler_pattern_learning.py to build session snapshots.
--
--   workflow_steps: per-step records for workflow tracking.
--     Read by dispatch_handler_pattern_learning.py to determine session outcome.
--
-- Idempotency:
--   All statements use IF NOT EXISTS so re-applying this migration is safe.
--   Running on a DB that already has these tables (from the manual DDL) is a no-op.
--
-- Rollback: rollback/019_rollback.sql

-- ============================================================================
-- Table: agent_actions
-- Per-tool-call records written by the PostToolUse handler.
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_actions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID,
    action_type     TEXT,
    tool_name       TEXT,
    file_path       TEXT,
    status          TEXT,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_actions_session_id
    ON agent_actions (session_id);

CREATE INDEX IF NOT EXISTS idx_agent_actions_created_at
    ON agent_actions (created_at);

-- ============================================================================
-- Table: workflow_steps
-- Per-step records for workflow tracking.
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_steps (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID,
    step_name       TEXT,
    status          TEXT,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_session_id
    ON workflow_steps (session_id);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE agent_actions IS
    'Per-tool-call records written by the PostToolUse handler. '
    'Queried by dispatch_handler_pattern_learning to build session snapshots. '
    'OMN-2985.';

COMMENT ON COLUMN agent_actions.session_id IS
    'Session identifier linking actions to a Claude Code session.';

COMMENT ON COLUMN agent_actions.action_type IS
    'Category of action (e.g. file_read, file_write, bash_exec).';

COMMENT ON COLUMN agent_actions.tool_name IS
    'Name of the Claude tool invoked (e.g. Read, Write, Bash).';

COMMENT ON COLUMN agent_actions.file_path IS
    'File path operated on (NULL if not a file operation).';

COMMENT ON COLUMN agent_actions.status IS
    'Outcome of the tool call (e.g. success, error).';

COMMENT ON COLUMN agent_actions.error_message IS
    'Error detail when status is error; NULL otherwise.';

COMMENT ON TABLE workflow_steps IS
    'Per-step records for workflow tracking. '
    'Queried by dispatch_handler_pattern_learning to determine session outcome. '
    'OMN-2985.';

COMMENT ON COLUMN workflow_steps.session_id IS
    'Session identifier linking steps to a Claude Code session.';

COMMENT ON COLUMN workflow_steps.step_name IS
    'Name of the workflow step (e.g. implement, local_review, create_pr).';

COMMENT ON COLUMN workflow_steps.status IS
    'Step outcome (e.g. completed, failed, skipped).';

COMMENT ON COLUMN workflow_steps.started_at IS
    'Timestamp when the step began execution.';

COMMENT ON COLUMN workflow_steps.completed_at IS
    'Timestamp when the step finished; NULL if still running or not recorded.';
