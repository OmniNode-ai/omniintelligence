-- Freshness Database Schema
-- Purpose: Track document freshness, dependencies, and refresh operations
-- Database: Supabase PostgreSQL (omninode_bridge)
-- Created: 2025-10-22

-- =====================================================
-- Table 1: document_freshness
-- Purpose: Core document tracking and freshness scoring
-- =====================================================
CREATE TABLE IF NOT EXISTS document_freshness (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(64) UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    last_modified TIMESTAMP NOT NULL,
    last_analyzed TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP,

    -- Classification
    document_type VARCHAR(50) NOT NULL,
    classification_confidence FLOAT NOT NULL DEFAULT 0.0,
    language VARCHAR(50),

    -- Content analysis
    content_hash VARCHAR(64),
    content_summary TEXT,
    key_terms JSONB DEFAULT '[]',

    -- Freshness scoring
    freshness_score FLOAT NOT NULL DEFAULT 0.0,
    freshness_level VARCHAR(20) NOT NULL DEFAULT 'unknown',
    importance_score FLOAT NOT NULL DEFAULT 0.0,

    -- Dependencies
    depends_on JSONB DEFAULT '[]',
    dependent_by JSONB DEFAULT '[]',

    -- Metadata
    metadata JSONB DEFAULT '{}',
    tags JSONB DEFAULT '[]',

    -- Audit fields
    created_by VARCHAR(100) DEFAULT 'system',
    updated_by VARCHAR(100) DEFAULT 'system',
    updated_at TIMESTAMP DEFAULT NOW(),
    version INTEGER DEFAULT 1
);

-- =====================================================
-- Table 2: freshness_scores_history
-- Purpose: Historical tracking of freshness scores over time
-- =====================================================
CREATE TABLE IF NOT EXISTS freshness_scores_history (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(64) NOT NULL,
    score_timestamp TIMESTAMP DEFAULT NOW(),
    freshness_score FLOAT NOT NULL,
    freshness_level VARCHAR(20) NOT NULL,
    importance_score FLOAT NOT NULL,

    -- Score components
    age_score FLOAT,
    dependency_score FLOAT,
    usage_score FLOAT,
    content_change_score FLOAT,

    -- Context
    calculation_method VARCHAR(50),
    metadata JSONB DEFAULT '{}',

    FOREIGN KEY (document_id) REFERENCES document_freshness(document_id) ON DELETE CASCADE
);

-- =====================================================
-- Table 3: document_dependencies
-- Purpose: Track relationships between documents
-- =====================================================
CREATE TABLE IF NOT EXISTS document_dependencies (
    id SERIAL PRIMARY KEY,
    source_document_id VARCHAR(64) NOT NULL,
    target_document_id VARCHAR(64) NOT NULL,
    dependency_type VARCHAR(50) NOT NULL,
    dependency_strength FLOAT DEFAULT 1.0,

    -- Context
    detected_method VARCHAR(50),
    confidence FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(source_document_id, target_document_id, dependency_type),
    FOREIGN KEY (source_document_id) REFERENCES document_freshness(document_id) ON DELETE CASCADE,
    FOREIGN KEY (target_document_id) REFERENCES document_freshness(document_id) ON DELETE CASCADE
);

-- =====================================================
-- Table 4: refresh_operations_log
-- Purpose: Log of document refresh operations
-- =====================================================
CREATE TABLE IF NOT EXISTS refresh_operations_log (
    id SERIAL PRIMARY KEY,
    operation_id VARCHAR(64) UNIQUE NOT NULL,
    operation_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',

    -- Scope
    target_documents JSONB DEFAULT '[]',
    refresh_strategy JSONB DEFAULT '{}',

    -- Execution
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds FLOAT,

    -- Results
    documents_processed INTEGER DEFAULT 0,
    documents_updated INTEGER DEFAULT 0,
    documents_failed INTEGER DEFAULT 0,

    -- Details
    error_message TEXT,
    metadata JSONB DEFAULT '{}',

    -- Context
    triggered_by VARCHAR(100) DEFAULT 'system',
    trigger_reason TEXT
);

-- =====================================================
-- Table 5: freshness_metrics
-- Purpose: Performance and operational metrics
-- =====================================================
CREATE TABLE IF NOT EXISTS freshness_metrics (
    id SERIAL PRIMARY KEY,
    metric_timestamp TIMESTAMP DEFAULT NOW(),
    metric_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,

    -- Context
    document_id VARCHAR(64),
    operation_id VARCHAR(64),
    metadata JSONB DEFAULT '{}',

    -- Grouping
    metric_category VARCHAR(50),
    metric_tags JSONB DEFAULT '[]'
);

-- =====================================================
-- INDEXES
-- Purpose: Optimize query performance
-- =====================================================

-- document_freshness indexes
CREATE INDEX IF NOT EXISTS idx_document_freshness_document_id ON document_freshness(document_id);
CREATE INDEX IF NOT EXISTS idx_document_freshness_last_modified ON document_freshness(last_modified);
CREATE INDEX IF NOT EXISTS idx_document_freshness_freshness_level ON document_freshness(freshness_level);
CREATE INDEX IF NOT EXISTS idx_document_freshness_document_type ON document_freshness(document_type);

-- freshness_scores_history indexes
CREATE INDEX IF NOT EXISTS idx_freshness_scores_document_id ON freshness_scores_history(document_id);
CREATE INDEX IF NOT EXISTS idx_freshness_scores_timestamp ON freshness_scores_history(score_timestamp);

-- document_dependencies indexes
CREATE INDEX IF NOT EXISTS idx_document_dependencies_source ON document_dependencies(source_document_id);
CREATE INDEX IF NOT EXISTS idx_document_dependencies_target ON document_dependencies(target_document_id);

-- refresh_operations_log indexes
CREATE INDEX IF NOT EXISTS idx_refresh_operations_status ON refresh_operations_log(status);
CREATE INDEX IF NOT EXISTS idx_refresh_operations_started ON refresh_operations_log(started_at);

-- freshness_metrics indexes
CREATE INDEX IF NOT EXISTS idx_freshness_metrics_timestamp ON freshness_metrics(metric_timestamp);
CREATE INDEX IF NOT EXISTS idx_freshness_metrics_type ON freshness_metrics(metric_type);

-- =====================================================
-- VERIFICATION QUERIES
-- Purpose: Verify schema was created successfully
-- =====================================================
-- Run these after migration to verify:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE '%freshness%';
-- SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE '%freshness%';
