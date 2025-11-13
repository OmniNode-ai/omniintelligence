# Archon MCP External Gateway - Quick Reference

## Current Status: ✅ Working as Designed

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARCHON MCP ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Docker Environment (Production):                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  archon_menu Tool                                        │  │
│  │  ├─ Internal Operations (68 tools) ──→ HTTP Services ✅  │  │
│  │  └─ External Operations (100+ tools) ──→ Gateway ❌      │  │
│  │                                                           │  │
│  │  External Gateway: DISABLED                              │  │
│  │  Reason: stdio services need host access                 │  │
│  │  Status: Graceful degradation active                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Host Environment (Development/Testing):                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  archon_menu Tool                                        │  │
│  │  ├─ Internal Operations (68 tools) ──→ HTTP Services ✅  │  │
│  │  └─ External Operations (100+ tools) ──→ Gateway ✅      │  │
│  │                                          │                │  │
│  │                                          └─→ zen          │  │
│  │                                          └─→ codanna      │  │
│  │                                          └─→ serena       │  │
│  │                                          └─→ sequential-* │  │
│  │                                                           │  │
│  │  External Gateway: ENABLED                               │  │
│  │  Status: Full functionality                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration Summary

### Docker (Production)
```bash
ARCHON_ENABLE_EXTERNAL_GATEWAY=false  # Default in docker-compose.yml
```
- ✅ Internal services: Working
- ❌ External services: Disabled (gracefully)
- 📝 Logs: Clear informational messages
- 🛡️  Status: Production-ready

### Host (.env)
```bash
ARCHON_ENABLE_EXTERNAL_GATEWAY=true
```
- ✅ Internal services: Working
- ✅ External services: Enabled
- 📦 Services: zen, codanna, serena, sequential-thinking
- ⚙️  Requirements: Node.js, Python/uv, Rust/cargo

## Usage Examples

### Internal Operations (Always Available)
```python
# Quality assessment
archon_menu(
    operation="assess_code_quality",
    params={"content": code, "source_path": "test.py", "language": "python"}
)

# Performance optimization
archon_menu(
    operation="identify_optimization_opportunities",
    params={"operation_name": "slow_endpoint"}
)

# Cache management
archon_menu(
    operation="manage_cache",
    params={"operation": "get_metrics"}
)
```

### External Operations (Host Only)
```python
# Zen AI chat
archon_menu(
    operation="zen.chat",
    params={"prompt": "Explain async/await", "model": "gemini-2.5-pro"}
)

# Zen version check
archon_menu(operation="zen.version")

# Codanna symbol search
archon_menu(
    operation="codanna.search_symbols",
    params={"query": "AuthService"}
)

# Sequential thinking
archon_menu(
    operation="sequential-thinking.sequentialthinking",
    params={"query": "What is the best approach to..."}
)
```

### Discovery (Check Available Tools)
```python
# List all available tools
archon_menu(operation="discover")

# Returns:
# {
#   "success": true,
#   "internal_tool_count": 68,
#   "external_tool_count": 0,  # 0 in Docker, 100+ on host
#   "internal_catalog": "...",
#   "external_catalog": "...",  # Only on host
#   "total_operations": 68      # 168+ on host
# }
```

## Error Handling

### External Tool in Docker
```json
{
  "success": false,
  "operation": "zen.chat",
  "error": "External MCP gateway not available",
  "hint": "Operation 'zen.chat' appears to be an external MCP tool (contains '.'),
           but gateway is not initialized. Check ARCHON_ENABLE_EXTERNAL_GATEWAY
           environment variable and gateway startup logs."
}
```

## Configured External Services

| Service | Tools | Transport | Status | Dependencies |
|---------|-------|-----------|--------|--------------|
| zen | 12 | stdio | ✅ Enabled | Python venv |
| codanna | 7 | stdio | ✅ Enabled | Rust/cargo |
| serena | 24 | stdio | ✅ Enabled | Python/uv |
| sequential-thinking | 1 | stdio | ✅ Enabled | Node.js/npx |
| context7 | 2 | stdio | ❌ Disabled | Stability issues |

**Total External Tools**: 100+ (when gateway enabled)

## Testing External Services

### 1. Run MCP Server on Host
```bash
# Stop Docker MCP (optional)
docker compose stop archon-mcp

# Start on host
cd python
poetry install
poetry run python -m src.mcp_server.mcp_server
```

### 2. Verify Gateway Initialization
Check logs for:
```
✓ External MCP gateway initialized - X tools discovered
📦 zen: 12 tools
📦 codanna: 7 tools
📦 serena: 24 tools
📦 sequential-thinking: 1 tool
```

### 3. Test External Tool
```python
# Via Claude Code or direct MCP call
result = archon_menu(operation="zen.version")
# Should return zen version info
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "External MCP gateway not available" | Gateway disabled | Run MCP server on host |
| "Discovery timed out after 60s" | Service not responding | Disable problematic service |
| Tool not found | Service not enabled | Check mcp_services.yaml |
| Path errors | Wrong service path | Update .env paths |

## Key Files

```
python/
├── .env                              # Host environment config
├── config/
│   └── mcp_services.yaml            # Service configuration
└── src/
    └── mcp_server/
        ├── mcp_server.py            # Gateway initialization (L203-247)
        ├── tools/
        │   └── archon_menu.py       # Unified routing (L309-406)
        └── gateway/
            └── unified_gateway.py   # Gateway implementation
```

## Environment Variables

```bash
# Gateway Control
ARCHON_ENABLE_EXTERNAL_GATEWAY=true    # true (host) / false (docker)

# External Service Paths (host only)
ZEN_PYTHON_PATH=/path/to/zen/.zen_venv/bin/python
ZEN_SERVER_PATH=/path/to/zen/server.py
CODANNA_PATH=/path/to/.cargo/bin/codanna
SERENA_PATH=/path/to/serena
UV_PATH=/path/to/.local/bin/uv
```

## Recommendations

### ✅ Production (Docker)
- Keep `ARCHON_ENABLE_EXTERNAL_GATEWAY=false`
- Use internal operations only
- Stable, isolated, production-ready

### ✅ Development (Host)
- Set `ARCHON_ENABLE_EXTERNAL_GATEWAY=true`
- Access all 168+ operations
- Requires external service dependencies

### 🔮 Future (HTTP-based External Services)
- Convert stdio services to HTTP/SSE
- Enable Docker deployment with external tools
- No host dependency required

---

**Status**: ✅ System working as designed
**Last Updated**: 2025-10-18
**Full Report**: See `EXTERNAL_GATEWAY_INVESTIGATION_REPORT.md`
