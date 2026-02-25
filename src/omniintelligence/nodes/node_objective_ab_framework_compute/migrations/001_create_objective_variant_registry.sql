-- SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
-- SPDX-License-Identifier: MIT
--
-- Migration: 001_create_objective_variant_registry.sql
-- Ticket: OMN-2571
-- Description: Creates objective_variant_registry and objective_variant_evaluations
--              tables for A/B objective testing framework.

-- ---------------------------------------------------------------------------
-- objective_variant_registry: registry of active variants per registry_id
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS objective_variant_registry (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registry_id                 TEXT NOT NULL,
    variant_id                  TEXT NOT NULL,
    objective_id                TEXT NOT NULL,
    objective_version           TEXT NOT NULL,
    role                        TEXT NOT NULL CHECK (role IN ('active', 'shadow')),
    traffic_weight              DOUBLE PRECISION NOT NULL CHECK (traffic_weight >= 0.0 AND traffic_weight <= 1.0),
    is_active                   BOOLEAN NOT NULL DEFAULT TRUE,
    significance_threshold      DOUBLE PRECISION NOT NULL DEFAULT 0.05,
    min_runs_for_significance   INTEGER NOT NULL DEFAULT 100,
    divergence_threshold        DOUBLE PRECISION NOT NULL DEFAULT 0.1,
    created_at_utc              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at_utc              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (registry_id, variant_id)
);

-- Index on registry_id for batch queries
CREATE INDEX IF NOT EXISTS idx_variant_registry_registry_id
    ON objective_variant_registry (registry_id);

-- Index on role for active/shadow queries
CREATE INDEX IF NOT EXISTS idx_variant_registry_role
    ON objective_variant_registry (role)
    WHERE is_active = TRUE;

-- ---------------------------------------------------------------------------
-- objective_variant_evaluations: per-variant evaluation results for each run
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS objective_variant_evaluations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              TEXT NOT NULL,
    variant_id          TEXT NOT NULL,
    registry_id         TEXT NOT NULL,
    objective_id        TEXT NOT NULL,
    objective_version   TEXT NOT NULL,
    role                TEXT NOT NULL,
    passed              BOOLEAN NOT NULL,
    score_correctness   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    score_safety        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    score_cost          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    score_latency       DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    score_maintainability DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    score_human_time    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    drives_policy_state BOOLEAN NOT NULL DEFAULT FALSE,
    divergence_detected BOOLEAN NOT NULL DEFAULT FALSE,
    evaluated_at_utc    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index on run_id for per-run queries
CREATE INDEX IF NOT EXISTS idx_variant_evals_run_id
    ON objective_variant_evaluations (run_id);

-- Index on variant_id for significance counting
CREATE INDEX IF NOT EXISTS idx_variant_evals_variant_id
    ON objective_variant_evaluations (variant_id);

-- ---------------------------------------------------------------------------
-- objective_variant_win_counts: running tallies for significance tracking
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS objective_variant_win_counts (
    variant_id          TEXT PRIMARY KEY,
    registry_id         TEXT NOT NULL,
    run_count           INTEGER NOT NULL DEFAULT 0,
    shadow_win_count    INTEGER NOT NULL DEFAULT 0,
    upgrade_emitted     BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at_utc      TIMESTAMPTZ NOT NULL DEFAULT now()
);
