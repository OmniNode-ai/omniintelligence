-- ============================================================================
-- Migration: 003 - Pattern Lineage Tables
-- ============================================================================
-- Description: Creates pattern lineage tracking tables for pattern traceability
-- Date: 2025-10-18
-- Track: Track 3 Phase 4 - Pattern Traceability
-- Dependencies: PostgreSQL 15+, uuid-ossp extension
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- 1. Pattern Lineage Nodes
-- ============================================================================
-- Stores pattern instances in the lineage graph
-- Each row represents a pattern at a specific point in time

CREATE TABLE IF NOT EXISTS pattern_lineage_nodes (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id VARCHAR(255) NOT NULL,

    -- Pattern metadata
    pattern_name VARCHAR(255) NOT NULL,
    pattern_type VARCHAR(100) NOT NULL, -- 'code', 'config', 'template', 'workflow'
    pattern_version VARCHAR(50) NOT NULL DEFAULT '1.0.0',

    -- Lineage tracking
    lineage_id UUID NOT NULL, -- Groups related pattern versions
    generation INTEGER NOT NULL DEFAULT 1, -- Generation in lineage (1 = original)

    -- Source and context
    source_system VARCHAR(100), -- 'ai_assistant', 'manual', 'automated_refactor'
    source_user VARCHAR(100),
    source_event_id UUID, -- References pattern_lineage_events

    -- Pattern content snapshot
    pattern_data JSONB NOT NULL, -- Full pattern data at this point in time
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Tracking fields
    correlation_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Additional fields required by code (not in original schema)
    event_type VARCHAR(100),
    tool_name VARCHAR(255),
    file_path TEXT,
    language VARCHAR(50),

    -- Constraints
    CONSTRAINT unique_pattern_lineage_version UNIQUE (pattern_id, pattern_version)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_pattern_id ON pattern_lineage_nodes(pattern_id);
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_lineage_id ON pattern_lineage_nodes(lineage_id);
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_generation ON pattern_lineage_nodes(generation);
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_created_at ON pattern_lineage_nodes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_correlation_id ON pattern_lineage_nodes(correlation_id);
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_source_event ON pattern_lineage_nodes(source_event_id);
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_pattern_version ON pattern_lineage_nodes(pattern_id, pattern_version);

-- GIN index for JSONB pattern_data queries
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_pattern_data ON pattern_lineage_nodes USING GIN (pattern_data);
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_metadata ON pattern_lineage_nodes USING GIN (metadata);


-- ============================================================================
-- 2. Pattern Lineage Edges
-- ============================================================================
-- Stores relationships between pattern nodes
-- Represents the directed acyclic graph (DAG) of pattern evolution

CREATE TABLE IF NOT EXISTS pattern_lineage_edges (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationship endpoints
    source_node_id UUID NOT NULL REFERENCES pattern_lineage_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES pattern_lineage_nodes(id) ON DELETE CASCADE,

    -- Relationship type
    edge_type VARCHAR(100) NOT NULL,
    -- Edge types:
    --   'derived_from'    - Target derived from source
    --   'modified_from'   - Target is modification of source
    --   'merged_from'     - Target merged from source
    --   'replaced_by'     - Source replaced by target
    --   'inspired_by'     - Target inspired by source
    --   'deprecated_by'   - Source deprecated by target

    -- Relationship metadata
    edge_weight FLOAT DEFAULT 1.0, -- Strength of relationship (0.0-1.0)
    transformation_type VARCHAR(100), -- 'refactor', 'enhancement', 'bugfix', 'merge'
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Tracking fields
    correlation_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),

    -- Constraints
    CONSTRAINT valid_edge_weight CHECK (edge_weight >= 0.0 AND edge_weight <= 1.0),
    CONSTRAINT no_self_loops CHECK (source_node_id != target_node_id),
    CONSTRAINT unique_edge UNIQUE (source_node_id, target_node_id, edge_type)
);

-- Indexes for graph traversal
CREATE INDEX IF NOT EXISTS idx_lineage_edges_source ON pattern_lineage_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_lineage_edges_target ON pattern_lineage_edges(target_node_id);
CREATE INDEX IF NOT EXISTS idx_lineage_edges_type ON pattern_lineage_edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_lineage_edges_created_at ON pattern_lineage_edges(created_at DESC);

-- Composite index for bidirectional traversal
CREATE INDEX IF NOT EXISTS idx_lineage_edges_bidirectional ON pattern_lineage_edges(source_node_id, target_node_id);

-- Composite index for optimized recursive CTE ancestry queries
CREATE INDEX IF NOT EXISTS idx_lineage_edges_target_source_type ON pattern_lineage_edges(target_node_id, source_node_id, edge_type);


-- ============================================================================
-- 3. Pattern Lineage Events
-- ============================================================================
-- Event log for all lineage changes
-- Provides audit trail and temporal tracking

CREATE TABLE IF NOT EXISTS pattern_lineage_events (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event classification
    event_type VARCHAR(100) NOT NULL,
    -- Event types:
    --   'pattern_created'      - New pattern registered
    --   'pattern_modified'     - Existing pattern updated
    --   'pattern_merged'       - Multiple patterns combined
    --   'pattern_applied'      - Pattern used in execution
    --   'pattern_deprecated'   - Pattern marked obsolete
    --   'pattern_forked'       - Pattern branched into variant
    --   'pattern_validated'    - Pattern passed validation

    event_subtype VARCHAR(100), -- More specific categorization

    -- Event subjects
    pattern_id VARCHAR(255) NOT NULL,
    pattern_node_id UUID REFERENCES pattern_lineage_nodes(id),

    -- Parent relationships (for derived/merged patterns)
    parent_pattern_ids TEXT[], -- Array of parent pattern IDs
    parent_node_ids UUID[], -- Array of parent node UUIDs

    -- Event payload
    event_data JSONB NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Event context
    reason TEXT, -- Human-readable reason for event
    triggered_by VARCHAR(100), -- 'user', 'system', 'ai_assistant'

    -- Tracking fields
    correlation_id UUID NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Performance tracking
    duration_ms INTEGER, -- Event processing duration
    success BOOLEAN DEFAULT true
);

-- Indexes for event queries
CREATE INDEX IF NOT EXISTS idx_lineage_events_type ON pattern_lineage_events(event_type);
CREATE INDEX IF NOT EXISTS idx_lineage_events_pattern_id ON pattern_lineage_events(pattern_id);
CREATE INDEX IF NOT EXISTS idx_lineage_events_timestamp ON pattern_lineage_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_lineage_events_correlation_id ON pattern_lineage_events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_lineage_events_pattern_node ON pattern_lineage_events(pattern_node_id);

-- GIN indexes for array and JSONB queries
CREATE INDEX IF NOT EXISTS idx_lineage_events_parent_patterns ON pattern_lineage_events USING GIN (parent_pattern_ids);
CREATE INDEX IF NOT EXISTS idx_lineage_events_parent_nodes ON pattern_lineage_events USING GIN (parent_node_ids);
CREATE INDEX IF NOT EXISTS idx_lineage_events_event_data ON pattern_lineage_events USING GIN (event_data);


-- ============================================================================
-- 4. Pattern Ancestry Cache
-- ============================================================================
-- Materialized ancestry paths for fast queries
-- Denormalized for performance, rebuilt periodically

CREATE TABLE IF NOT EXISTS pattern_ancestry_cache (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pattern identification
    pattern_id VARCHAR(255) NOT NULL,
    pattern_node_id UUID NOT NULL REFERENCES pattern_lineage_nodes(id) ON DELETE CASCADE,

    -- Ancestry information
    ancestor_ids UUID[] NOT NULL, -- Ordered array of ancestor node IDs
    ancestor_pattern_ids TEXT[] NOT NULL, -- Ordered array of ancestor pattern IDs
    ancestry_depth INTEGER NOT NULL, -- Number of generations to root
    lineage_path VARCHAR(1000), -- Path representation

    -- Metadata
    total_ancestors INTEGER NOT NULL,
    direct_descendants_count INTEGER DEFAULT 0,
    total_descendants_count INTEGER DEFAULT 0,

    -- Cache management
    cache_version INTEGER NOT NULL DEFAULT 1,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_stale BOOLEAN DEFAULT false,

    -- Constraints
    CONSTRAINT unique_cached_pattern UNIQUE (pattern_node_id)
);

-- Indexes for ancestry queries
CREATE INDEX IF NOT EXISTS idx_ancestry_cache_pattern_id ON pattern_ancestry_cache(pattern_id);
CREATE INDEX IF NOT EXISTS idx_ancestry_cache_depth ON pattern_ancestry_cache(ancestry_depth);
CREATE INDEX IF NOT EXISTS idx_ancestry_cache_updated ON pattern_ancestry_cache(last_updated DESC);
CREATE INDEX IF NOT EXISTS idx_ancestry_cache_stale ON pattern_ancestry_cache(is_stale) WHERE is_stale = true;

-- GIN indexes for array queries
CREATE INDEX IF NOT EXISTS idx_ancestry_cache_ancestors ON pattern_ancestry_cache USING GIN (ancestor_ids);
CREATE INDEX IF NOT EXISTS idx_ancestry_cache_ancestor_patterns ON pattern_ancestry_cache USING GIN (ancestor_pattern_ids);


-- ============================================================================
-- Utility Functions
-- ============================================================================

-- Function to invalidate ancestry cache for a pattern and its descendants
CREATE OR REPLACE FUNCTION invalidate_ancestry_cache(p_pattern_node_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    rows_updated INTEGER;
BEGIN
    -- Mark pattern and all descendants as stale
    UPDATE pattern_ancestry_cache
    SET is_stale = true,
        last_updated = NOW()
    WHERE pattern_node_id = p_pattern_node_id
       OR p_pattern_node_id = ANY(ancestor_ids);

    GET DIAGNOSTICS rows_updated = ROW_COUNT;
    RETURN rows_updated;
END;
$$;


-- Function to get full ancestry chain for a pattern (OPTIMIZED)
CREATE OR REPLACE FUNCTION get_pattern_ancestry(p_pattern_node_id UUID)
RETURNS TABLE (
    ancestor_id UUID,
    ancestor_pattern_id VARCHAR,
    generation INTEGER,
    edge_type VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_timeout INTERVAL := INTERVAL '100 milliseconds';  -- Query timeout
    v_max_depth INTEGER := 20;  -- Reduced from 100 to prevent deep traversals
    v_start_time TIMESTAMP := clock_timestamp();
BEGIN
    -- Set statement timeout for this specific query
    SET LOCAL statement_timeout = v_timeout;

    RETURN QUERY
    WITH RECURSIVE ancestry AS (
        -- Base case: the pattern itself
        SELECT
            n.id as ancestor_id,
            n.pattern_id as ancestor_pattern_id,
            n.generation,
            NULL::VARCHAR as edge_type,
            n.created_at,
            1 as depth,
            clock_timestamp() as query_time
        FROM pattern_lineage_nodes n
        WHERE n.id = p_pattern_node_id

        UNION ALL

        -- Recursive case: traverse parent edges with early termination
        SELECT
            parent.id,
            parent.pattern_id,
            parent.generation,
            e.edge_type,
            parent.created_at,
            a.depth + 1,
            clock_timestamp()
        FROM ancestry a
        JOIN pattern_lineage_edges e ON e.target_node_id = a.ancestor_id
        JOIN pattern_lineage_nodes parent ON parent.id = e.source_node_id
        WHERE a.depth < v_max_depth  -- Reduced depth limit
          AND clock_timestamp() - a.query_time < INTERVAL '50 milliseconds'  -- Early termination
    )
    SELECT
        a.ancestor_id,
        a.ancestor_pattern_id,
        a.generation,
        a.edge_type,
        a.created_at
    FROM ancestry a
    ORDER BY a.depth
    LIMIT 1000;  -- Prevent excessive result sets

    -- Reset statement timeout
    SET LOCAL statement_timeout = DEFAULT;

EXCEPTION WHEN OTHERS THEN
    -- Reset statement timeout on error
    SET LOCAL statement_timeout = DEFAULT;
    RAISE;
END;
$$;


-- Function to get direct parents only (1 level) - FAST alternative to full ancestry
CREATE OR REPLACE FUNCTION get_pattern_direct_parents(p_pattern_node_id UUID)
RETURNS TABLE (
    parent_id UUID,
    parent_pattern_id VARCHAR,
    edge_type VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT
        parent.id,
        parent.pattern_id,
        e.edge_type,
        parent.created_at
    FROM pattern_lineage_edges e
    JOIN pattern_lineage_nodes parent ON parent.id = e.source_node_id
    WHERE e.target_node_id = p_pattern_node_id
    ORDER BY parent.created_at DESC
    LIMIT 50;  -- Reasonable limit for direct parents
END;
$$;

-- Function to get descendants of a pattern
CREATE OR REPLACE FUNCTION get_pattern_descendants(p_pattern_node_id UUID)
RETURNS TABLE (
    descendant_id UUID,
    descendant_pattern_id VARCHAR,
    edge_type VARCHAR,
    transformation_type VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        n.id,
        n.pattern_id,
        e.edge_type,
        e.transformation_type,
        n.created_at
    FROM pattern_lineage_edges e
    JOIN pattern_lineage_nodes n ON n.id = e.target_node_id
    WHERE e.source_node_id = p_pattern_node_id
    ORDER BY n.created_at DESC;
END;
$$;


-- ============================================================================
-- Comments and Documentation
-- ============================================================================

COMMENT ON TABLE pattern_lineage_nodes IS 'Pattern instances in lineage graph with version snapshots';
COMMENT ON TABLE pattern_lineage_edges IS 'Directed relationships between pattern nodes forming evolution DAG';
COMMENT ON TABLE pattern_lineage_events IS 'Event log for all pattern lineage changes and audit trail';
COMMENT ON TABLE pattern_ancestry_cache IS 'Materialized ancestry paths for fast <200ms queries';

COMMENT ON FUNCTION invalidate_ancestry_cache IS 'Invalidate ancestry cache for pattern and descendants';
COMMENT ON FUNCTION get_pattern_ancestry IS 'Recursive query to get full ancestry chain with <200ms target';
COMMENT ON FUNCTION get_pattern_descendants IS 'Get direct descendants of a pattern node';

-- ============================================================================
-- Migration Complete
-- ============================================================================
