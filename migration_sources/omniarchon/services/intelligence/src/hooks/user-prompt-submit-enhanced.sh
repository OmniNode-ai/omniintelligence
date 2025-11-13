#!/bin/bash
# UserPromptSubmit Hook - Enhanced Agent Layer
# Detects agent invocations and injects intelligence context

set -euo pipefail

# Configuration
LOG_FILE="$HOME/.claude/hooks/hook-enhanced.log"
HOOKS_LIB="$HOME/.claude/hooks/lib"
export PYTHONPATH="${HOOKS_LIB}:${PYTHONPATH:-}"

# Environment variables
export ARCHON_MCP_URL="${ARCHON_MCP_URL:-http://localhost:8051}"
export ARCHON_INTELLIGENCE_URL="${ARCHON_INTELLIGENCE_URL:-http://localhost:8053}"

# Read stdin (Claude Code sends JSON)
INPUT=$(cat)

# Log hook trigger
echo "[$(date '+%Y-%m-%d %H:%M:%S')] UserPromptSubmit hook triggered" >> "$LOG_FILE"

# Extract prompt from JSON
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""')

if [[ -z "$PROMPT" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: No prompt in input" >> "$LOG_FILE"
    echo "$INPUT"
    exit 0
fi

# Log prompt (first 100 chars)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Prompt: ${PROMPT:0:100}..." >> "$LOG_FILE"

# Detect agent invocation using agent_detector.py
AGENT_DETECTION=$(python3 "${HOOKS_LIB}/agent_detector.py" "$PROMPT" 2>>"$LOG_FILE" || echo "NO_AGENT_DETECTED")

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Detection result: $AGENT_DETECTION" >> "$LOG_FILE"

# Check if agent was detected
if [[ "$AGENT_DETECTION" == "NO_AGENT_DETECTED" ]] || [[ -z "$AGENT_DETECTION" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] No agent detected, passing through" >> "$LOG_FILE"
    echo "$INPUT"
    exit 0
fi

# Extract agent information
AGENT_NAME=$(echo "$AGENT_DETECTION" | grep "AGENT_DETECTED:" | cut -d: -f2 | tr -d ' ')
DOMAIN_QUERY=$(echo "$AGENT_DETECTION" | grep "DOMAIN_QUERY:" | cut -d: -f2-)
IMPL_QUERY=$(echo "$AGENT_DETECTION" | grep "IMPLEMENTATION_QUERY:" | cut -d: -f2-)
AGENT_DOMAIN=$(echo "$AGENT_DETECTION" | grep "AGENT_DOMAIN:" | cut -d: -f2-)
AGENT_PURPOSE=$(echo "$AGENT_DETECTION" | grep "AGENT_PURPOSE:" | cut -d: -f2-)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Agent detected: $AGENT_NAME" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Domain: $AGENT_DOMAIN" >> "$LOG_FILE"

# Generate correlation ID
CORRELATION_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')

# Track intent pattern (synchronous, but fast - typically <100ms)
if [[ -n "$AGENT_NAME" ]] && [[ "$AGENT_NAME" != "" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Tracking intent pattern for $AGENT_NAME" >> "$LOG_FILE"

    # Call pattern tracker synchronously (blocking, but fast)
    python3 "${HOOKS_LIB}/track_intent.py" \
        --prompt "$PROMPT" \
        --agent "$AGENT_NAME" \
        --domain "$AGENT_DOMAIN" \
        --purpose "$AGENT_PURPOSE" \
        --correlation-id "$CORRELATION_ID" \
        --session-id "${SESSION_ID:-}" \
        >> "$LOG_FILE" 2>&1 || echo "[$(date '+%Y-%m-%d %H:%M:%S')] Intent tracking failed (continuing)" >> "$LOG_FILE"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Intent tracking complete" >> "$LOG_FILE"
fi

# Trigger background intelligence gathering (async, non-blocking)
if [[ -n "$DOMAIN_QUERY" ]] && [[ "$DOMAIN_QUERY" != "" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting background RAG query for domain" >> "$LOG_FILE"
    (
        curl -s -X POST "${ARCHON_MCP_URL}/api/rag/query" \
            -H "Content-Type: application/json" \
            -d "{\"query\": \"$DOMAIN_QUERY\", \"match_count\": 5, \"context\": \"general\"}" \
            > "/tmp/agent_intelligence_domain_${CORRELATION_ID}.json" 2>&1
    ) &
fi

if [[ -n "$IMPL_QUERY" ]] && [[ "$IMPL_QUERY" != "" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting background RAG query for implementation" >> "$LOG_FILE"
    (
        curl -s -X POST "${ARCHON_MCP_URL}/api/rag/query" \
            -H "Content-Type: application/json" \
            -d "{\"query\": \"$IMPL_QUERY\", \"match_count\": 3, \"context\": \"general\"}" \
            > "/tmp/agent_intelligence_impl_${CORRELATION_ID}.json" 2>&1
    ) &
fi

# Build enhanced context
AGENT_CONTEXT=$(cat <<EOF

---
🤖 [Agent Framework Context - Auto-injected by hooks]

**Agent Detected**: ${AGENT_NAME}
**Agent Domain**: ${AGENT_DOMAIN}
**Agent Purpose**: ${AGENT_PURPOSE}

**Framework References**:
- @MANDATORY_FUNCTIONS.md (47 required functions across 11 categories)
- @quality-gates-spec.yaml (23 quality gates for validation)
- @performance-thresholds.yaml (33 performance thresholds)
- @COMMON_WORKFLOW.md (Agent workflow patterns)

**Intelligence Gathering**:
- Domain Query: ${DOMAIN_QUERY:0:80}...
- Implementation Query: ${IMPL_QUERY:0:80}...
- RAG queries executed in background (check /tmp/agent_intelligence_*)
- Correlation ID: ${CORRELATION_ID}

**Archon MCP Integration**:
- MCP Server: ${ARCHON_MCP_URL}
- Intelligence Service: ${ARCHON_INTELLIGENCE_URL}

**Mandatory Execution**:
All 47 mandatory functions (IC-001 to FI-004) and 23 quality gates will be enforced through PreToolUse and PostToolUse hooks.
EOF
)

# Inject context into prompt
ENHANCED_PROMPT="${PROMPT}${AGENT_CONTEXT}"

echo "[$(date '+%Y-%m-d %H:%M:%S')] Context injected, correlation: $CORRELATION_ID" >> "$LOG_FILE"

# Output enhanced prompt via hookSpecificOutput.additionalContext
echo "$INPUT" | jq --arg context "$AGENT_CONTEXT" '.hookSpecificOutput.hookEventName = "UserPromptSubmit" | .hookSpecificOutput.additionalContext = $context'

exit 0
