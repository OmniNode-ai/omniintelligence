#!/bin/bash
# Create Archon Ticket for Kafka Consumer EFFECT Node Implementation
# Usage: ./scripts/create_kafka_consumer_ticket.sh

set -e

TICKET_FILE="/Volumes/PRO-G40/Code/omniarchon/ARCHON_TICKET_KAFKA_CONSUMER.json"
ARCHON_API="http://localhost:8181"

echo "🎫 Creating Archon ticket for Kafka Consumer EFFECT Node..."
echo ""

# Check if Archon server is running
if ! curl -s "${ARCHON_API}/health" > /dev/null 2>&1; then
    echo "❌ Archon server is not running at ${ARCHON_API}"
    echo "   Please start the server first:"
    echo "   cd /Volumes/PRO-G40/Code/omniarchon && docker compose up -d"
    exit 1
fi

# Read ticket specification
if [ ! -f "$TICKET_FILE" ]; then
    echo "❌ Ticket specification file not found: $TICKET_FILE"
    exit 1
fi

TICKET_DATA=$(cat "$TICKET_FILE")

# Extract project ID (you may need to update this)
# For now, we'll use the Archon project if it exists, or create one
PROJECT_ID="archon-omninode-integration"

echo "📋 Ticket details:"
echo "   Title: Implement Kafka Consumer EFFECT Node for Bidirectional OmniNode Integration"
echo "   Priority: HIGHEST"
echo "   Assignee: agent-workflow-coordinator"
echo "   Feature: omninode-integration"
echo ""

# Create the ticket using Archon MCP API
# Note: Adjust this based on actual Archon API endpoint structure

echo "🚀 Creating ticket via Archon API..."

# Using Python to create the ticket via MCP
python3 << 'PYTHON_SCRIPT'
import json
import sys

# Load ticket data
with open("/Volumes/PRO-G40/Code/omniarchon/ARCHON_TICKET_KAFKA_CONSUMER.json") as f:
    ticket = json.load(f)

# Convert to Archon task format
task_data = {
    "title": ticket["title"],
    "description": ticket["description"],
    "assignee": ticket["assignee"],
    "task_order": ticket["task_order"],
    "feature": ticket["feature"],
    "sources": ticket["sources"],
    "code_examples": ticket["code_examples"]
}

print("Task data prepared:")
print(json.dumps(task_data, indent=2))

# Instructions for manual creation if API fails
print("\n" + "="*80)
print("MANUAL CREATION INSTRUCTIONS (if API is unavailable):")
print("="*80)
print("\n1. Open Claude Code MCP")
print("\n2. Use the following command:")
print('\nmcp__archon__create_task(')
print('    project_id="<your-project-id>",')
print(f'    title="{task_data["title"]}",')
print(f'    description="""{task_data["description"]}""",')
print(f'    assignee="{task_data["assignee"]}",')
print(f'    task_order={task_data["task_order"]},')
print(f'    feature="{task_data["feature"]}",')
print(f'    sources={json.dumps(task_data["sources"])},')
print(f'    code_examples={json.dumps(task_data["code_examples"])}')
print(')')
print("\n" + "="*80)
PYTHON_SCRIPT

echo ""
echo "✅ Ticket specification saved to: $TICKET_FILE"
echo "📖 Implementation plan: /Volumes/PRO-G40/Code/omniarchon/KAFKA_CONSUMER_EFFECT_NODE_PLAN.md"
echo ""
echo "Next steps:"
echo "1. Ensure Archon server is fully operational"
echo "2. Create project if needed: mcp__archon__create_project(...)"
echo "3. Create task using ticket specification above"
echo "4. Execute with agent-workflow-coordinator for parallel processing"
