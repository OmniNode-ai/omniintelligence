-- SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
-- SPDX-License-Identifier: MIT
--
-- Migration: 001_create_policy_state.sql
-- Ticket: OMN-2557
-- Description: Creates policy_state and policy_state_audit tables for
--              PolicyStateReducer node. Supports all four policy types
--              (tool_reliability, pattern_effectiveness, model_routing_confidence,
--              retry_threshold) with lifecycle state tracking and idempotency.

-- ---------------------------------------------------------------------------
-- policy_state: current state for each policy entity
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS policy_state (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id           TEXT NOT NULL,
    policy_type         TEXT NOT NULL CHECK (
                            policy_type IN (
                                'tool_reliability',
                                'pattern_effectiveness',
                                'model_routing_confidence',
                                'retry_threshold'
                            )
                        ),
    lifecycle_state     TEXT NOT NULL CHECK (
                            lifecycle_state IN (
                                'candidate',
                                'validated',
                                'promoted',
                                'deprecated'
                            )
                        ),
    state_json          JSONB NOT NULL,
    run_count           INTEGER NOT NULL DEFAULT 0,
    failure_count       INTEGER NOT NULL DEFAULT 0,
    blacklisted         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at_utc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at_utc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (policy_id, policy_type)
);

-- Index on policy_type for batch queries by type
CREATE INDEX IF NOT EXISTS idx_policy_state_type
    ON policy_state (policy_type);

-- Index on lifecycle_state for promotion/deprecation queries
CREATE INDEX IF NOT EXISTS idx_policy_state_lifecycle
    ON policy_state (lifecycle_state);

-- Index on blacklisted for fast alert query
CREATE INDEX IF NOT EXISTS idx_policy_state_blacklisted
    ON policy_state (blacklisted)
    WHERE blacklisted = TRUE;

-- ---------------------------------------------------------------------------
-- policy_state_audit: append-only audit log of all state transitions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS policy_state_audit (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id               TEXT NOT NULL,
    policy_type             TEXT NOT NULL,
    event_id                TEXT NOT NULL,
    idempotency_key         TEXT NOT NULL UNIQUE,
    old_lifecycle_state     TEXT NOT NULL,
    new_lifecycle_state     TEXT NOT NULL,
    transition_occurred     BOOLEAN NOT NULL DEFAULT FALSE,
    old_state_json          JSONB NOT NULL,
    new_state_json          JSONB NOT NULL,
    reward_delta            DOUBLE PRECISION NOT NULL,
    run_id                  TEXT NOT NULL,
    objective_id            TEXT NOT NULL,
    blacklisted             BOOLEAN NOT NULL DEFAULT FALSE,
    alert_emitted           BOOLEAN NOT NULL DEFAULT FALSE,
    occurred_at_utc         TIMESTAMPTZ NOT NULL
);

-- Index on policy_id for history queries
CREATE INDEX IF NOT EXISTS idx_policy_state_audit_policy_id
    ON policy_state_audit (policy_id);

-- Index on idempotency_key for dedup lookups (UNIQUE already creates one,
-- but explicit here for clarity)
CREATE INDEX IF NOT EXISTS idx_policy_state_audit_idempotency
    ON policy_state_audit (idempotency_key);

-- Index on occurred_at_utc for time-range queries
CREATE INDEX IF NOT EXISTS idx_policy_state_audit_occurred_at
    ON policy_state_audit (occurred_at_utc DESC);

-- ---------------------------------------------------------------------------
-- processed_events: idempotency tracking for Kafka event dedup
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS policy_state_processed_events (
    idempotency_key     TEXT PRIMARY KEY,
    processed_at_utc    TIMESTAMPTZ NOT NULL DEFAULT now()
);
