-- Migration: 017_create_objective_evaluations
-- Description: Create objective_evaluations table for storing EvaluationResult per run
-- Author: omniintelligence
-- Date: 2026-02-24
-- Ticket: OMN-2578
--
-- This table stores the output of NodeScoringReducerCompute (OMN-2545) after each
-- agent session evaluation. It is the primary storage for the objective evaluation
-- pipeline and serves as the source of truth for:
--   - Dashboard analytics (omnidash)
--   - Policy state updates (NodePolicyStateReducer, OMN-2557)
--   - Replay verification (bundle_fingerprint + run_id uniqueness)
--
-- Idempotency contract:
--   ON CONFLICT (run_id, bundle_fingerprint) DO UPDATE SET evaluated_at = EXCLUDED.evaluated_at
--   Re-processing the same (run_id, bundle) only updates the timestamp.
--
-- Dependencies:
--   - 000_extensions.sql (for gen_random_uuid())

-- ============================================================================
-- Create objective_evaluations table
-- ============================================================================

CREATE TABLE IF NOT EXISTS objective_evaluations (
    -- Surrogate primary key
    id                      UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- Run identification
    -- run_id: correlation_id cast to string from the STOP hook event
    run_id                  TEXT        NOT NULL,
    -- session_id: Claude Code session identifier (opaque string, not enforced as UUID)
    session_id              TEXT        NOT NULL,
    -- task_class: task class used to select the ObjectiveSpec
    task_class              TEXT        NOT NULL DEFAULT 'default',

    -- Evidence bundle identification
    -- bundle_fingerprint: SHA-256 hex digest of the serialized EvidenceItems
    -- Used for replay verification: same evidence always produces same fingerprint
    bundle_fingerprint      TEXT        NOT NULL,

    -- Evaluation result
    -- passed: true if all hard gates passed, false if any gate failed
    passed                  BOOLEAN     NOT NULL,
    -- failures: array of gate IDs that failed (empty if passed=true)
    failures                TEXT[]      NOT NULL DEFAULT '{}',

    -- Score vector (six dimensions, all in [0.0, 1.0])
    -- All-zero when passed=false (per ModelEvaluationResult invariants)
    score_correctness       FLOAT8      NOT NULL DEFAULT 0.0
                                        CHECK (score_correctness >= 0.0 AND score_correctness <= 1.0),
    score_safety            FLOAT8      NOT NULL DEFAULT 0.0
                                        CHECK (score_safety >= 0.0 AND score_safety <= 1.0),
    score_cost              FLOAT8      NOT NULL DEFAULT 0.0
                                        CHECK (score_cost >= 0.0 AND score_cost <= 1.0),
    score_latency           FLOAT8      NOT NULL DEFAULT 0.0
                                        CHECK (score_latency >= 0.0 AND score_latency <= 1.0),
    score_maintainability   FLOAT8      NOT NULL DEFAULT 0.0
                                        CHECK (score_maintainability >= 0.0 AND score_maintainability <= 1.0),
    score_human_time        FLOAT8      NOT NULL DEFAULT 0.0
                                        CHECK (score_human_time >= 0.0 AND score_human_time <= 1.0),

    -- Audit fields
    -- evaluated_at: ISO-8601 UTC timestamp when evaluation was computed
    -- Updated on idempotent re-delivery (ON CONFLICT DO UPDATE)
    evaluated_at            TEXT        NOT NULL,
    -- created_at: when the row was first inserted (immutable after creation)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_objective_evaluations PRIMARY KEY (id),
    -- Replay invariant: same run with same evidence always produces same result
    CONSTRAINT uq_objective_evaluations_run_bundle
        UNIQUE (run_id, bundle_fingerprint)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Index for session-level queries (get all evaluations for a session)
CREATE INDEX IF NOT EXISTS idx_objective_evaluations_session_id
    ON objective_evaluations(session_id);

-- Index for run-level queries (get evaluation for a specific run)
CREATE INDEX IF NOT EXISTS idx_objective_evaluations_run_id
    ON objective_evaluations(run_id);

-- Index for time-range queries (analytics dashboards, decay analysis)
CREATE INDEX IF NOT EXISTS idx_objective_evaluations_created_at
    ON objective_evaluations(created_at DESC);

-- Index for task-class filtering (per-class score analytics)
CREATE INDEX IF NOT EXISTS idx_objective_evaluations_task_class
    ON objective_evaluations(task_class);

-- Index for pass/fail queries (rate metrics, policy state triggers)
CREATE INDEX IF NOT EXISTS idx_objective_evaluations_passed
    ON objective_evaluations(passed);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE objective_evaluations IS
    'Objective evaluation results from the scoring pipeline. '
    'One row per (run_id, bundle_fingerprint) pair. '
    'Unique on (run_id, bundle_fingerprint) for replay integrity. OMN-2578.';

COMMENT ON COLUMN objective_evaluations.run_id IS
    'Agent run identifier (correlation_id from STOP hook event cast to string). '
    'Used as Kafka partition key for RunEvaluatedEvent.';

COMMENT ON COLUMN objective_evaluations.session_id IS
    'Claude Code session identifier (opaque string, not enforced as UUID).';

COMMENT ON COLUMN objective_evaluations.task_class IS
    'Task class used to select the ObjectiveSpec for this evaluation. '
    'Defaults to ''default'' when no task class is available.';

COMMENT ON COLUMN objective_evaluations.bundle_fingerprint IS
    'SHA-256 hex digest of the serialized EvidenceBundle items. '
    'Content-addressed: same items always produce same fingerprint. '
    'Together with run_id, forms the replay integrity key.';

COMMENT ON COLUMN objective_evaluations.passed IS
    'True if all hard gates passed. False if any gate failed. '
    'When false, all score_* columns are 0.0 per EvaluationResult invariants.';

COMMENT ON COLUMN objective_evaluations.failures IS
    'Array of gate IDs that failed. Empty array when passed=true.';

COMMENT ON COLUMN objective_evaluations.score_correctness IS
    'Correctness dimension of the ScoreVector. 0.0 when passed=false.';

COMMENT ON COLUMN objective_evaluations.score_safety IS
    'Safety dimension of the ScoreVector. 0.0 when passed=false.';

COMMENT ON COLUMN objective_evaluations.score_cost IS
    'Cost efficiency dimension of the ScoreVector. 0.0 when passed=false.';

COMMENT ON COLUMN objective_evaluations.score_latency IS
    'Latency dimension of the ScoreVector. 0.0 when passed=false.';

COMMENT ON COLUMN objective_evaluations.score_maintainability IS
    'Maintainability dimension of the ScoreVector. 0.0 when passed=false.';

COMMENT ON COLUMN objective_evaluations.score_human_time IS
    'Human time saved dimension of the ScoreVector. 0.0 when passed=false.';

COMMENT ON COLUMN objective_evaluations.evaluated_at IS
    'ISO-8601 UTC timestamp when evaluation was computed. '
    'Updated on idempotent re-delivery (ON CONFLICT DO UPDATE).';

COMMENT ON COLUMN objective_evaluations.created_at IS
    'When the row was first inserted. Immutable after creation.';
