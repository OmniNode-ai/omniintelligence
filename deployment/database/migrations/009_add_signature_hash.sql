-- Migration: 009_add_signature_hash
-- Description: Add signature_hash column for stable pattern identity (SHA256)
-- Author: omniintelligence
-- Date: 2026-02-02
-- Ticket: OMN-1780
--
-- Dependencies: 005_create_learned_patterns.sql
-- Note: signature_hash provides a stable identity hash (SHA256) for lineage tracking,
--       while pattern_signature retains the raw signature text. This separation allows
--       the signature format to evolve without breaking lineage identity.

-- ============================================================================
-- Add signature_hash Column
-- ============================================================================

-- Add column with temporary default for backfill (will be set to NOT NULL after backfill)
ALTER TABLE learned_patterns
    ADD COLUMN IF NOT EXISTS signature_hash TEXT;

-- ============================================================================
-- Backfill Existing Data
-- ============================================================================

-- Backfill signature_hash from pattern_signature for existing rows
-- Note: For existing data, we use pattern_signature as the hash value.
--       New patterns will compute a proper SHA256 hash in the application layer.
UPDATE learned_patterns
SET signature_hash = pattern_signature
WHERE signature_hash IS NULL;

-- ============================================================================
-- Add NOT NULL Constraint
-- ============================================================================

-- Now that all rows have values, add the NOT NULL constraint
ALTER TABLE learned_patterns
    ALTER COLUMN signature_hash SET NOT NULL;

-- ============================================================================
-- Constraints
-- ============================================================================

-- Unique constraint for signature_hash + domain + version (mirrors pattern_signature constraint)
-- Note: This constraint ensures no duplicate patterns with the same hash within a domain version.
ALTER TABLE learned_patterns
    ADD CONSTRAINT unique_signature_hash_domain_version
    UNIQUE (domain_id, signature_hash, version);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Partial unique index for current version lookup by signature_hash
-- Note: Ensures only one "current" pattern per (signature_hash, domain_id) combination.
CREATE UNIQUE INDEX IF NOT EXISTS idx_current_pattern_hash
    ON learned_patterns (signature_hash, domain_id)
    WHERE is_current = TRUE;

-- Index for querying by domain and signature_hash
-- Note: Supports efficient lookup of patterns by domain and hash for lineage queries.
CREATE INDEX IF NOT EXISTS idx_learned_patterns_domain_hash
    ON learned_patterns(domain_id, signature_hash);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON COLUMN learned_patterns.signature_hash IS 'SHA256 hash of pattern signature for stable lineage identity. Application layer computes hash; existing data backfilled from pattern_signature.';

COMMENT ON CONSTRAINT unique_signature_hash_domain_version ON learned_patterns IS 'Ensures uniqueness of (domain_id, signature_hash, version) for lineage tracking';

COMMENT ON INDEX idx_current_pattern_hash IS 'Enables efficient lookup of current pattern version by signature_hash and domain';
COMMENT ON INDEX idx_learned_patterns_domain_hash IS 'Supports efficient lineage queries by domain and signature hash';
