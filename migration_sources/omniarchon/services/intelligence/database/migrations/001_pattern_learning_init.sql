-- ============================================================================
-- Migration: 001 - Pattern Learning Engine Initial Schema
-- ============================================================================
-- Description: Creates initial schema for pattern learning and storage
-- Author: AI-Generated (Codestral + Human Refinement)
-- Date: 2025-10-02
-- Track: Track 3-1.2 - PostgreSQL Storage Layer
-- Dependencies: PostgreSQL 15+, uuid-ossp extension, pg_trgm extension
-- ============================================================================

-- Migration ID for tracking
INSERT INTO schema_versions (version, description, applied_at)
VALUES ('1.0.0_pattern_learning', 'Pattern Learning Engine initial schema', NOW())
ON CONFLICT (version) DO NOTHING;

-- Execute main schema
\i /Volumes/PRO-G40/Code/Archon/services/intelligence/database/schema/pattern_learning_schema.sql

-- ============================================================================
-- Post-Migration Verification
-- ============================================================================

-- Verify tables exist
DO $$
BEGIN
    ASSERT (SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pattern_templates')),
        'Table pattern_templates not created';
    ASSERT (SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pattern_usage_events')),
        'Table pattern_usage_events not created';
    ASSERT (SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pattern_relationships')),
        'Table pattern_relationships not created';
    ASSERT (SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pattern_analytics')),
        'Table pattern_analytics not created';

    RAISE NOTICE 'Pattern Learning Engine schema migration completed successfully';
END $$;
