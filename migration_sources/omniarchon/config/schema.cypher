// OmniMemory Causal Graph Schema
// Cypher schema for Memgraph-based causal graph system
// Created: 2025-08-06

// =============================================================================
// NODE TYPES AND CONSTRAINTS
// =============================================================================

// Create node type constraints for better performance and data integrity

// ToolCall nodes - represent tool executions
CREATE CONSTRAINT ON (n:ToolCall) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:ToolCall) ASSERT exists(n.id);
CREATE CONSTRAINT ON (n:ToolCall) ASSERT exists(n.tool_name);
CREATE CONSTRAINT ON (n:ToolCall) ASSERT exists(n.correlation_id);
CREATE CONSTRAINT ON (n:ToolCall) ASSERT exists(n.created_at);

// File nodes - represent file operations
CREATE CONSTRAINT ON (n:File) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:File) ASSERT exists(n.id);
CREATE CONSTRAINT ON (n:File) ASSERT exists(n.path);
CREATE CONSTRAINT ON (n:File) ASSERT exists(n.correlation_id);

// Event nodes - represent message bus events
CREATE CONSTRAINT ON (n:Event) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Event) ASSERT exists(n.id);
CREATE CONSTRAINT ON (n:Event) ASSERT exists(n.topic);
CREATE CONSTRAINT ON (n:Event) ASSERT exists(n.correlation_id);

// Prompt nodes - represent AI prompts and completions
CREATE CONSTRAINT ON (n:Prompt) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Prompt) ASSERT exists(n.id);
CREATE CONSTRAINT ON (n:Prompt) ASSERT exists(n.role);
CREATE CONSTRAINT ON (n:Prompt) ASSERT exists(n.correlation_id);

// Debug nodes - represent debug log entries
CREATE CONSTRAINT ON (n:Debug) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Debug) ASSERT exists(n.id);
CREATE CONSTRAINT ON (n:Debug) ASSERT exists(n.log_level);
CREATE CONSTRAINT ON (n:Debug) ASSERT exists(n.correlation_id);

// Session nodes - represent Claude Code sessions
CREATE CONSTRAINT ON (n:Session) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Session) ASSERT exists(n.id);
CREATE CONSTRAINT ON (n:Session) ASSERT exists(n.created_at);

// =============================================================================
// RELATIONSHIP TYPES
// =============================================================================

// No constraints needed for relationships in Memgraph, but we define the types:
// CALLS_TOOL - ToolCall -> ToolCall (nested tool calls)
// OUTPUTS_FILE - ToolCall -> File (tool creates/modifies file)
// EMITS_EVENT - ToolCall -> Event (tool triggers event)
// RESPONDS_TO - Prompt -> ToolCall (prompt triggers tool)
// LOGS_ABOUT - Debug -> ToolCall/File/Event (debug entry relates to entity)
// CAUSES - Event -> Event (event chain causality)
// BELONGS_TO_SESSION - All nodes -> Session (session grouping)
// CORRELATES_WITH - Any -> Any (correlation relationships)
// PRECEDES - Any -> Any (temporal ordering)
// DEPENDS_ON - Any -> Any (dependency relationships)

// =============================================================================
// INDEXES FOR PERFORMANCE
// =============================================================================

// Temporal indexes for time-based queries
CREATE INDEX ON :ToolCall(created_at);
CREATE INDEX ON :File(created_at);
CREATE INDEX ON :Event(created_at);
CREATE INDEX ON :Prompt(created_at);
CREATE INDEX ON :Debug(created_at);
CREATE INDEX ON :Session(created_at);

// Correlation indexes for linking
CREATE INDEX ON :ToolCall(correlation_id);
CREATE INDEX ON :File(correlation_id);
CREATE INDEX ON :Event(correlation_id);
CREATE INDEX ON :Prompt(correlation_id);
CREATE INDEX ON :Debug(correlation_id);

// Session indexes for grouping
CREATE INDEX ON :ToolCall(session_id);
CREATE INDEX ON :File(session_id);
CREATE INDEX ON :Event(session_id);
CREATE INDEX ON :Prompt(session_id);
CREATE INDEX ON :Debug(session_id);

// Tool-specific indexes
CREATE INDEX ON :ToolCall(tool_name);
CREATE INDEX ON :File(path);
CREATE INDEX ON :Event(topic);
CREATE INDEX ON :Prompt(role);
CREATE INDEX ON :Debug(log_level);

// =============================================================================
// EXAMPLE QUERIES AND PATTERNS
// =============================================================================

// Example: Find all tool calls in a session with their files
// MATCH (s:Session {id: $session_id})<-[:BELONGS_TO_SESSION]-(tc:ToolCall)
// OPTIONAL MATCH (tc)-[:OUTPUTS_FILE]->(f:File)
// RETURN tc, f ORDER BY tc.created_at;

// Example: Trace causal chain from a tool call
// MATCH path = (start:ToolCall {id: $tool_call_id})-[:CALLS_TOOL|OUTPUTS_FILE|EMITS_EVENT*1..10]->(end)
// RETURN path ORDER BY length(path);

// Example: Find all events caused by a specific correlation
// MATCH (n)-[:CORRELATES_WITH*1..5]-(related)
// WHERE n.correlation_id = $correlation_id
// RETURN n, related;

// Example: Time-machine query - all activity in time range
// MATCH (n)
// WHERE n.created_at >= $start_time AND n.created_at <= $end_time
// OPTIONAL MATCH (n)-[r]-(related)
// RETURN n, r, related ORDER BY n.created_at;

// =============================================================================
// GRAPH ANALYTICS PREPARATION
// =============================================================================

// Enable graph algorithms for pattern analysis
// These will be used for:
// - Finding shortest paths between events
// - Detecting anomalous patterns
// - Clustering related events
// - PageRank for importance scoring

// Example algorithm usage:
// CALL pagerank.get() YIELD node, rank
// RETURN node.id, node.tool_name, rank ORDER BY rank DESC LIMIT 10;

// =============================================================================
// STREAMING INTEGRATION SETUP
// =============================================================================

// Kafka stream transformations will be set up via Python API
// This schema supports real-time ingestion of:
// 1. Claude Code hook events -> ToolCall nodes
// 2. File system events -> File nodes
// 3. Message bus events -> Event nodes
// 4. Debug log entries -> Debug nodes
// 5. Prompt/completion pairs -> Prompt nodes

// All streaming ingestion will maintain:
// - Correlation ID linking
// - Temporal ordering
// - Session grouping
// - Causal relationships
