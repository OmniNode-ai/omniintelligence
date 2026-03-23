-- Migration 025: Review Calibration Runs
-- Ticket: OMN-6170
-- Creates tables for the Review Calibration Loop (OMN-6164)

-- Table 1: Per-run calibration record with metrics and alignment details
CREATE TABLE IF NOT EXISTS review_calibration_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          TEXT NOT NULL,
    ground_truth_model TEXT NOT NULL,
    challenger_model TEXT NOT NULL,
    precision_score FLOAT8 NOT NULL DEFAULT 0.0,
    recall_score    FLOAT8 NOT NULL DEFAULT 0.0,
    f1_score        FLOAT8 NOT NULL DEFAULT 0.0,
    noise_ratio     FLOAT8 NOT NULL DEFAULT 0.0,
    true_positives  INT NOT NULL DEFAULT 0,
    false_positives INT NOT NULL DEFAULT 0,
    false_negatives INT NOT NULL DEFAULT 0,
    finding_count   INT NOT NULL DEFAULT 0,
    alignment_details JSONB NOT NULL DEFAULT '[]'::jsonb,
    fewshot_snapshot JSONB,
    human_overrides JSONB,
    prompt_version  TEXT NOT NULL DEFAULT '',
    embedding_model_version TEXT,
    config_version  TEXT NOT NULL DEFAULT '',
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index: challenger + created_at for per-model trend queries
CREATE INDEX IF NOT EXISTS idx_review_calibration_runs_challenger_created
    ON review_calibration_runs (challenger_model, created_at DESC);

-- Index: created_at for time-range queries
CREATE INDEX IF NOT EXISTS idx_review_calibration_runs_created_at
    ON review_calibration_runs (created_at DESC);

-- Index: dedup on (run_id, challenger_model)
CREATE UNIQUE INDEX IF NOT EXISTS idx_review_calibration_runs_dedup
    ON review_calibration_runs (run_id, challenger_model);


-- Table 2: Calibration-derived EMA scores per model
CREATE TABLE IF NOT EXISTS review_calibration_model_scores (
    model_id        TEXT NOT NULL,
    reference_model TEXT NOT NULL,
    calibration_score FLOAT8 NOT NULL DEFAULT 0.0,
    precision_ema   FLOAT8 NOT NULL DEFAULT 0.0,
    recall_ema      FLOAT8 NOT NULL DEFAULT 0.0,
    f1_ema          FLOAT8 NOT NULL DEFAULT 0.0,
    noise_ema       FLOAT8 NOT NULL DEFAULT 0.0,
    run_count       INT NOT NULL DEFAULT 0,
    last_run_id     TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (model_id, reference_model)
);


-- Table 3: Transactional outbox for Kafka events
CREATE TABLE IF NOT EXISTS calibration_event_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT NOT NULL,
    event_payload   JSONB NOT NULL,
    published       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at    TIMESTAMPTZ
);

-- Index: unpublished events for outbox polling
CREATE INDEX IF NOT EXISTS idx_calibration_event_outbox_unpublished
    ON calibration_event_outbox (created_at ASC)
    WHERE published = false;
