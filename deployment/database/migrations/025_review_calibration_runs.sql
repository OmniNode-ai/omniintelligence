-- Migration 025: Review Calibration Runs
-- Reference: OMN-6170 (epic OMN-6164)
--
-- Creates tables for the Review Calibration Loop:
-- 1. review_calibration_runs - Per-run calibration records
-- 2. review_calibration_model_scores - EMA-updated calibration scores per model+reference
-- 3. calibration_event_outbox - Transactional outbox for Kafka event emission

CREATE TABLE IF NOT EXISTS review_calibration_runs (
    id                      UUID        NOT NULL DEFAULT gen_random_uuid(),
    run_id                  TEXT        NOT NULL,
    ground_truth_model      TEXT        NOT NULL,
    challenger_model        TEXT        NOT NULL,
    true_positives          INTEGER     NOT NULL DEFAULT 0,
    false_positives         INTEGER     NOT NULL DEFAULT 0,
    false_negatives         INTEGER     NOT NULL DEFAULT 0,
    precision_score         FLOAT8      NOT NULL DEFAULT 0.0,
    recall_score            FLOAT8      NOT NULL DEFAULT 0.0,
    f1_score                FLOAT8      NOT NULL DEFAULT 0.0,
    noise_ratio             FLOAT8      NOT NULL DEFAULT 0.0,
    ground_truth_count      INTEGER     NOT NULL DEFAULT 0,
    challenger_count        INTEGER     NOT NULL DEFAULT 0,
    prompt_version          TEXT        NOT NULL,
    content_hash            TEXT        NOT NULL,
    embedding_model_version TEXT,
    config_version          TEXT,
    alignment_details       JSONB       NOT NULL DEFAULT '[]'::jsonb,
    fewshot_snapshot        JSONB,
    human_overrides         JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_review_calibration_runs PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_review_calibration_runs_challenger
    ON review_calibration_runs (challenger_model, created_at);

CREATE INDEX IF NOT EXISTS idx_review_calibration_runs_created
    ON review_calibration_runs (created_at);

-- Unique constraint for idempotent save_run within the same invocation
CREATE UNIQUE INDEX IF NOT EXISTS idx_review_calibration_runs_dedup
    ON review_calibration_runs (run_id, challenger_model);

-- Dedicated calibration scores table (separate from plan_reviewer_model_accuracy)
-- Composite PK ensures independent EMA history per (challenger, reference) pair
CREATE TABLE IF NOT EXISTS review_calibration_model_scores (
    model_id                TEXT        NOT NULL,
    reference_model         TEXT        NOT NULL,
    calibration_score       FLOAT8      NOT NULL DEFAULT 0.0,
    calibration_run_count   INTEGER     NOT NULL DEFAULT 0,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_review_calibration_model_scores PRIMARY KEY (model_id, reference_model)
);

-- Transactional outbox for calibration Kafka events
CREATE TABLE IF NOT EXISTS calibration_event_outbox (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    event_topic     TEXT        NOT NULL,
    event_key       TEXT        NOT NULL,
    event_payload   JSONB       NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at    TIMESTAMPTZ,
    CONSTRAINT pk_calibration_event_outbox PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_calibration_event_outbox_unpublished
    ON calibration_event_outbox (created_at)
    WHERE published_at IS NULL;
