# Traceability & Pattern Learning - Architecture Diagrams

**Visual reference for system architecture**

---

## 1. Complete System Overview

```mermaid
graph TB
    subgraph "Claude Code Environment"
        A[User Prompt] --> B[UserPromptSubmit Hook]
        B --> C[Generate Correlation ID]
        C --> D[Enhanced Agent Router]
        D --> E[PreToolUse Hook]
        E --> F[Agent Execution]
        F --> G[PostToolUse Hook]
        G --> H[Stop Hook]
    end

    subgraph "Tracing Layer"
        C -.->|Log| I[Trace Start Event]
        D -.->|Log| J[Routing Decision]
        E -.->|Log| K[Hook Execution]
        F -.->|Log| L[Endpoint Calls]
        G -.->|Log| M[Hook Completion]
        H -.->|Log| N[Execution Complete]
    end

    subgraph "Archon Intelligence Service"
        I --> O[Trace Assembly Service]
        J --> O
        K --> O
        L --> O
        M --> O
        N --> O

        O --> P[Complete Execution Trace]
        P --> Q{Success?}

        Q -->|Yes| R[Pattern Extractor]
        Q -->|No| S[Error Analyzer]

        R --> T[Success Patterns DB]
        S --> U[Error Patterns DB]
    end

    subgraph "Pattern Learning"
        T --> V[Pattern Matcher]
        V --> W[Vector Search<br/>Qdrant]
        V --> X[Graph Analysis<br/>Memgraph]

        V --> Y[Pattern Match Found]
        Y --> Z[Generate Replay Plan]
        Z --> D
    end

    subgraph "Storage Layer"
        O --> DB[(Supabase PostgreSQL)]
        T --> DB
        U --> DB
        W --> QD[(Qdrant<br/>Vector DB)]
        X --> MG[(Memgraph<br/>Knowledge Graph)]
    end

    style A fill:#e1f5ff
    style C fill:#fff4e6
    style D fill:#f3e5f5
    style O fill:#e8f5e9
    style V fill:#fff3e0
    style Z fill:#fce4ec
```

---

## 2. Correlation ID Flow

```mermaid
sequenceDiagram
    participant U as User
    participant UPS as UserPromptSubmit Hook
    participant PTU as PreToolUse Hook
    participant Agent as Agent Execution
    participant EP as Archon Endpoint
    participant DB as Database

    U->>UPS: Submit prompt
    activate UPS
    UPS->>UPS: Generate correlation_id<br/>session_id, root_id

    Note over UPS: correlation_id = UUID<br/>root_id = correlation_id<br/>session_id = Claude session

    UPS->>DB: Log trace start
    Note right of DB: execution_traces<br/>correlation_id: abc123<br/>root_id: abc123<br/>status: in_progress

    UPS->>PTU: Enhanced prompt<br/>+ correlation headers
    deactivate UPS

    activate PTU
    PTU->>PTU: Generate execution_id<br/>parent_id = correlation_id

    PTU->>DB: Log hook execution
    Note right of DB: hook_executions<br/>correlation_id: abc123<br/>execution_id: def456<br/>parent_id: abc123

    PTU->>EP: Call RAG endpoint<br/>X-Correlation-ID: abc123<br/>X-Execution-ID: def456
    activate EP

    EP->>EP: Extract correlation headers

    EP->>DB: Log endpoint call
    Note right of DB: endpoint_calls<br/>correlation_id: abc123<br/>hook_execution_id: def456

    EP-->>PTU: Response
    deactivate EP

    PTU->>Agent: Enhanced tool call<br/>+ intelligence + correlation
    deactivate PTU

    activate Agent
    Agent->>DB: Update trace status
    Note right of DB: execution_traces<br/>correlation_id: abc123<br/>status: success
    deactivate Agent
```

---

## 3. Pattern Learning Workflow

```mermaid
flowchart TD
    A[Execution Completes] --> B{Success?}

    B -->|No| C[Log Error Pattern]
    B -->|Yes| D[Evaluate Success Criteria]

    D --> E{All Criteria Met?}
    E -->|No| C
    E -->|Yes| F[Extract Pattern]

    F --> G[Generate Prompt Embedding]
    F --> H[Extract Keywords]
    F --> I[Classify Intent]
    F --> J[Extract Execution Path]

    G --> K[Store in success_patterns]
    H --> K
    I --> K
    J --> K

    K --> L[Index in Qdrant]
    K --> M[Update Knowledge Graph]

    L --> N[Pattern Available for Matching]
    M --> N

    style D fill:#e8f5e9
    style F fill:#fff9c4
    style K fill:#e1f5fe
    style N fill:#f3e5f5
```

---

## 4. Pattern Matching Flow

```mermaid
flowchart TD
    A[New User Request] --> B[Generate Request Embedding]

    B --> C[Vector Search in Qdrant]
    C --> D[Get Top 10 Candidates]

    D --> E[Multi-Dimensional Scoring]

    E --> F[Semantic Similarity<br/>40% weight]
    E --> G[Keyword Overlap<br/>20% weight]
    E --> H[Intent Match<br/>20% weight]
    E --> I[Context Fit<br/>10% weight]
    E --> J[Historical Success<br/>10% weight]

    F --> K[Calculate Total Score]
    G --> K
    H --> K
    I --> K
    J --> K

    K --> L{Score >= 0.85?}

    L -->|Yes| M[Use Learned Pattern]
    L -->|No| N{Score >= 0.75?}

    N -->|Yes| O[Suggest Pattern<br/>with Normal Routing]
    N -->|No| P[Normal Routing Only]

    M --> Q[Generate Replay Plan]
    Q --> R[Route to Agent]

    style B fill:#fff9c4
    style C fill:#e1f5fe
    style E fill:#f3e5f5
    style M fill:#c8e6c9
    style P fill:#ffccbc
```

---

## 5. Pattern Replay Architecture

```mermaid
graph TB
    subgraph "Replay Plan Components"
        A[Learned Pattern] --> B[Agent Selection]
        A --> C[Hook Execution Plan]
        A --> D[Intelligence Plan]
        A --> E[Endpoint Expectations]
        A --> F[Performance Expectations]
    end

    subgraph "Execution with Replay"
        B --> G[Route to Specific Agent]
        C --> H[Execute Hooks in Order]
        D --> I[Run Intelligence Queries]
        E --> J[Call Expected Endpoints]

        H --> K{Hook Successful?}
        I --> L{Intelligence Gathered?}
        J --> M{Endpoint Success?}

        K -->|No| N[Track Deviation]
        L -->|No| N
        M -->|No| N

        K -->|Yes| O[Continue Execution]
        L -->|Yes| O
        M -->|Yes| O
    end

    subgraph "Outcome Tracking"
        O --> P{Execution Complete?}
        P -->|Yes| Q[Compare vs Expectations]
        N --> Q

        Q --> R[Update Pattern Success Rate]
        R --> S{Success Rate < 0.7?}

        S -->|Yes| T[Mark Pattern Low Confidence]
        S -->|No| U[Keep Pattern Active]
    end

    F --> Q

    style A fill:#fff3e0
    style G fill:#e8f5e9
    style N fill:#ffcdd2
    style R fill:#c5cae9
    style T fill:#ffab91
```

---

## 6. Database Schema Relationships

```mermaid
erDiagram
    EXECUTION_TRACES ||--o{ AGENT_ROUTING_DECISIONS : has
    EXECUTION_TRACES ||--o{ HOOK_EXECUTIONS : contains
    EXECUTION_TRACES ||--o{ ENDPOINT_CALLS : logs
    EXECUTION_TRACES ||--o| SUCCESS_PATTERNS : generates

    HOOK_EXECUTIONS ||--o{ ENDPOINT_CALLS : triggers

    SUCCESS_PATTERNS ||--o{ PATTERN_USAGE_LOG : tracked_by
    EXECUTION_TRACES ||--o{ PATTERN_USAGE_LOG : uses

    AGENT_ROUTING_DECISIONS }o--|| SUCCESS_PATTERNS : uses_pattern

    EXECUTION_TRACES {
        uuid correlation_id PK
        uuid root_id FK
        uuid parent_id FK
        uuid session_id
        text prompt_text
        text status
        boolean success
        timestamptz started_at
        timestamptz completed_at
    }

    AGENT_ROUTING_DECISIONS {
        uuid id PK
        uuid correlation_id FK
        text selected_agent
        float confidence_total
        text routing_strategy
        uuid pattern_id FK
    }

    HOOK_EXECUTIONS {
        uuid id PK
        uuid execution_id
        uuid correlation_id FK
        text hook_type
        text tool_name
        integer duration_ms
        boolean success
    }

    ENDPOINT_CALLS {
        uuid id PK
        uuid correlation_id FK
        uuid hook_execution_id FK
        text endpoint_path
        jsonb request_body
        jsonb response_body
        integer duration_ms
        boolean success
    }

    SUCCESS_PATTERNS {
        uuid pattern_id PK
        uuid source_correlation_id FK
        text prompt_text
        vector prompt_embedding
        text intent
        jsonb hook_sequence
        jsonb endpoint_pattern
        float success_rate
        integer usage_count
    }

    PATTERN_USAGE_LOG {
        uuid id PK
        uuid pattern_id FK
        uuid correlation_id FK
        float match_score
        boolean success
        jsonb deviations
    }
```

---

## 7. Analytics Dashboard Architecture

```mermaid
graph TB
    subgraph "Data Sources"
        A[(execution_traces)]
        B[(agent_routing_decisions)]
        C[(hook_executions)]
        D[(endpoint_calls)]
        E[(success_patterns)]
        F[(pattern_usage_log)]
    end

    subgraph "Analytics Views"
        A --> G[agent_success_rates]
        B --> G
        A --> H[hook_performance_summary]
        C --> H
        D --> I[endpoint_reliability]
        E --> J[pattern_effectiveness]
        F --> J
    end

    subgraph "Dashboard UI"
        G --> K[Agent Performance Widget]
        H --> L[Hook Performance Widget]
        I --> M[Endpoint Health Widget]
        J --> N[Pattern Success Widget]

        K --> O[Real-time Dashboard]
        L --> O
        M --> O
        N --> O

        O --> P[Drill-down Views]
        P --> Q[Trace Timeline]
        P --> R[Pattern Details]
        P --> S[Error Analysis]
    end

    subgraph "Alerts & Notifications"
        G --> T{Success Rate < 80%?}
        H --> U{Duration > Threshold?}
        I --> V{Error Rate > 5%?}
        J --> W{Pattern Success < 70%?}

        T -->|Yes| X[Alert Team]
        U -->|Yes| X
        V -->|Yes| X
        W -->|Yes| X
    end

    style O fill:#e8f5e9
    style X fill:#ffcdd2
```

---

## 8. Performance Optimization Strategy

```mermaid
flowchart TD
    A[Performance Monitoring] --> B{Latency > Target?}

    B -->|Trace Logging| C[Async Non-blocking<br/>Fire & Forget]
    B -->|Pattern Matching| D[Implement Caching<br/>TTL 1 hour]
    B -->|Database Queries| E[Add Indexes<br/>Connection Pooling]
    B -->|Pattern Extraction| F[Batch Processing<br/>Every 5 minutes]

    C --> G[Target: <5ms]
    D --> H[Target: <100ms]
    E --> I[Target: <20ms]
    F --> J[Target: <30s per batch]

    G --> K[Monitor & Adjust]
    H --> K
    I --> K
    J --> K

    K --> L{Targets Met?}
    L -->|No| M[Scale Resources]
    L -->|Yes| N[Continue Monitoring]

    M --> O[Horizontal Scaling]
    M --> P[Vertical Scaling]
    M --> Q[Optimize Algorithms]

    O --> K
    P --> K
    Q --> K

    style G fill:#c8e6c9
    style H fill:#c8e6c9
    style I fill:#c8e6c9
    style J fill:#c8e6c9
    style M fill:#fff9c4
```

---

## 9. Deployment Architecture

```mermaid
graph TB
    subgraph "Development"
        A[Local Machine] --> B[Dev Supabase]
        A --> C[Local Qdrant]
        A --> D[Local Memgraph]
    end

    subgraph "Staging"
        E[Staging Hooks] --> F[Staging Intelligence Service]
        F --> G[Staging Supabase]
        F --> H[Staging Qdrant]
        F --> I[Staging Memgraph]
    end

    subgraph "Production"
        J[Prod Hooks] --> K[Prod Intelligence Service]
        K --> L[Prod Supabase Primary]
        L --> M[Supabase Replica]

        K --> N[Prod Qdrant Cluster]
        N --> N1[Qdrant Node 1]
        N --> N2[Qdrant Node 2]

        K --> O[Prod Memgraph Cluster]
        O --> O1[Memgraph Node 1]
        O --> O2[Memgraph Node 2]
    end

    subgraph "Monitoring"
        P[Prometheus] --> Q[Grafana]
        K -.->|Metrics| P
        L -.->|Metrics| P
        N -.->|Metrics| P
        O -.->|Metrics| P
    end

    subgraph "Alerting"
        P --> R{Threshold<br/>Breached?}
        R -->|Yes| S[PagerDuty]
        R -->|Yes| T[Slack]
    end

    style J fill:#e8f5e9
    style K fill:#e8f5e9
    style L fill:#e8f5e9
    style S fill:#ffcdd2
```

---

## 10. Error Handling & Recovery

```mermaid
flowchart TD
    A[Error Detected] --> B{Error Type}

    B -->|Trace Logging Failed| C[Log to Local File]
    B -->|Database Connection| D[Retry with Backoff]
    B -->|Pattern Matching Failed| E[Fall Back to Normal Routing]
    B -->|Pattern Replay Failed| F[Disable Pattern & Retry]
    B -->|Endpoint Timeout| G[Circuit Breaker]

    C --> H[Alert Monitoring Team]
    D --> I{Max Retries?}
    E --> J[Log Pattern Failure]
    F --> K[Mark Pattern Low Confidence]
    G --> L[Activate Fallback]

    I -->|Yes| M[Alert Database Team]
    I -->|No| N[Continue]

    H --> O[Continue Without Tracing]
    J --> P[Route Normally]
    K --> Q[Update Pattern Stats]
    L --> R[Use Cached Data]
    M --> S[Manual Intervention]

    O --> T[Execution Continues]
    P --> T
    Q --> T
    R --> T

    style A fill:#ffcdd2
    style O fill:#fff9c4
    style T fill:#c8e6c9
```

---

**Document Status**: Architecture Reference
**Last Updated**: 2025-10-01
