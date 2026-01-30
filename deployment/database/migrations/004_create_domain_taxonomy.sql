-- Migration: 004_create_domain_taxonomy
-- Description: Create domain_taxonomy table for versioned domain classification
-- Author: omniintelligence
-- Date: 2026-01-29
-- Ticket: OMN-1666
--
-- Dependencies: 000_extensions.sql
-- Note: Provides stable, versioned domain classification for patterns.
--       Domains must come from this versioned enum, not derived dynamically.

-- ============================================================================
-- Domain Taxonomy Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS domain_taxonomy (
    -- Primary key
    id SERIAL PRIMARY KEY,

    -- Domain identification
    domain_id VARCHAR(50) NOT NULL UNIQUE,
    domain_version VARCHAR(20) NOT NULL,

    -- Description
    description TEXT,

    -- Auditing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Index for querying by domain version
CREATE INDEX IF NOT EXISTS idx_domain_taxonomy_version
    ON domain_taxonomy(domain_version);

-- Note: No explicit index needed for domain_id - the UNIQUE constraint creates one implicitly

-- ============================================================================
-- Seed Data: v1.0 Domain Taxonomy
-- ============================================================================

INSERT INTO domain_taxonomy (domain_id, domain_version, description) VALUES
    ('code_generation', '1.0', 'Creating new code'),
    ('code_review', '1.0', 'Reviewing existing code'),
    ('debugging', '1.0', 'Finding and fixing bugs'),
    ('testing', '1.0', 'Writing or running tests'),
    ('documentation', '1.0', 'Writing docs or comments'),
    ('refactoring', '1.0', 'Restructuring existing code'),
    ('architecture', '1.0', 'System design decisions'),
    ('devops', '1.0', 'CI/CD, deployment, infra'),
    ('data_analysis', '1.0', 'Data processing and analysis'),
    ('general', '1.0', 'General purpose tasks')
ON CONFLICT (domain_id) DO NOTHING;

-- ============================================================================
-- Trigger for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_domain_taxonomy_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_domain_taxonomy_updated_at
    BEFORE UPDATE ON domain_taxonomy
    FOR EACH ROW
    EXECUTE FUNCTION update_domain_taxonomy_updated_at();

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE domain_taxonomy IS 'Versioned domain classification for patterns - quality gate for pattern promotion';
COMMENT ON COLUMN domain_taxonomy.domain_id IS 'Unique domain identifier (e.g., code_generation, debugging)';
COMMENT ON COLUMN domain_taxonomy.domain_version IS 'Taxonomy version (e.g., 1.0) for schema evolution';
COMMENT ON COLUMN domain_taxonomy.description IS 'Human-readable description of the domain';
COMMENT ON COLUMN domain_taxonomy.created_at IS 'When this domain was added to the taxonomy';
COMMENT ON COLUMN domain_taxonomy.updated_at IS 'When this domain was last modified';
