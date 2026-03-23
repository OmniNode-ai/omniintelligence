-- Rollback Migration 025: Review Calibration Runs
-- Reference: OMN-6170 (epic OMN-6164)

DROP INDEX IF EXISTS idx_calibration_event_outbox_unpublished;
DROP TABLE IF EXISTS calibration_event_outbox;

DROP TABLE IF EXISTS review_calibration_model_scores;

DROP INDEX IF EXISTS idx_review_calibration_runs_dedup;
DROP INDEX IF EXISTS idx_review_calibration_runs_created;
DROP INDEX IF EXISTS idx_review_calibration_runs_challenger;
DROP TABLE IF EXISTS review_calibration_runs;
