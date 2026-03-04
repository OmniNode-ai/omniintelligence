-- Migration: 022_add_project_scope_to_learned_patterns
-- Description: Add project_scope column to learned_patterns for project-specific pattern scoping
-- Author: omniintelligence
-- Date: 2026-03-04
-- Ticket: OMN-1607
--
-- Dependencies: 005_create_learned_patterns.sql
-- Note: project_scope = NULL means pattern applies globally (backward compatible).
--       Non-null project_scope limits pattern applicability to that project.

-- ============================================================================
-- Add project_scope column
-- ============================================================================

ALTER TABLE learned_patterns
ADD COLUMN IF NOT EXISTS project_scope VARCHAR(255) DEFAULT NULL;

-- ============================================================================
-- Index for project_scope filtering
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_learned_patterns_project_scope
    ON learned_patterns (project_scope);

-- Composite index for project-scoped domain queries
CREATE INDEX IF NOT EXISTS idx_learned_patterns_domain_project_scope
    ON learned_patterns (domain_id, project_scope);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON COLUMN learned_patterns.project_scope IS 'Optional project scope (e.g., "omniclaude", "omniarchon"). NULL means pattern applies globally.';
