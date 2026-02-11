-- Migration: 011_add_evidence_tier_to_learned_patterns
-- Description: Add evidence_tier column to learned_patterns for evidence-based promotion gating
-- Author: omniintelligence
-- Date: 2026-02-11
-- Ticket: OMN-2133
--
-- Dependencies: 005_create_learned_patterns.sql (adds column to existing table)
-- Note: evidence_tier is the denormalized source of truth for promotion gating.
--       The attribution binder is the SOLE writer of this column.
--       Monotonic: tiers only increase (UNMEASURED -> OBSERVED -> MEASURED -> VERIFIED).

-- ============================================================================
-- Add evidence_tier column
-- ============================================================================

-- Note: CHECK enforces lowercase values. All writers MUST use EnumEvidenceTier.value
-- (which produces lowercase). Case-mismatched writes (e.g., 'OBSERVED') will be
-- rejected by PostgreSQL with a check constraint violation.
ALTER TABLE learned_patterns
ADD COLUMN IF NOT EXISTS evidence_tier TEXT NOT NULL DEFAULT 'unmeasured'
    CONSTRAINT check_evidence_tier_valid CHECK (
        evidence_tier IN ('unmeasured', 'observed', 'measured', 'verified')
    );

-- ============================================================================
-- Index for evidence tier queries
-- ============================================================================

-- Index for promotion eligibility queries that filter by evidence tier
CREATE INDEX IF NOT EXISTS idx_learned_patterns_evidence_tier
    ON learned_patterns(evidence_tier);

-- Composite index for auto-promote queries: status + evidence_tier
CREATE INDEX IF NOT EXISTS idx_learned_patterns_status_evidence_tier
    ON learned_patterns(status, evidence_tier)
    WHERE status IN ('candidate', 'provisional') AND is_current = TRUE;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON COLUMN learned_patterns.evidence_tier IS 'Evidence quality tier (unmeasured|observed|measured|verified). Denormalized for fast reads. Attribution binder is sole writer. Monotonic: only increases.';
