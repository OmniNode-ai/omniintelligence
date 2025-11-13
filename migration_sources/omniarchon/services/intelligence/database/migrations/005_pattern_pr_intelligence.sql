-- Migration 005: Pattern PR Intelligence
-- Date: 2025-10-28
-- Purpose: Add table for tracking pattern mentions in PR reviews and correlating with PR outcomes
-- Dependencies: 003_pattern_lineage_tables.sql (pattern_lineage_nodes)

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Pattern PR Intelligence Table
-- Stores pattern mentions extracted from PR reviews, comments, and descriptions
-- Links patterns to PR outcomes for intelligence gathering
CREATE TABLE IF NOT EXISTS pattern_pr_intelligence (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key to pattern_lineage_nodes
    pattern_id UUID NOT NULL REFERENCES pattern_lineage_nodes(id) ON DELETE CASCADE,

    -- PR identification
    pr_number INTEGER NOT NULL,
    pr_repository VARCHAR(255) NOT NULL,
    pr_url TEXT,

    -- Mention context
    mention_type VARCHAR(50) NOT NULL,
    -- Valid values: 'description', 'review_comment', 'inline_comment', 'commit_message'

    -- Sentiment analysis
    sentiment VARCHAR(20) NOT NULL,
    -- Valid values: 'positive', 'negative', 'neutral'

    -- Extracted content
    extracted_text TEXT NOT NULL,
    full_context TEXT,

    -- PR outcome tracking
    pr_outcome VARCHAR(20),
    -- Valid values: 'approved', 'changes_requested', 'commented', 'merged', 'closed', 'pending'

    pr_merged BOOLEAN DEFAULT FALSE,
    time_to_merge_hours NUMERIC(10,2),

    -- Authorship and timing
    author VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pr_created_at TIMESTAMP WITH TIME ZONE,
    pr_merged_at TIMESTAMP WITH TIME ZONE,

    -- Intelligence metadata
    correlation_id UUID,
    extraction_method VARCHAR(50) DEFAULT 'langextract',
    confidence_score NUMERIC(3,2),

    -- Additional metadata
    metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT valid_mention_type CHECK (
        mention_type IN ('description', 'review_comment', 'inline_comment', 'commit_message')
    ),
    CONSTRAINT valid_sentiment CHECK (
        sentiment IN ('positive', 'negative', 'neutral')
    ),
    CONSTRAINT valid_pr_outcome CHECK (
        pr_outcome IS NULL OR pr_outcome IN (
            'approved', 'changes_requested', 'commented', 'merged', 'closed', 'pending'
        )
    ),
    CONSTRAINT valid_confidence_score CHECK (
        confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)
    )
);

-- Indexes for common query patterns

-- Index on pattern_id for finding all PR mentions of a pattern
CREATE INDEX idx_pattern_pr_intelligence_pattern
    ON pattern_pr_intelligence(pattern_id);

-- Index on PR outcome for finding patterns in successful/failed PRs
CREATE INDEX idx_pattern_pr_intelligence_outcome
    ON pattern_pr_intelligence(pr_outcome);

-- Index on PR repository and number for finding all patterns in a PR
CREATE INDEX idx_pattern_pr_intelligence_pr
    ON pattern_pr_intelligence(pr_repository, pr_number);

-- Index on sentiment for sentiment analysis queries
CREATE INDEX idx_pattern_pr_intelligence_sentiment
    ON pattern_pr_intelligence(sentiment);

-- Index on mention type for filtering by comment type
CREATE INDEX idx_pattern_pr_intelligence_mention_type
    ON pattern_pr_intelligence(mention_type);

-- Index on created_at for time-based queries
CREATE INDEX idx_pattern_pr_intelligence_created_at
    ON pattern_pr_intelligence(created_at DESC);

-- Composite index for pattern quality analysis
-- Find patterns with positive mentions in merged PRs
CREATE INDEX idx_pattern_pr_intelligence_quality
    ON pattern_pr_intelligence(pattern_id, sentiment, pr_merged)
    WHERE pr_merged = TRUE;

-- GIN index on metadata for flexible querying
CREATE INDEX idx_pattern_pr_intelligence_metadata
    ON pattern_pr_intelligence USING GIN(metadata);

-- Index on correlation_id for tracing
CREATE INDEX idx_pattern_pr_intelligence_correlation
    ON pattern_pr_intelligence(correlation_id);

-- Comments for documentation
COMMENT ON TABLE pattern_pr_intelligence IS
    'Stores pattern mentions extracted from PR reviews and correlates them with PR outcomes for pattern quality intelligence';

COMMENT ON COLUMN pattern_pr_intelligence.pattern_id IS
    'Reference to the pattern in pattern_lineage_nodes';

COMMENT ON COLUMN pattern_pr_intelligence.mention_type IS
    'Type of PR content where pattern was mentioned: description, review_comment, inline_comment, commit_message';

COMMENT ON COLUMN pattern_pr_intelligence.sentiment IS
    'Sentiment of the mention: positive (recommended/praised), negative (criticized), neutral (mentioned)';

COMMENT ON COLUMN pattern_pr_intelligence.pr_outcome IS
    'Final outcome of the PR: approved, changes_requested, commented, merged, closed, pending';

COMMENT ON COLUMN pattern_pr_intelligence.confidence_score IS
    'Confidence score (0-1) of the pattern extraction from langextract';

-- Create view for pattern PR statistics
CREATE OR REPLACE VIEW pattern_pr_statistics AS
SELECT
    p.pattern_id,
    p.pattern_name,
    p.pattern_type,
    COUNT(DISTINCT pri.id) AS total_mentions,
    COUNT(DISTINCT pri.pr_number) AS prs_mentioned_in,
    COUNT(DISTINCT CASE WHEN pri.sentiment = 'positive' THEN pri.id END) AS positive_mentions,
    COUNT(DISTINCT CASE WHEN pri.sentiment = 'negative' THEN pri.id END) AS negative_mentions,
    COUNT(DISTINCT CASE WHEN pri.pr_merged = TRUE THEN pri.pr_number END) AS merged_prs,
    AVG(CASE WHEN pri.pr_merged = TRUE THEN pri.time_to_merge_hours END) AS avg_time_to_merge_hours,
    ROUND(
        COUNT(DISTINCT CASE WHEN pri.sentiment = 'positive' THEN pri.id END)::NUMERIC /
        NULLIF(COUNT(DISTINCT pri.id), 0),
        4
    ) AS positive_sentiment_ratio,
    MAX(pri.created_at) AS last_mentioned_at
FROM
    pattern_lineage_nodes p
    LEFT JOIN pattern_pr_intelligence pri ON p.id = pri.pattern_id
GROUP BY
    p.id, p.pattern_id, p.pattern_name, p.pattern_type;

COMMENT ON VIEW pattern_pr_statistics IS
    'Aggregated statistics for pattern PR mentions and outcomes';

-- Migration verification query
-- Run this to verify the migration succeeded
DO $$
BEGIN
    RAISE NOTICE 'Migration 005 completed successfully';
    RAISE NOTICE 'Created table: pattern_pr_intelligence';
    RAISE NOTICE 'Created view: pattern_pr_statistics';
    RAISE NOTICE 'Created % indexes', (
        SELECT COUNT(*)
        FROM pg_indexes
        WHERE tablename = 'pattern_pr_intelligence'
    );
END $$;
