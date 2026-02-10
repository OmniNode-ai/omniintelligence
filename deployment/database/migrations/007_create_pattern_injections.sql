-- Migration: 007_create_pattern_injections
-- Description: Create pattern_injections table for tracking injection events with A/B experiment support
-- Author: omniintelligence
-- Date: 2026-01-30
-- Ticket: OMN-1670
--
-- Dependencies: 005_create_learned_patterns.sql (pattern_ids references learned_patterns)
-- Note: Tracks every pattern injection with A/B cohort assignment for measuring effectiveness.
--       pattern_ids is a UUID array without FK constraint (PostgreSQL limitation);
--       referential integrity enforced at application level.

-- ============================================================================
-- Pattern Injections Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS pattern_injections (
    -- Primary key (single PK, no separate id column)
    injection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session and tracing
    session_id UUID NOT NULL,
    correlation_id UUID,

    -- Pattern tracking (no FK - PostgreSQL doesn't support array FKs)
    pattern_ids UUID[] NOT NULL DEFAULT '{}',

    -- Timing
    injected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Injection context (subset of hook events where injection is valid)
    injection_context VARCHAR(30) NOT NULL
        CHECK (injection_context IN ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'SubagentStart')),

    -- A/B experiment tracking
    cohort VARCHAR(20) NOT NULL DEFAULT 'treatment'
        CHECK (cohort IN ('control', 'treatment')),
    assignment_seed BIGINT NOT NULL,

    -- Compiled content (what was actually injected)
    compiled_content TEXT,
    compiled_token_count INT,

    -- Outcome tracking
    outcome_recorded BOOLEAN NOT NULL DEFAULT FALSE,
    outcome_success BOOLEAN,
    outcome_recorded_at TIMESTAMPTZ,
    outcome_failure_reason TEXT,

    -- Contribution heuristic (for pattern attribution)
    contribution_heuristic JSONB,
    heuristic_method VARCHAR(50),
    heuristic_confidence FLOAT,

    -- Auditing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Primary lookup: find injections for a session
CREATE INDEX IF NOT EXISTS idx_pattern_injections_session_id
    ON pattern_injections(session_id);

-- Partial index: efficiently find pending outcomes
CREATE INDEX IF NOT EXISTS idx_pattern_injections_pending_outcome
    ON pattern_injections(session_id, outcome_recorded)
    WHERE outcome_recorded = FALSE;

-- A/B cohort analysis
CREATE INDEX IF NOT EXISTS idx_pattern_injections_cohort
    ON pattern_injections(cohort);

-- Time-based queries (analytics, cleanup)
CREATE INDEX IF NOT EXISTS idx_pattern_injections_injected_at
    ON pattern_injections(injected_at);

-- GIN index for pattern containment queries ("which injections included pattern X?")
CREATE INDEX IF NOT EXISTS idx_pattern_injections_pattern_ids
    ON pattern_injections USING GIN (pattern_ids);

-- Correlation tracing
CREATE INDEX IF NOT EXISTS idx_pattern_injections_correlation_id
    ON pattern_injections(correlation_id)
    WHERE correlation_id IS NOT NULL;

-- ============================================================================
-- Trigger for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_pattern_injections_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_pattern_injections_updated_at
    BEFORE UPDATE ON pattern_injections
    FOR EACH ROW
    EXECUTE FUNCTION update_pattern_injections_updated_at();

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE pattern_injections IS 'Tracks every pattern injection event with A/B experiment support for measuring effectiveness';

COMMENT ON COLUMN pattern_injections.injection_id IS 'Primary key - unique identifier for this injection event';
COMMENT ON COLUMN pattern_injections.session_id IS 'Claude Code session that received the injection';
COMMENT ON COLUMN pattern_injections.correlation_id IS 'Distributed tracing ID for linking across Kafka, ledger, and DB';
COMMENT ON COLUMN pattern_injections.pattern_ids IS 'Array of learned_patterns.id values injected (app-level validation, no FK)';
COMMENT ON COLUMN pattern_injections.injected_at IS 'When the injection occurred';
COMMENT ON COLUMN pattern_injections.injection_context IS 'Hook event that triggered injection: SessionStart, UserPromptSubmit, PreToolUse, SubagentStart';
COMMENT ON COLUMN pattern_injections.cohort IS 'A/B experiment cohort: control (no patterns) or treatment (validated patterns)';
COMMENT ON COLUMN pattern_injections.assignment_seed IS 'Seed used for deterministic cohort assignment (hash-based)';
COMMENT ON COLUMN pattern_injections.compiled_content IS 'Actual text content that was injected';
COMMENT ON COLUMN pattern_injections.compiled_token_count IS 'Token count of compiled_content for limit tracking';
COMMENT ON COLUMN pattern_injections.outcome_recorded IS 'Whether session outcome has been recorded for this injection';
COMMENT ON COLUMN pattern_injections.outcome_success IS 'Session outcome: TRUE=success, FALSE=failure, NULL=not yet recorded';
COMMENT ON COLUMN pattern_injections.outcome_recorded_at IS 'When the outcome was recorded';
COMMENT ON COLUMN pattern_injections.outcome_failure_reason IS 'Reason for failure if outcome_success=FALSE';
COMMENT ON COLUMN pattern_injections.contribution_heuristic IS 'JSONB mapping pattern_id to contribution score for attribution';
COMMENT ON COLUMN pattern_injections.heuristic_method IS 'Method used: equal_split, recency_weighted, first_match';
COMMENT ON COLUMN pattern_injections.heuristic_confidence IS 'Confidence in the heuristic (0.0-1.0)';
COMMENT ON COLUMN pattern_injections.created_at IS 'Row creation timestamp';
COMMENT ON COLUMN pattern_injections.updated_at IS 'Row last update timestamp';

COMMENT ON FUNCTION update_pattern_injections_updated_at IS 'Trigger function to auto-update updated_at on row modification';
