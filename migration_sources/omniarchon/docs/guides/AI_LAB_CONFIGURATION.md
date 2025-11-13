# AI Lab Configuration

**Last Updated**: 2025-09-30

## 🖥️ Active Machines

### 1. Mac Studio (Primary Ollama Server)
- **IP**: 192.168.86.200
- **Port**: 11434
- **Endpoint**: http://192.168.86.200:11434
- **Purpose**: AI Quorum, Ollama embeddings (nomic-embed-text)
- **Models**:
  - `codestral:22b-v0.1-q4_K_M` (AI Quorum, weight: 1.5)
  - `nomic-embed-text` (768d embeddings for Event Memory)
- **Status**: ✅ Operational
- **Integrations**:
  - Claude Code hooks (AI Quorum)
  - Archon MCP (embeddings)
  - Event Memory Store (Phase 6)

### 2. AI PC - RTX 5090 (vLLM Primary)
- **IP**: 192.168.86.201
- **GPU**: RTX 5090 (GPU 0)
- **Port**: 8000
- **Endpoint**: http://192.168.86.201:8000/v1
- **API Format**: OpenAI-compatible
- **Purpose**: Code generation, deep reasoning
- **Models**:
  - `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct` (max_len: 4096)
- **Status**: ✅ Operational (Just verified)
- **Integrations**:
  - ⏳ Pending: Claude Code hooks integration
  - ⏳ Pending: Archon MCP integration

### 3. AI PC - RTX 4090 (vLLM Secondary)
- **IP**: 192.168.86.201
- **GPU**: RTX 4090 (GPU 1)
- **Port**: 8001
- **Endpoint**: http://192.168.86.201:8001/v1
- **API Format**: OpenAI-compatible
- **Purpose**: General reasoning, backup code model
- **Models**:
  - `meta-llama/Meta-Llama-3.1-8B-Instruct` (max_len: 8192)
- **Status**: ✅ Operational
- **Integrations**:
  - ✅ Claude Code hooks (AI Quorum, weight: 1.2)
  - ⏳ Pending: Archon MCP integration

### 4. Mac Mini (Ollama Model Server)
- **IP**: 192.168.86.101
- **Port**: 11434
- **Endpoint**: http://192.168.86.101:11434
- **Purpose**: Diverse model hosting, specialized inference
- **Models**:
  - `gpt-oss:20b` (20.9B, general reasoning)
  - `deepseek-coder-v2:latest` (15.7B, code generation)
  - `deepseek-coder:6.7b` (7B, lightweight code model)
  - `llama3.1:latest` (8B, general model)
  - `nomic-embed-text:latest` (137M, embeddings)
- **Status**: ✅ Operational
- **Integrations**:
  - ⏳ Pending: Claude Code hooks integration
  - ⏳ Pending: Archon MCP integration

## 🔧 Integration Configuration

### Claude Code Hooks
**Location**: `~/.claude/hooks/config.yaml`

```yaml
# AI Quorum Settings (Phase 4)
quorum:
  enabled: true
  models:
    codestral:
      enabled: true
      type: "ollama"
      name: "codestral:22b-v0.1-q4_K_M"
      weight: 1.5
      timeout: 5.0

    deepseek:
      enabled: true
      type: "openai"
      base_url: "http://192.168.86.201:8000/v1"
      name: "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
      weight: 2.0
      timeout: 5.0

    llama:
      enabled: true
      type: "openai"
      base_url: "http://192.168.86.201:8001/v1"
      name: "meta-llama/Meta-Llama-3.1-8B-Instruct"
      weight: 1.2
      timeout: 5.0

  ollama:
    base_url: "http://192.168.86.200:11434"

# Event Memory Store (Phase 6)
reflex_arc:
  event_memory:
    ollama_url: "http://192.168.86.200:11434"
    embedding_model: "nomic-embed-text"
```

### Archon MCP
**Services**: Main Server (8181), Intelligence (8053), Search (8055)

```env
# LLM Configuration
OLLAMA_BASE_URL=http://192.168.86.200:11434

# Optional: vLLM for advanced code generation
VLLM_BASE_URL=http://192.168.86.201:8000/v1
VLLM_MODEL=deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct
```

## 📊 Capacity Planning

| Machine | Purpose | Capacity | Current Use | Available |
|---------|---------|----------|-------------|-----------|
| Mac Studio | Ollama (Embeddings, Quorum) | ~32GB VRAM | 40% | 60% |
| RTX 5090 | vLLM Code Gen (DeepSeek) | ~24GB VRAM | 35% | 65% |
| RTX 4090 | vLLM General (Llama 3.1) | ~24GB VRAM | 25% | 75% |
| Mac Mini | Ollama (Diverse Models) | ~16GB VRAM | 30% | 70% |

**Total AI Workload Capacity**: 4 machines, ~96GB combined VRAM

**AI Quorum Weights**: 5.7 total
- DeepSeek (RTX 5090): 2.0 (35% influence)
- Codestral (Mac Studio): 1.5 (26% influence)
- Llama 3.1 (RTX 4090): 1.2 (21% influence)
- Gemini Flash: 1.0 (18% influence)

## 🚀 Expansion Plan

### Phase 1 (Current): Foundation
- ✅ Mac Studio (Ollama)
- ✅ RTX 5090 (vLLM primary)
- ⏳ RTX 4090 (vLLM secondary - needs API config)

### Phase 2 (Next): Integration
- Add RTX 5090 to Claude Code hooks (AI Quorum expansion)
- Configure RTX 4090 with proper OpenAI endpoint
- Load balancing across vLLM instances

### Phase 3 (Current): Mac Mini Integration
- ✅ Mac Mini discovered (192.168.86.101)
- 5 models available: gpt-oss:20b, deepseek-coder-v2, etc.
- Candidate for AI Quorum expansion

## 🔍 Testing & Verification

### Mac Studio (Ollama)
```bash
# Test Ollama
curl http://192.168.86.200:11434/api/tags

# Test embeddings
curl http://192.168.86.200:11434/api/embeddings \
  -d '{"model":"nomic-embed-text","prompt":"test"}'
```

### RTX 5090 (vLLM)
```bash
# Test models endpoint
curl http://192.168.86.201:8000/v1/models

# Test completion
curl http://192.168.86.201:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct","prompt":"def hello():"}'
```

## 📝 Notes

### Network Configuration
- Subnet: 192.168.86.0/24
- All machines on same LAN
- No authentication required (internal network)

### Model Selection Strategy
- **Embeddings**: nomic-embed-text (768d, fast)
- **Code Review**: codestral (22B, specialized)
- **Code Generation**: DeepSeek-Coder (efficient, OpenAI compatible)

### Performance Targets
- Ollama embedding: <100ms
- AI Quorum scoring: <1000ms
- vLLM completion: <2000ms (depends on length)

---

**Next Steps**:
1. ✅ Document 5090 configuration
2. ⏳ Configure 4090 OpenAI endpoint
3. ⏳ Integrate 5090 into Claude Code hooks
4. ⏳ Load balancing strategy
