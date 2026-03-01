-- Rollback: 020_plan_reviewer_accuracy_and_runs
-- Description: Drop plan_reviewer_model_accuracy and plan_reviewer_strategy_runs tables
-- Ticket: OMN-3284
--
-- WARNING: This rollback drops tables and all their data.
-- Only apply if node_plan_reviewer_multi_compute is not running.

DROP TABLE IF EXISTS plan_reviewer_strategy_runs;
DROP TABLE IF EXISTS plan_reviewer_model_accuracy;
