"""
Architectural Decision Scenarios for Multi-Model Consensus

These fixtures provide realistic architectural decision scenarios
requiring AI Quorum validation.

Scenarios:
- Node type selection (Effect vs Compute vs Reducer)
- Contract design decisions
- Performance vs maintainability tradeoffs
- Scaling strategy decisions
"""

# ============================================================================
# SCENARIO 1: Node Type Selection
# ============================================================================

SCENARIO_NODE_TYPE_SELECTION = {
    "scenario_id": "node_type_001",
    "title": "Email Notification Service - Node Type Selection",
    "description": """
    Deciding the correct ONEX node type for an email notification service.

    The service needs to:
    - Send emails to external SMTP server
    - Format email templates
    - Track delivery status
    - Aggregate statistics

    Possible approaches:
    1. Single Effect node (everything in one place)
    2. Compute node for formatting + Effect node for sending
    3. Compute + Effect + Reducer (formatting + sending + stats)
    4. Orchestrator coordinating multiple nodes
    """,
    "code_proposal": '''
    class NodeEmailSenderEffect:
        """Proposal: Single Effect node for email sending."""

        async def execute_effect(self, contract: ModelContractEffect):
            # Format email (is this Compute?)
            formatted = self._format_email(contract.template, contract.data)

            # Send email (clearly Effect)
            result = await self._send_email(formatted)

            # Track stats (is this Reducer?)
            await self._update_statistics(result)

            return result
    ''',
    "question": "Should this be one Effect node or multiple specialized nodes?",
    "consensus_options": [
        {
            "option": "single_effect",
            "description": "One Effect node handling everything",
            "pros": ["Simple", "Fewer moving parts", "Easy to maintain"],
            "cons": ["Violates SRP", "Mixing concerns", "Hard to test"],
        },
        {
            "option": "compute_plus_effect",
            "description": "Compute for formatting + Effect for sending",
            "pros": ["Separation of concerns", "Testable formatting", "Reusable"],
            "cons": ["More complexity", "More nodes to manage"],
        },
        {
            "option": "full_onex",
            "description": "Compute + Effect + Reducer (formatting + sending + stats)",
            "pros": [
                "Perfect ONEX compliance",
                "Clear separation",
                "Highly testable",
            ],
            "cons": ["Most complex", "Most nodes", "Potential overkill"],
        },
        {
            "option": "orchestrator",
            "description": "Orchestrator coordinating specialized nodes",
            "pros": ["Clear workflow", "Dependency management", "Flexible"],
            "cons": ["Highest complexity", "Most infrastructure"],
        },
    ],
    "expected_consensus_threshold": 0.7,
    "model_weights": {
        "gemini-flash": 1.0,
        "codestral": 1.5,
        "deepseek-lite": 2.0,
        "llama-3.1": 1.2,
        "deepseek-full": 1.8,
    },
}


# ============================================================================
# SCENARIO 2: Contract Design Decision
# ============================================================================

SCENARIO_CONTRACT_DESIGN = {
    "scenario_id": "contract_001",
    "title": "API Gateway Contract - Design Decision",
    "description": """
    Designing a contract for an API Gateway node that routes requests
    to different backend services.

    Requirements:
    - Route based on URL path, method, headers
    - Support multiple routing strategies
    - Handle authentication
    - Rate limiting

    Question: Should routing logic be in contract or node implementation?
    """,
    "code_proposal_a": """
    # Option A: Rich contract with routing logic
    class ModelContractAPIGatewayOrchestrator(ModelContractBase):
        def __init__(self, name, version, description, routing_config):
            super().__init__(name, version, description, "orchestrator")
            self.routing_config = routing_config  # Complex routing rules

        def determine_route(self, request):
            # Routing logic in contract
            for rule in self.routing_config["rules"]:
                if self._matches_rule(request, rule):
                    return rule["target"]
            return self.routing_config["default"]

        def _matches_rule(self, request, rule):
            # Complex matching logic in contract
            pass
    """,
    "code_proposal_b": """
    # Option B: Thin contract, logic in node
    class ModelContractAPIGatewayOrchestrator(ModelContractBase):
        def __init__(self, name, version, description, routing_rules):
            super().__init__(name, version, description, "orchestrator")
            self.routing_rules = routing_rules  # Just data

    class NodeAPIGatewayOrchestrator:
        async def execute_orchestration(self, contract):
            # Routing logic in node implementation
            route = self._determine_route(request, contract.routing_rules)
            return await self._execute_route(route)
    """,
    "question": "Should contracts be data-only or contain business logic?",
    "consensus_options": [
        {
            "option": "rich_contract",
            "description": "Contract contains routing logic",
            "pros": ["Reusable logic", "Testable independently", "Type-safe"],
            "cons": ["Violates data/behavior separation", "Hard to serialize"],
        },
        {
            "option": "thin_contract",
            "description": "Contract is data-only, logic in node",
            "pros": ["Clean separation", "Easy to serialize", "ONEX pattern"],
            "cons": ["Logic tied to implementation", "Less reusable"],
        },
        {
            "option": "hybrid",
            "description": "Contract validates, node implements",
            "pros": ["Balance of concerns", "Validation in contract"],
            "cons": ["Split responsibility", "Potential confusion"],
        },
    ],
    "expected_consensus_threshold": 0.8,
}


# ============================================================================
# SCENARIO 3: Performance vs Maintainability
# ============================================================================

SCENARIO_PERFORMANCE_VS_MAINTAINABILITY = {
    "scenario_id": "tradeoff_001",
    "title": "Cache Layer - Performance vs Maintainability",
    "description": """
    Implementing a caching layer for frequently accessed data.

    High-performance approach: In-memory cache with manual invalidation
    Maintainable approach: Cache with TTL and automatic eviction

    Trade-offs to consider:
    - Performance: In-memory is 10x faster
    - Complexity: Manual invalidation is error-prone
    - Consistency: TTL can serve stale data
    - Scalability: In-memory doesn't scale across instances
    """,
    "code_proposal_fast": '''
    class NodeCacheManagerReducer:
        """High-performance in-memory cache."""

        def __init__(self):
            self._cache = {}  # Fast in-memory dict
            self._dependencies = {}  # Manual dependency tracking

        async def execute_reduction(self, contract):
            # Ultra-fast lookup
            if contract.cache_key in self._cache:
                return self._cache[contract.cache_key]

            # Manual invalidation (complex but fast)
            result = await self._fetch_fresh_data(contract)
            self._cache[contract.cache_key] = result
            self._track_dependencies(contract.cache_key, result)

            return result
    ''',
    "code_proposal_maintainable": '''
    class NodeCacheManagerReducer:
        """Maintainable cache with automatic management."""

        def __init__(self, redis_client):
            self.redis = redis_client  # Managed cache with TTL

        async def execute_reduction(self, contract):
            # Simple TTL-based cache
            cached = await self.redis.get(contract.cache_key)
            if cached:
                return cached

            # Automatic expiration (no manual invalidation)
            result = await self._fetch_fresh_data(contract)
            await self.redis.setex(
                contract.cache_key,
                contract.ttl_seconds or 300,
                result
            )

            return result
    ''',
    "question": "Prioritize performance or maintainability?",
    "consensus_options": [
        {
            "option": "high_performance",
            "description": "In-memory cache with manual invalidation",
            "metrics": {
                "latency_ms": 1,
                "complexity_score": 8,
                "maintainability_score": 4,
            },
        },
        {
            "option": "maintainable",
            "description": "Redis with automatic TTL",
            "metrics": {
                "latency_ms": 10,
                "complexity_score": 3,
                "maintainability_score": 9,
            },
        },
        {
            "option": "hybrid",
            "description": "L1 in-memory + L2 Redis cache",
            "metrics": {
                "latency_ms": 2,
                "complexity_score": 6,
                "maintainability_score": 7,
            },
        },
    ],
    "expected_consensus_threshold": 0.6,
    "context": "Production system with 100M requests/day",
}


# ============================================================================
# SCENARIO 4: Scaling Strategy
# ============================================================================

SCENARIO_SCALING_STRATEGY = {
    "scenario_id": "scaling_001",
    "title": "Event Processing - Horizontal vs Vertical Scaling",
    "description": """
    Event processing system handling 10K events/second with spikes to 50K.

    Current: Single Reducer node aggregating all events
    Problem: CPU bottleneck at peak load

    Scaling options:
    1. Vertical: Bigger machine, optimize algorithm
    2. Horizontal: Partition events across multiple Reducer nodes
    3. Hybrid: Partition + local aggregation + final merge
    """,
    "code_proposal_vertical": '''
    class NodeEventAggregatorReducer:
        """Optimized single-node reducer."""

        async def execute_reduction(self, contract):
            # Highly optimized single-threaded aggregation
            # Use efficient data structures, batch processing
            # Requires 32-core CPU, 64GB RAM

            async with self._lock:  # Single node, need locking
                state = await self._load_state_optimized(contract.state_key)
                updated = self._fast_aggregate(state, contract.events)
                await self._persist_state_batch(contract.state_key, updated)

            return updated
    ''',
    "code_proposal_horizontal": '''
    # Partition coordinator
    class NodeEventPartitionerOrchestrator:
        """Distribute events across partitions."""

        async def execute_orchestration(self, contract):
            # Partition events by key
            partitions = self._partition_events(contract.events)

            # Process partitions in parallel
            results = await asyncio.gather(*[
                self._process_partition(partition_id, events)
                for partition_id, events in partitions.items()
            ])

            # Final merge if needed
            return self._merge_results(results)

    # Each partition handled by separate Reducer
    class NodePartitionReducer:
        """Handle single partition."""

        async def execute_reduction(self, contract):
            # No cross-partition locking needed
            state = await self._load_partition_state(contract.partition_id)
            updated = self._aggregate_partition(state, contract.events)
            await self._persist_partition_state(contract.partition_id, updated)

            return updated
    ''',
    "question": "How should we scale this event processing system?",
    "consensus_options": [
        {
            "option": "vertical",
            "description": "Optimize and scale single node",
            "capacity": "15K events/second",
            "cost_monthly": 500,
            "complexity": "Low",
            "single_point_of_failure": True,
        },
        {
            "option": "horizontal",
            "description": "Partition across multiple nodes",
            "capacity": "100K+ events/second",
            "cost_monthly": 800,
            "complexity": "High",
            "single_point_of_failure": False,
        },
        {
            "option": "hybrid",
            "description": "Partition + optimized reducers",
            "capacity": "200K+ events/second",
            "cost_monthly": 1200,
            "complexity": "Medium",
            "single_point_of_failure": False,
        },
    ],
    "expected_consensus_threshold": 0.75,
    "current_load": "10K events/sec avg, 50K peak",
}


# ============================================================================
# All Scenarios
# ============================================================================

ALL_SCENARIOS = [
    SCENARIO_NODE_TYPE_SELECTION,
    SCENARIO_CONTRACT_DESIGN,
    SCENARIO_PERFORMANCE_VS_MAINTAINABILITY,
    SCENARIO_SCALING_STRATEGY,
]
