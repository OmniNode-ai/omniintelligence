-- Migration: 020_plan_reviewer_accuracy_and_runs
-- Description: Create tables for multi-LLM plan reviewer model accuracy tracking
--              and strategy run history (OMN-3284)
-- Author: omniintelligence
-- Date: 2026-03-01
-- Ticket: OMN-3284
--
-- Context:
--   The multi-LLM plan reviewer (node_plan_reviewer_multi_compute) needs:
--
--   plan_reviewer_model_accuracy: Tracks per-model accuracy scores so the
--     orchestrator can weight votes by historical correctness. Seeded with
--     the four initial model IDs at a neutral 0.5 score.
--
--   plan_reviewer_strategy_runs: Audit log of every review run, recording
--     which strategy and models were used, plan content hash, findings
--     summary, and performance metrics.
--
-- Idempotency:
--   All statements use IF NOT EXISTS / ON CONFLICT DO NOTHING so
--   re-applying this migration is safe.
--
-- Rollback: rollback/020_rollback.sql

-- ============================================================================
-- Table: plan_reviewer_model_accuracy
-- Per-model accuracy scores for weighted voting.
-- ============================================================================

CREATE TABLE IF NOT EXISTS plan_reviewer_model_accuracy (
    model_id          TEXT        NOT NULL,
    score_correctness FLOAT8      NOT NULL DEFAULT 0.5,
    run_count         INTEGER     NOT NULL DEFAULT 0,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_plan_reviewer_model_accuracy PRIMARY KEY (model_id)
);

-- Seed the four model IDs with a neutral accuracy score.
-- ON CONFLICT DO NOTHING makes this idempotent.
INSERT INTO plan_reviewer_model_accuracy (model_id) VALUES
    ('qwen3-coder'),
    ('deepseek-r1'),
    ('gemini-flash'),
    ('glm-4')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Table: plan_reviewer_strategy_runs
-- Audit log of every strategy run with full context for analysis.
-- ============================================================================

CREATE TABLE IF NOT EXISTS plan_reviewer_strategy_runs (
    id                       UUID        NOT NULL DEFAULT gen_random_uuid(),
    run_id                   TEXT        NOT NULL,
    strategy                 TEXT        NOT NULL,
    models_used              TEXT[]      NOT NULL,
    plan_text_hash           TEXT        NOT NULL,
    findings_count           INTEGER     NOT NULL DEFAULT 0,
    categories_with_findings TEXT[]      NOT NULL DEFAULT '{}',
    categories_clean         TEXT[]      NOT NULL DEFAULT '{}',
    avg_confidence           FLOAT8,
    tokens_used              INTEGER,
    duration_ms              INTEGER,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_plan_reviewer_strategy_runs PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_plan_reviewer_strategy_runs_run_id
    ON plan_reviewer_strategy_runs (run_id);

CREATE INDEX IF NOT EXISTS idx_plan_reviewer_strategy_runs_strategy
    ON plan_reviewer_strategy_runs (strategy);

CREATE INDEX IF NOT EXISTS idx_plan_reviewer_strategy_runs_created_at
    ON plan_reviewer_strategy_runs (created_at);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE plan_reviewer_model_accuracy IS
    'Per-model accuracy scores for the multi-LLM plan reviewer. '
    'Updated after each run to weight vote contributions by historical correctness. '
    'OMN-3284.';

COMMENT ON COLUMN plan_reviewer_model_accuracy.model_id IS
    'Stable model identifier matching EnumReviewModel values.';

COMMENT ON COLUMN plan_reviewer_model_accuracy.score_correctness IS
    'Running accuracy score in [0.0, 1.0]. Starts at 0.5 (neutral). '
    'Increases when model findings match consensus, decreases otherwise.';

COMMENT ON COLUMN plan_reviewer_model_accuracy.run_count IS
    'Total number of runs contributing to the current score_correctness value.';

COMMENT ON COLUMN plan_reviewer_model_accuracy.updated_at IS
    'Timestamp of last score update.';

COMMENT ON TABLE plan_reviewer_strategy_runs IS
    'Audit log of every multi-LLM plan review run. '
    'Records strategy, models, plan hash, findings summary, and performance metrics. '
    'OMN-3284.';

COMMENT ON COLUMN plan_reviewer_strategy_runs.run_id IS
    'Caller-supplied correlation ID (e.g. ticket ID or session ID).';

COMMENT ON COLUMN plan_reviewer_strategy_runs.strategy IS
    'Review strategy used; matches EnumReviewStrategy values '
    '(panel_vote, specialist_split, sequential_critique, independent_merge).';

COMMENT ON COLUMN plan_reviewer_strategy_runs.models_used IS
    'Array of model IDs that participated in this run.';

COMMENT ON COLUMN plan_reviewer_strategy_runs.plan_text_hash IS
    'SHA-256 hex digest of the plan text reviewed. '
    'Allows deduplication and cross-run comparison.';

COMMENT ON COLUMN plan_reviewer_strategy_runs.findings_count IS
    'Total number of findings surfaced across all models.';

COMMENT ON COLUMN plan_reviewer_strategy_runs.categories_with_findings IS
    'Review categories where at least one model raised a finding.';

COMMENT ON COLUMN plan_reviewer_strategy_runs.categories_clean IS
    'Review categories where all models reported clean.';

COMMENT ON COLUMN plan_reviewer_strategy_runs.avg_confidence IS
    'Average confidence score across all model outputs; NULL if not reported.';

COMMENT ON COLUMN plan_reviewer_strategy_runs.tokens_used IS
    'Total tokens consumed across all model calls; NULL if not tracked.';

COMMENT ON COLUMN plan_reviewer_strategy_runs.duration_ms IS
    'Wall-clock duration of the full review run in milliseconds; NULL if not tracked.';
