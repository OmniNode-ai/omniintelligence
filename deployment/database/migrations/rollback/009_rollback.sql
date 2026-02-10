-- Rollback: 009_add_signature_hash
-- Description: Remove signature_hash column and associated constraints/indexes from learned_patterns
-- Author: omniintelligence
-- Date: 2026-02-02
-- Ticket: OMN-1780

-- Drop indexes first
DROP INDEX IF EXISTS idx_current_pattern_hash;
DROP INDEX IF EXISTS idx_learned_patterns_domain_hash;

-- Drop unique constraint
ALTER TABLE learned_patterns
    DROP CONSTRAINT IF EXISTS unique_signature_hash_domain_version;

-- Drop column (NOT NULL constraint is removed automatically)
ALTER TABLE learned_patterns
    DROP COLUMN IF EXISTS signature_hash;
