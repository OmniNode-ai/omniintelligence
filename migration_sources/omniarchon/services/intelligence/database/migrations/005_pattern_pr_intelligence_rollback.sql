-- Migration 005 Rollback: Pattern PR Intelligence
-- Date: 2025-10-28
-- Purpose: Rollback pattern PR intelligence tables and views

-- Drop view first (depends on table)
DROP VIEW IF EXISTS pattern_pr_statistics;

-- Drop table (cascades to dependent objects)
DROP TABLE IF EXISTS pattern_pr_intelligence CASCADE;

-- Verification
DO $$
BEGIN
    RAISE NOTICE 'Migration 005 rollback completed successfully';
    RAISE NOTICE 'Dropped view: pattern_pr_statistics';
    RAISE NOTICE 'Dropped table: pattern_pr_intelligence';
END $$;
