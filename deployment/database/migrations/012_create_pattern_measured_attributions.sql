-- Migration: 012_create_pattern_measured_attributions
-- Description: Create pattern_measured_attributions table for attribution audit trail
-- Author: omniintelligence
-- Date: 2026-02-11
-- Ticket: OMN-2133
--
-- Dependencies: 005_create_learned_patterns.sql (pattern_id references learned_patterns)
-- Note: This table provides the audit trail for evidence-based attribution.
--       Each record captures a single attribution binding event: linking a session
--       outcome to a pipeline measurement run and computing the evidence tier.
--       The evidence_tier on learned_patterns is the denormalized projection;
--       this table is the source of truth for WHY that tier was assigned.

-- ============================================================================
-- Pattern Measured Attributions Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS pattern_measured_attributions (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pattern reference
    -- ON DELETE RESTRICT: preserve attribution history even if pattern is removed
    pattern_id UUID NOT NULL REFERENCES learned_patterns(id) ON DELETE RESTRICT,

    -- Session that triggered this attribution
    session_id UUID NOT NULL,

    -- Pipeline run (nullable: run_id=NULL means OBSERVED-only attribution)
    run_id UUID,

    -- Evidence tier computed for this attribution event
    evidence_tier TEXT NOT NULL
        CONSTRAINT check_attribution_evidence_tier_valid CHECK (
            evidence_tier IN ('unmeasured', 'observed', 'measured', 'verified')
        ),

    -- Full measured attribution contract as JSON (nullable when run_id is NULL)
    measured_attribution_json JSONB,

    -- Correlation tracing
    correlation_id UUID,

    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Primary lookup: find attributions for a pattern, most recent first
CREATE INDEX IF NOT EXISTS idx_pattern_attributions_pattern_created
    ON pattern_measured_attributions(pattern_id, created_at DESC);

-- Session lookup: find all attributions from a session
CREATE INDEX IF NOT EXISTS idx_pattern_attributions_session
    ON pattern_measured_attributions(session_id);

-- Run lookup: find attributions linked to a pipeline run (partial: only non-NULL run_ids)
CREATE INDEX IF NOT EXISTS idx_pattern_attributions_run_id
    ON pattern_measured_attributions(run_id)
    WHERE run_id IS NOT NULL;

-- Correlation tracing
CREATE INDEX IF NOT EXISTS idx_pattern_attributions_correlation
    ON pattern_measured_attributions(correlation_id)
    WHERE correlation_id IS NOT NULL;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE pattern_measured_attributions IS 'Audit trail for evidence-based attribution binding. Links session outcomes to pipeline runs and records evidence tier computations.';

COMMENT ON COLUMN pattern_measured_attributions.id IS 'Unique attribution record identifier';
COMMENT ON COLUMN pattern_measured_attributions.pattern_id IS 'Reference to the attributed pattern. Uses ON DELETE RESTRICT to preserve audit trail.';
COMMENT ON COLUMN pattern_measured_attributions.session_id IS 'Claude Code session that triggered this attribution';
COMMENT ON COLUMN pattern_measured_attributions.run_id IS 'Pipeline run ID for measured attribution. NULL means OBSERVED-only (no pipeline run data).';
COMMENT ON COLUMN pattern_measured_attributions.evidence_tier IS 'Evidence tier computed for this attribution event (unmeasured|observed|measured|verified)';
COMMENT ON COLUMN pattern_measured_attributions.measured_attribution_json IS 'Full ContractMeasuredAttribution as JSON. NULL when run_id is NULL (OBSERVED-only path).';
COMMENT ON COLUMN pattern_measured_attributions.correlation_id IS 'Distributed tracing ID for linking across services';
COMMENT ON COLUMN pattern_measured_attributions.created_at IS 'When this attribution was recorded';
