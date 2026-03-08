-- SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
-- SPDX-License-Identifier: MIT
--
-- Migration: 023_create_debug_intelligence_tables.sql
-- Description: Debug Intelligence Phase 1 — CI failure tracking tables.
-- Ticket: OMN-3556
--
-- Streak semantics:
--   failure_streaks.streak_count  = source of truth for consecutive failure count
--   ci_failure_events.streak_snapshot = historical copy taken AT insertion time
--   NEVER compute consecutive by COUNT(*) on ci_failure_events rows.
--
-- SHA semantics:
--   debug_trigger_records.observed_bad_sha = the SHA that crossed the threshold.
--   This is NOT necessarily the first bad commit — it is the first observed
--   commit after the streak threshold was exceeded. A future bisect phase
--   (Phase 2) will populate suspected_first_bad_sha separately.

-- ---------------------------------------------------------------------------
-- failure_streaks: source of truth for consecutive failure streaks per (repo, branch)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS failure_streaks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo            TEXT NOT NULL,
    branch          TEXT NOT NULL,
    streak_count    INTEGER NOT NULL DEFAULT 0,
    last_sha        TEXT,
    started_at_utc  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at_utc  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repo, branch)
);

CREATE INDEX IF NOT EXISTS idx_failure_streaks_repo_branch
    ON failure_streaks (repo, branch);

-- ---------------------------------------------------------------------------
-- ci_failure_events: individual failure event log
-- Note: streak_snapshot is copied from failure_streaks.streak_count at insertion.
--       Do NOT use COUNT(*) on this table to derive consecutive count.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ci_failure_events (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo                    TEXT NOT NULL,
    branch                  TEXT NOT NULL,
    sha                     TEXT NOT NULL,
    pr_number               INTEGER,
    error_fingerprint       TEXT NOT NULL,
    error_classification    TEXT NOT NULL DEFAULT 'unknown',
    -- streak_snapshot: value of failure_streaks.streak_count at the time this
    -- event was inserted. Historical record only. NOT the live streak count.
    streak_snapshot         INTEGER NOT NULL DEFAULT 0,
    created_at_utc          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ci_failure_events_repo_branch
    ON ci_failure_events (repo, branch);

CREATE INDEX IF NOT EXISTS idx_ci_failure_events_fingerprint
    ON ci_failure_events (error_fingerprint);

CREATE INDEX IF NOT EXISTS idx_ci_failure_events_created_at
    ON ci_failure_events (created_at_utc DESC);

-- ---------------------------------------------------------------------------
-- debug_trigger_records: created when streak_count crosses threshold
--
-- SHA semantics (Phase 1):
--   observed_bad_sha = sha that was present when threshold was first crossed.
--   This is "first commit observed after threshold", not "first bad commit".
--   Phase 2 will add suspected_first_bad_sha via bisect.
--
-- fix_record_id: intentionally no FK constraint (circular reference avoided).
--   Application layer enforces consistency via try_mark_trigger_resolved().
--   Retrieval queries must join to verify fix_records points back (see adapter).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS debug_trigger_records (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo                    TEXT NOT NULL,
    branch                  TEXT NOT NULL,
    failure_fingerprint     TEXT NOT NULL,
    error_classification    TEXT NOT NULL DEFAULT 'unknown',
    -- observed_bad_sha: the SHA present when streak threshold was crossed.
    -- Phase 1 label: "observed", not "first bad" — avoids false confidence.
    observed_bad_sha        TEXT NOT NULL,
    streak_count_at_trigger INTEGER NOT NULL,
    resolved                BOOLEAN NOT NULL DEFAULT FALSE,
    -- fix_record_id: no FK (avoids circular with debug_fix_records).
    -- Must verify consistency via adapter join before returning fix records.
    fix_record_id           UUID,
    created_at_utc          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_debug_trigger_records_fingerprint
    ON debug_trigger_records (failure_fingerprint);

CREATE INDEX IF NOT EXISTS idx_debug_trigger_records_unresolved
    ON debug_trigger_records (resolved, repo, branch)
    WHERE resolved = FALSE;

CREATE INDEX IF NOT EXISTS idx_debug_trigger_records_created_at
    ON debug_trigger_records (created_at_utc DESC);

-- ---------------------------------------------------------------------------
-- debug_fix_records: created when CI recovers after a TriggerRecord exists
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS debug_fix_records (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_record_id       UUID NOT NULL REFERENCES debug_trigger_records(id),
    repo                    TEXT NOT NULL,
    sha                     TEXT NOT NULL,
    pr_number               INTEGER,
    -- regression_test_added: true if PR touches tests/ AND adds or modifies
    -- at least one test file. Phase 1 heuristic — not perfect, but honest.
    regression_test_added   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at_utc          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_debug_fix_records_trigger
    ON debug_fix_records (trigger_record_id);

CREATE INDEX IF NOT EXISTS idx_debug_fix_records_created_at
    ON debug_fix_records (created_at_utc DESC);
