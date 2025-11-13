-- ============================================================================
-- Pattern Relationships Enhancements
-- ============================================================================
-- Purpose: Add triggers and constraints to prevent invalid relationships
-- Created: 2025-10-28
-- Track: Pattern Relationship Detection and Graph Engine
-- ============================================================================

-- Add CHECK constraint to prevent self-relationships
-- NOTE: This constraint may already exist from Phase 1 migration
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_no_self_relationship'
        AND conrelid = 'pattern_relationships'::regclass
    ) THEN
        ALTER TABLE pattern_relationships
        ADD CONSTRAINT chk_no_self_relationship
        CHECK (source_pattern_id != target_pattern_id);
    END IF;
END $$;

-- Create function to update relationship strength based on usage
CREATE OR REPLACE FUNCTION update_relationship_strength()
RETURNS TRIGGER AS $$
BEGIN
    -- Automatically update relationship strength based on context
    -- This is a placeholder for future ML-based strength calculation

    -- Ensure strength is in valid range
    IF NEW.strength < 0.0 THEN
        NEW.strength := 0.0;
    ELSIF NEW.strength > 1.0 THEN
        NEW.strength := 1.0;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for relationship strength validation
DROP TRIGGER IF EXISTS trg_validate_relationship_strength ON pattern_relationships;
CREATE TRIGGER trg_validate_relationship_strength
BEFORE INSERT OR UPDATE ON pattern_relationships
FOR EACH ROW
EXECUTE FUNCTION update_relationship_strength();

-- Create index for bidirectional relationship queries
CREATE INDEX IF NOT EXISTS idx_relationship_bidirectional
ON pattern_relationships(target_pattern_id, source_pattern_id);

-- Create index for relationship type + strength (for ranking similar patterns)
CREATE INDEX IF NOT EXISTS idx_relationship_type_strength
ON pattern_relationships(relationship_type, strength DESC);

-- Create partial index for high-confidence relationships
CREATE INDEX IF NOT EXISTS idx_high_confidence_relationships
ON pattern_relationships(source_pattern_id, relationship_type, strength)
WHERE strength >= 0.8;

-- Create GIN index on context JSONB for fast metadata queries
CREATE INDEX IF NOT EXISTS idx_relationship_context_gin
ON pattern_relationships USING gin(context);

-- Add comments
COMMENT ON CONSTRAINT chk_no_self_relationship ON pattern_relationships
IS 'Prevents a pattern from having a relationship with itself';

COMMENT ON FUNCTION update_relationship_strength()
IS 'Validates and normalizes relationship strength to [0.0, 1.0] range';

COMMENT ON INDEX idx_relationship_bidirectional
IS 'Optimizes bidirectional relationship queries (both source->target and target->source)';

COMMENT ON INDEX idx_high_confidence_relationships
IS 'Optimizes queries for high-confidence relationships (strength >= 0.8)';

-- ============================================================================
-- Validation
-- ============================================================================

DO $$
BEGIN
    -- Verify constraint exists
    ASSERT (SELECT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_no_self_relationship'
        AND conrelid = 'pattern_relationships'::regclass
    )), 'Self-relationship constraint not created';

    -- Verify trigger exists
    ASSERT (SELECT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_validate_relationship_strength'
    )), 'Relationship strength validation trigger not created';

    -- Verify indexes exist
    ASSERT (SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_relationship_bidirectional'
    )), 'Bidirectional index not created';

    ASSERT (SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_high_confidence_relationships'
    )), 'High confidence index not created';

    RAISE NOTICE 'Pattern relationships enhancements applied successfully';
END $$;

-- ============================================================================
-- Sample Queries for Testing
-- ============================================================================

-- Find all high-confidence relationships for a pattern
-- SELECT * FROM pattern_relationships
-- WHERE source_pattern_id = '<pattern_id>'
-- AND strength >= 0.8
-- ORDER BY strength DESC;

-- Find bidirectional relationships (mutual dependencies)
-- SELECT
--     r1.source_pattern_id AS pattern_a,
--     r1.target_pattern_id AS pattern_b,
--     r1.relationship_type AS relationship_ab,
--     r2.relationship_type AS relationship_ba,
--     r1.strength AS strength_ab,
--     r2.strength AS strength_ba
-- FROM pattern_relationships r1
-- JOIN pattern_relationships r2
--     ON r1.source_pattern_id = r2.target_pattern_id
--     AND r1.target_pattern_id = r2.source_pattern_id
-- WHERE r1.source_pattern_id < r1.target_pattern_id;  -- Avoid duplicates

-- Find patterns with specific metadata in context
-- SELECT * FROM pattern_relationships
-- WHERE context @> '{"detection_method": "import_analysis"}'::jsonb;
