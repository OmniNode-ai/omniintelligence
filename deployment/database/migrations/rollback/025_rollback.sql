-- Rollback Migration 025: Review Calibration Runs
-- Ticket: OMN-6170

-- Drop indexes first
DROP INDEX IF EXISTS idx_calibration_event_outbox_unpublished;
DROP INDEX IF EXISTS idx_review_calibration_runs_dedup;
DROP INDEX IF EXISTS idx_review_calibration_runs_created_at;
DROP INDEX IF EXISTS idx_review_calibration_runs_challenger_created;

-- Drop tables
DROP TABLE IF EXISTS calibration_event_outbox;
DROP TABLE IF EXISTS review_calibration_model_scores;
DROP TABLE IF EXISTS review_calibration_runs;
