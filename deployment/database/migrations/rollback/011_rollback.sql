-- Rollback: 011_add_evidence_tier_to_learned_patterns
-- Description: Remove evidence_tier column from learned_patterns
-- Author: omniintelligence
-- Date: 2026-02-11
-- Ticket: OMN-2133

-- Drop indexes first
DROP INDEX IF EXISTS idx_learned_patterns_status_evidence_tier;
DROP INDEX IF EXISTS idx_learned_patterns_evidence_tier;

-- Drop column (constraint is dropped automatically with the column)
ALTER TABLE learned_patterns DROP COLUMN IF EXISTS evidence_tier;
