-- ============================================================================
-- Rollback: 004 - Pattern Quality Metrics
-- ============================================================================
-- Description: Rollback migration 004 - drops pattern_quality_metrics table
-- Date: 2025-10-28
-- WARNING: This will delete all quality metrics data!
-- ============================================================================

-- Drop helper functions
DROP FUNCTION IF EXISTS get_average_quality_score();
DROP FUNCTION IF EXISTS get_quality_trend(UUID, INTEGER);
DROP FUNCTION IF EXISTS get_latest_quality_metric(UUID);

-- Drop indexes (automatically dropped with table, but explicit for clarity)
DROP INDEX IF EXISTS idx_pqm_metadata;
DROP INDEX IF EXISTS idx_pqm_quality_score;
DROP INDEX IF EXISTS idx_pqm_pattern_measurement;
DROP INDEX IF EXISTS idx_pqm_measurement_timestamp;
DROP INDEX IF EXISTS idx_pqm_pattern_id;

-- Drop table (CASCADE will drop dependent objects)
DROP TABLE IF EXISTS pattern_quality_metrics CASCADE;

-- Note: Conditional indexes on pattern_feedback and patterns tables
-- are not dropped as they may be used by other features

-- ============================================================================
-- Rollback Complete
-- ============================================================================
-- Objects dropped: pattern_quality_metrics table, 5 indexes, 3 functions
-- Data loss: All quality metrics data removed
-- ============================================================================
