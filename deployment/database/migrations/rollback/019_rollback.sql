-- Rollback: 019_agent_actions_and_workflow_steps
-- Description: Drop agent_actions and workflow_steps tables
-- Ticket: OMN-2985
--
-- WARNING: This rollback drops tables and all their data.
-- Only apply if dispatch_handler_pattern_learning.py is not running.

DROP TABLE IF EXISTS agent_actions;
DROP TABLE IF EXISTS workflow_steps;
