# Reflex Arc Architecture: Implementation Plan

## Executive Summary

Transform Claude Code hooks from reactive validators into an intelligent, self-improving system that prevents mistakes before they happen. Build incrementally on existing infrastructure (quality_enforcer.py, post_tool_use_enforcer.py, 49 agents, ONEX validators, Archon MCP) to create a three-layer architecture:

1. **Intent Dispatcher**: Pre-execution routing with ONEX rule injection
2. **Smart Triage**: Tiered post-execution validation with root cause analysis
3. **Mistake Memory**: Vector-based learning loop preventing repeated errors

**Total Timeline**: 6 weeks | **Target**: 70% mistake reduction, 50% faster validation

---

## Current State Assessment

### Assets
```
~/.claude/hooks/
├── quality_enforcer.py          # PreToolUse: naming validation + AI Quorum
├── post_tool_use_enforcer.py    # PostToolUse: auto-fix capabilities
├── config.yaml                   # Hook configuration
└── lib/
    ├── consensus/quorum.py       # AI consensus system
    └── validators/               # Validation components

~/.claude/agents/configs/         # 49 specialized agents
omnibase_core/validation/         # 13 ONEX validation scripts
Archon MCP                        # Quality assessment tools (8053)
```

### Gaps
- No pre-execution agent routing
- No mistake pattern detection
- No learning from past failures
- Limited root cause analysis
- No ONEX rule injection at intent stage

---

## Phase 1 (Weeks 1-2): Foundation & Quick Wins

### Goal
Build Intent Dispatcher foundation and mistake tracking infrastructure for immediate impact.

### Deliverables

#### 1.1 Intent Classification System (Days 1-3)
**File**: `~/.claude/hooks/lib/dispatcher/intent_classifier.py`

```python
class IntentClassifier:
    """Classify tool use intent and extract ONEX-relevant patterns."""

    INTENT_PATTERNS = {
        'file_modification': {
            'triggers': ['Edit', 'Write', 'replace_'],
            'agents': ['agent-code-quality-analyzer', 'agent-onex-compliance'],
            'validators': ['naming_validator', 'structure_validator']
        },
        'api_design': {
            'triggers': ['create.*api', 'endpoint', 'route'],
            'agents': ['agent-api-architect', 'agent-python-fastapi-expert'],
            'validators': ['api_compliance_validator', 'parameter_validator']
        },
        'test_creation': {
            'triggers': ['test_', 'spec', 'pytest'],
            'agents': ['agent-testing', 'agent-onex-test-generator'],
            'validators': ['test_coverage_validator']
        }
        # Add 8-10 common intent patterns
    }

    def classify(self, tool_name: str, arguments: dict) -> IntentContext:
        """Classify intent and return routing context."""
        pass
```

**Integration**: Modify `quality_enforcer.py` to call classifier before validation.

**Success Metric**: 85%+ intent classification accuracy on common patterns.

#### 1.2 Mistake Memory Store (Days 4-7)
**File**: `~/.claude/hooks/lib/memory/mistake_store.py`

```python
from qdrant_client import QdrantClient
from datetime import datetime

class MistakeMemory:
    """Vector store for capturing and retrieving past mistakes."""

    def __init__(self, qdrant_url: str = "http://localhost:6333"):
        self.client = QdrantClient(url=qdrant_url)
        self.collection = "claude_mistakes"

    def record_mistake(self,
                      tool_name: str,
                      arguments: dict,
                      error_message: str,
                      root_cause: str,
                      fix_applied: str,
                      context: dict):
        """Record a mistake with embeddings for similarity search."""
        embedding = self._generate_embedding({
            'tool': tool_name,
            'error': error_message,
            'root_cause': root_cause
        })

        self.client.upsert(
            collection_name=self.collection,
            points=[{
                'id': str(uuid.uuid4()),
                'vector': embedding,
                'payload': {
                    'timestamp': datetime.utcnow().isoformat(),
                    'tool_name': tool_name,
                    'error_message': error_message,
                    'root_cause': root_cause,
                    'fix_applied': fix_applied,
                    'context': context
                }
            }]
        )

    def find_similar_mistakes(self, current_intent: dict, limit: int = 5):
        """Find similar past mistakes to prevent repetition."""
        query_embedding = self._generate_embedding(current_intent)

        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_embedding,
            limit=limit,
            score_threshold=0.8
        )

        return [hit.payload for hit in results]
```

**Storage**: Use local Qdrant instance (reuse Archon's if available) or SQLite fallback.

**Success Metric**: Store captures 100% of validation failures with searchable context.

#### 1.3 Enhanced Intent Dispatcher (Days 8-10)
**File**: `~/.claude/hooks/lib/dispatcher/intent_dispatcher.py`

```python
class IntentDispatcher:
    """Pre-execution routing with ONEX rule injection and mistake prevention."""

    def __init__(self):
        self.classifier = IntentClassifier()
        self.memory = MistakeMemory()
        self.agent_registry = self._load_agent_registry()

    def dispatch(self, tool_name: str, arguments: dict) -> DispatchResult:
        """Route intent to optimal validation path."""

        # 1. Classify intent
        intent = self.classifier.classify(tool_name, arguments)

        # 2. Check for similar past mistakes
        similar_mistakes = self.memory.find_similar_mistakes(intent.to_dict())

        if similar_mistakes:
            # Inject preventive guidance
            return DispatchResult(
                proceed=True,
                warnings=[f"Similar past mistake detected: {m['error_message']}"
                         for m in similar_mistakes[:2]],
                suggested_agents=intent.agents,
                onex_rules=self._get_onex_rules(intent),
                preventive_guidance=self._generate_guidance(similar_mistakes)
            )

        # 3. Route to optimal agents
        return DispatchResult(
            proceed=True,
            suggested_agents=intent.agents,
            onex_rules=self._get_onex_rules(intent),
            validators=intent.validators
        )

    def _get_onex_rules(self, intent: IntentContext) -> list[str]:
        """Inject relevant ONEX rules based on intent."""
        # Map intent to specific ONEX validation rules
        pass
```

**Integration**: Replace simple validation in `quality_enforcer.py` with dispatcher call.

**Success Metric**: 90% of tool uses get relevant agent suggestions and ONEX rules.

#### 1.4 Integration with Existing Hooks (Days 11-14)

**File**: `~/.claude/hooks/quality_enforcer.py` (enhanced)

```python
from lib.dispatcher.intent_dispatcher import IntentDispatcher

class EnhancedQualityEnforcer:
    """Enhanced pre-tool-use hook with intent dispatching."""

    def __init__(self):
        self.dispatcher = IntentDispatcher()
        self.naming_validator = NamingValidator()  # Existing
        self.quorum = AIQuorum()  # Existing

    def pre_tool_use(self, tool_name: str, arguments: dict) -> HookResult:
        """Enhanced pre-execution validation."""

        # 1. Dispatch intent (new)
        dispatch = self.dispatcher.dispatch(tool_name, arguments)

        if dispatch.warnings:
            # Show warnings but allow to proceed
            logger.warning("Preventive guidance: %s", dispatch.warnings)

        # 2. Apply ONEX rules (new)
        if dispatch.onex_rules:
            for rule in dispatch.onex_rules:
                self._inject_onex_guidance(arguments, rule)

        # 3. Run existing validations (keep)
        if self._should_validate_naming(tool_name):
            naming_result = self.naming_validator.validate(arguments)
            if not naming_result.passed:
                return HookResult(allow=False, message=naming_result.error)

        # 4. AI Quorum for critical changes (keep, but route to suggested agents)
        if dispatch.suggested_agents and self._is_critical_change(tool_name, arguments):
            quorum_result = self.quorum.validate(
                tool_name, arguments,
                preferred_agents=dispatch.suggested_agents
            )
            return HookResult(
                allow=quorum_result.approved,
                message=quorum_result.reasoning
            )

        return HookResult(allow=True)
```

**Success Metric**: Hooks work seamlessly with 0 regressions, add <50ms latency.

---

## Phase 2 (Weeks 3-4): Intelligence Layer

### Goal
Add smart triage with tiered validation and root cause analysis.

### Deliverables

#### 2.1 Tiered Validation Engine (Days 15-18)
**File**: `~/.claude/hooks/lib/triage/validation_engine.py`

```python
class TieredValidationEngine:
    """Multi-tier validation with intelligent escalation."""

    VALIDATION_TIERS = {
        'tier_1_fast': {
            'validators': ['syntax_check', 'basic_naming'],
            'timeout_ms': 50,
            'failure_escalates_to': 'tier_2_standard'
        },
        'tier_2_standard': {
            'validators': ['onex_compliance', 'structure_validation'],
            'timeout_ms': 200,
            'failure_escalates_to': 'tier_3_deep'
        },
        'tier_3_deep': {
            'validators': ['ai_code_review', 'security_scan'],
            'timeout_ms': 2000,
            'failure_escalates_to': 'tier_4_critical'
        },
        'tier_4_critical': {
            'validators': ['ai_quorum', 'archon_quality_assessment'],
            'timeout_ms': 5000,
            'failure_escalates_to': None  # Terminal
        }
    }

    async def validate(self, result: ToolResult, context: IntentContext) -> ValidationResult:
        """Run tiered validation with intelligent escalation."""

        current_tier = 'tier_1_fast'

        while current_tier:
            tier_config = self.VALIDATION_TIERS[current_tier]

            # Run validators in parallel
            validation_results = await asyncio.gather(*[
                self._run_validator(v, result, context)
                for v in tier_config['validators']
            ])

            # Check if all passed
            if all(r.passed for r in validation_results):
                return ValidationResult(
                    passed=True,
                    tier_reached=current_tier,
                    validation_time_ms=sum(r.duration_ms for r in validation_results)
                )

            # Escalate if failures detected
            if tier_config['failure_escalates_to']:
                logger.info(f"Escalating from {current_tier} to {tier_config['failure_escalates_to']}")
                current_tier = tier_config['failure_escalates_to']
            else:
                # Terminal tier failed
                return ValidationResult(
                    passed=False,
                    tier_reached=current_tier,
                    failures=[r for r in validation_results if not r.passed]
                )
```

**Success Metric**: 80% of validations complete in Tier 1-2, <5% reach Tier 4.

#### 2.2 Root Cause Analyzer (Days 19-22)
**File**: `~/.claude/hooks/lib/triage/root_cause_analyzer.py`

```python
class RootCauseAnalyzer:
    """Intelligent root cause analysis using Archon MCP and local heuristics."""

    def __init__(self):
        self.archon_client = httpx.AsyncClient(base_url="http://localhost:8053")
        self.pattern_matcher = PatternMatcher()

    async def analyze(self,
                     validation_failure: ValidationFailure,
                     tool_result: ToolResult,
                     context: IntentContext) -> RootCause:
        """Multi-dimensional root cause analysis."""

        # 1. Pattern matching (fast, local)
        local_patterns = self.pattern_matcher.find_patterns(
            validation_failure.error_message,
            tool_result.content
        )

        if local_patterns and local_patterns.confidence > 0.8:
            return RootCause(
                category=local_patterns.category,
                description=local_patterns.description,
                confidence=local_patterns.confidence,
                fix_suggestions=local_patterns.fixes,
                source='local_patterns'
            )

        # 2. Archon MCP intelligence (slower, higher accuracy)
        try:
            archon_analysis = await self.archon_client.post(
                "/assess/code",
                json={
                    'content': tool_result.content,
                    'error_context': validation_failure.error_message,
                    'language': context.language
                },
                timeout=2.0
            )

            if archon_analysis.status_code == 200:
                data = archon_analysis.json()
                return RootCause(
                    category=data['root_cause']['category'],
                    description=data['root_cause']['description'],
                    confidence=data['confidence_score'],
                    fix_suggestions=data['recommendations'],
                    source='archon_intelligence'
                )
        except Exception as e:
            logger.warning(f"Archon analysis failed: {e}")

        # 3. Fallback to heuristics
        return self._heuristic_analysis(validation_failure, tool_result)
```

**Integration**: Use Archon MCP quality assessment tools (port 8053) when available.

**Success Metric**: Root cause identification accuracy >75%, response time <2s.

#### 2.3 Smart Auto-Fix Engine (Days 23-26)
**File**: `~/.claude/hooks/lib/triage/auto_fix_engine.py`

```python
class SmartAutoFixEngine:
    """Intelligent auto-fix with safety checks and rollback."""

    def __init__(self):
        self.root_cause_analyzer = RootCauseAnalyzer()
        self.mistake_memory = MistakeMemory()
        self.fix_strategies = self._load_fix_strategies()

    async def attempt_fix(self,
                         validation_failure: ValidationFailure,
                         tool_result: ToolResult,
                         context: IntentContext) -> FixResult:
        """Attempt intelligent auto-fix with safety checks."""

        # 1. Analyze root cause
        root_cause = await self.root_cause_analyzer.analyze(
            validation_failure, tool_result, context
        )

        # 2. Check if similar fix was successful before
        similar_fixes = self.mistake_memory.find_successful_fixes(
            root_cause.category,
            limit=3
        )

        if similar_fixes:
            # Apply previously successful fix strategy
            strategy = similar_fixes[0]['fix_strategy']
        else:
            # Select fix strategy based on root cause
            strategy = self._select_fix_strategy(root_cause)

        if not strategy or not strategy.is_safe:
            return FixResult(
                attempted=False,
                reason="No safe auto-fix available",
                root_cause=root_cause
            )

        # 3. Apply fix with rollback capability
        try:
            original_state = self._capture_state(tool_result)

            fixed_result = await strategy.apply(tool_result, root_cause)

            # 4. Validate fix
            validation = await self._validate_fix(fixed_result, context)

            if validation.passed:
                # Record successful fix
                self.mistake_memory.record_successful_fix(
                    root_cause=root_cause,
                    strategy=strategy.name,
                    result=fixed_result
                )

                return FixResult(
                    attempted=True,
                    successful=True,
                    fixed_result=fixed_result,
                    strategy_used=strategy.name
                )
            else:
                # Rollback
                self._restore_state(original_state)
                return FixResult(
                    attempted=True,
                    successful=False,
                    reason="Fix validation failed"
                )

        except Exception as e:
            logger.error(f"Auto-fix failed: {e}")
            self._restore_state(original_state)
            return FixResult(attempted=True, successful=False, reason=str(e))
```

**Safety**: Only auto-fix low-risk issues (naming, formatting, simple ONEX violations).

**Success Metric**: 60% of Tier 1-2 failures auto-fixed successfully, 0 false fixes.

#### 2.4 Enhanced PostToolUse Hook (Days 27-28)

**File**: `~/.claude/hooks/post_tool_use_enforcer.py` (enhanced)

```python
from lib.triage.validation_engine import TieredValidationEngine
from lib.triage.auto_fix_engine import SmartAutoFixEngine

class SmartTriageEnforcer:
    """Enhanced post-tool-use hook with smart triage."""

    def __init__(self):
        self.validation_engine = TieredValidationEngine()
        self.auto_fix_engine = SmartAutoFixEngine()
        self.mistake_memory = MistakeMemory()

    async def post_tool_use(self,
                           tool_name: str,
                           arguments: dict,
                           result: ToolResult,
                           context: IntentContext) -> PostHookResult:
        """Smart triage with tiered validation and auto-fix."""

        # 1. Tiered validation
        validation = await self.validation_engine.validate(result, context)

        if validation.passed:
            logger.info(f"Validation passed at {validation.tier_reached} "
                       f"in {validation.validation_time_ms}ms")
            return PostHookResult(allow=True)

        # 2. Log validation failures
        logger.warning(f"Validation failed at {validation.tier_reached}: "
                      f"{validation.failures}")

        # 3. Attempt auto-fix
        fix_result = await self.auto_fix_engine.attempt_fix(
            validation.failures[0], result, context
        )

        if fix_result.successful:
            logger.info(f"Auto-fix successful using {fix_result.strategy_used}")
            return PostHookResult(
                allow=True,
                modified_result=fix_result.fixed_result,
                message="Auto-fixed validation issue"
            )

        # 4. Record mistake for learning
        self.mistake_memory.record_mistake(
            tool_name=tool_name,
            arguments=arguments,
            error_message=str(validation.failures),
            root_cause=fix_result.root_cause.description if fix_result.root_cause else "Unknown",
            fix_applied="None" if not fix_result.attempted else "Failed",
            context=context.to_dict()
        )

        # 5. Block or warn based on severity
        if validation.tier_reached == 'tier_4_critical':
            return PostHookResult(
                allow=False,
                message=f"Critical validation failure: {validation.failures}"
            )
        else:
            return PostHookResult(
                allow=True,
                warnings=validation.failures,
                message="Non-critical validation warnings"
            )
```

**Success Metric**: 50% reduction in validation failures reaching Tier 3-4.

---

## Phase 3 (Weeks 5-6): Learning & Adaptation

### Goal
Close the learning loop with pattern detection and adaptive rule evolution.

### Deliverables

#### 3.1 Mistake Pattern Detector (Days 29-32)
**File**: `~/.claude/hooks/lib/learning/pattern_detector.py`

```python
class MistakePatternDetector:
    """Detect recurring mistake patterns and suggest new rules."""

    def __init__(self):
        self.mistake_memory = MistakeMemory()
        self.clustering_threshold = 0.85

    async def detect_patterns(self, time_window_days: int = 7) -> list[MistakePattern]:
        """Analyze recent mistakes for recurring patterns."""

        # 1. Fetch recent mistakes
        recent_mistakes = await self.mistake_memory.get_recent(
            days=time_window_days,
            min_count=3  # Need at least 3 occurrences
        )

        # 2. Cluster by similarity
        clusters = self._cluster_mistakes(recent_mistakes)

        # 3. Extract patterns
        patterns = []
        for cluster in clusters:
            if len(cluster.mistakes) >= 3:  # Recurring pattern
                pattern = MistakePattern(
                    category=cluster.common_category,
                    frequency=len(cluster.mistakes),
                    root_causes=[m.root_cause for m in cluster.mistakes],
                    common_context=cluster.common_context,
                    suggested_rule=self._generate_rule_suggestion(cluster),
                    examples=cluster.mistakes[:3]
                )
                patterns.append(pattern)

        return sorted(patterns, key=lambda p: p.frequency, reverse=True)

    def _generate_rule_suggestion(self, cluster: MistakeCluster) -> dict:
        """Generate a new validation rule suggestion."""
        return {
            'rule_type': 'intent_validator',
            'triggers': cluster.common_triggers,
            'validation_logic': self._extract_validation_logic(cluster),
            'error_message_template': cluster.common_error_pattern,
            'auto_fixable': cluster.common_fix_success_rate > 0.8,
            'confidence': cluster.similarity_score
        }
```

**Success Metric**: Detect 80% of recurring patterns (3+ occurrences in 7 days).

#### 3.2 Adaptive Rule Generator (Days 33-36)
**File**: `~/.claude/hooks/lib/learning/rule_generator.py`

```python
class AdaptiveRuleGenerator:
    """Generate and propose new validation rules from patterns."""

    def __init__(self):
        self.pattern_detector = MistakePatternDetector()
        self.rule_evaluator = RuleEvaluator()

    async def generate_rules(self) -> list[ProposedRule]:
        """Generate new validation rules from detected patterns."""

        # 1. Detect patterns
        patterns = await self.pattern_detector.detect_patterns()

        # 2. Generate rule candidates
        candidates = []
        for pattern in patterns:
            rule = self._pattern_to_rule(pattern)

            # 3. Evaluate rule effectiveness
            evaluation = await self.rule_evaluator.evaluate(
                rule, pattern.examples
            )

            if evaluation.would_prevent_pct > 0.8:  # 80% prevention rate
                candidates.append(ProposedRule(
                    rule=rule,
                    pattern=pattern,
                    evaluation=evaluation,
                    status='pending_approval'
                ))

        return candidates

    def _pattern_to_rule(self, pattern: MistakePattern) -> ValidationRule:
        """Convert mistake pattern to validation rule."""

        if pattern.category == 'naming_violation':
            return NamingValidationRule(
                name=f"auto_generated_naming_{pattern.hash}",
                triggers=pattern.common_context['tool_patterns'],
                regex_pattern=self._extract_regex(pattern),
                error_message=pattern.suggested_rule['error_message_template']
            )

        elif pattern.category == 'onex_compliance':
            return ONEXValidationRule(
                name=f"auto_generated_onex_{pattern.hash}",
                triggers=pattern.common_context['intent_patterns'],
                validation_function=pattern.suggested_rule['validation_logic'],
                auto_fix_enabled=pattern.suggested_rule['auto_fixable']
            )

        # Add more rule types as needed
        return CustomValidationRule(pattern.suggested_rule)
```

**Approval Flow**: Generate rules → Human review → Activate on approval.

**Success Metric**: Generate 1-2 high-quality rules per week from patterns.

#### 3.3 Learning Dashboard (Days 37-40)
**File**: `~/.claude/hooks/lib/learning/dashboard.py`

```python
class LearningDashboard:
    """Visualize learning metrics and proposed rules."""

    def __init__(self):
        self.mistake_memory = MistakeMemory()
        self.rule_generator = AdaptiveRuleGenerator()

    async def generate_report(self) -> dict:
        """Generate learning system performance report."""

        return {
            'period': '7_days',
            'metrics': {
                'total_mistakes': await self._count_mistakes(),
                'auto_fixed': await self._count_auto_fixes(),
                'prevented_by_intent': await self._count_preventions(),
                'recurring_patterns': await self._count_patterns()
            },
            'patterns_detected': await self.rule_generator.generate_rules(),
            'top_root_causes': await self._get_top_root_causes(),
            'validation_tier_distribution': await self._get_tier_distribution(),
            'improvement_trend': await self._calculate_trend()
        }

    def export_metrics_for_archon(self) -> dict:
        """Export metrics in Archon-compatible format."""
        # Integration with Archon MCP monitoring
        pass
```

**Output**: Weekly markdown report + metrics for Archon dashboard.

**Success Metric**: Dashboard shows clear week-over-week improvement trends.

#### 3.4 Integration & Polish (Days 41-42)

- Add graceful degradation (system works even if Qdrant/Archon unavailable)
- Implement configuration hot-reload
- Add detailed logging and observability
- Create user documentation
- Performance tuning (target: <100ms total overhead)

---

## File Structure

```
~/.claude/hooks/
├── quality_enforcer.py                    # Enhanced PreToolUse hook
├── post_tool_use_enforcer.py             # Enhanced PostToolUse hook
├── config.yaml                            # Central configuration
├── requirements.txt                       # Python dependencies
│
├── lib/
│   ├── __init__.py
│   │
│   ├── dispatcher/                        # Phase 1: Intent Dispatcher
│   │   ├── __init__.py
│   │   ├── intent_classifier.py          # Intent classification
│   │   └── intent_dispatcher.py          # Pre-execution routing
│   │
│   ├── memory/                            # Phase 1: Mistake Memory
│   │   ├── __init__.py
│   │   ├── mistake_store.py              # Vector storage
│   │   └── embeddings.py                 # Embedding generation
│   │
│   ├── triage/                            # Phase 2: Smart Triage
│   │   ├── __init__.py
│   │   ├── validation_engine.py          # Tiered validation
│   │   ├── root_cause_analyzer.py        # RCA engine
│   │   └── auto_fix_engine.py            # Smart auto-fix
│   │
│   ├── learning/                          # Phase 3: Learning Loop
│   │   ├── __init__.py
│   │   ├── pattern_detector.py           # Pattern detection
│   │   ├── rule_generator.py             # Adaptive rules
│   │   └── dashboard.py                  # Metrics & reporting
│   │
│   ├── validators/                        # Existing validators (keep)
│   │   ├── naming_validator.py
│   │   ├── onex_validator.py
│   │   └── ...
│   │
│   ├── consensus/                         # Existing (keep)
│   │   └── quorum.py
│   │
│   └── integrations/                      # External service clients
│       ├── archon_client.py              # Archon MCP client
│       └── qdrant_client.py              # Qdrant vector DB
│
└── data/                                  # Local data storage
    ├── mistakes.db                        # SQLite fallback
    └── rules_pending_approval.json       # Proposed rules
```

---

## Key Integration Points

### 1. Archon MCP Integration
```python
# ~/.claude/hooks/lib/integrations/archon_client.py
class ArchonClient:
    """Client for Archon MCP quality assessment tools."""

    BASE_URL = "http://localhost:8053"  # Intelligence Service

    async def assess_code_quality(self, code: str, language: str):
        """Use Archon's quality assessment (Phase 5A)."""
        pass

    async def get_quality_patterns(self, code: str):
        """Get best practices and anti-patterns."""
        pass
```

**Used By**: RootCauseAnalyzer, AutoFixEngine

### 2. Agent Registry Integration
```python
# ~/.claude/hooks/lib/dispatcher/intent_dispatcher.py
class IntentDispatcher:
    def _load_agent_registry(self):
        """Load 49 agents from ~/.claude/agents/configs/"""
        return yaml.safe_load(
            open(Path.home() / '.claude/agents/configs/agent-registry.yaml')
        )
```

**Used By**: IntentClassifier, IntentDispatcher

### 3. ONEX Validator Integration
```python
# ~/.claude/hooks/lib/validators/onex_validator.py
class ONEXValidator:
    """Wrapper for omnibase_core validation scripts."""

    VALIDATOR_PATH = Path("~/Code/omnibase_core/validation")

    def run_validation(self, script_name: str, target: str):
        """Run ONEX validation script."""
        pass
```

**Used By**: TieredValidationEngine

### 4. Qdrant Vector Store
```python
# ~/.claude/hooks/lib/integrations/qdrant_client.py
QDRANT_CONFIG = {
    'url': os.getenv('QDRANT_URL', 'http://localhost:6333'),
    'collection': 'claude_mistakes',
    'embedding_model': 'text-embedding-3-small'
}
```

**Fallback**: SQLite FTS5 if Qdrant unavailable

---

## Success Metrics

### Phase 1 Metrics (Weeks 1-2)
- **Intent Classification Accuracy**: 85%+ on common patterns
- **Mistake Capture Rate**: 100% of validation failures stored
- **Dispatcher Latency**: <50ms added to PreToolUse
- **Similar Mistake Detection**: Find relevant past mistakes in <100ms

### Phase 2 Metrics (Weeks 3-4)
- **Tier Distribution**: 80% complete in Tier 1-2, <5% reach Tier 4
- **Root Cause Accuracy**: 75%+ correct identification
- **Auto-Fix Success Rate**: 60%+ successful fixes for Tier 1-2 failures
- **Validation Reduction**: 50% fewer failures reaching Tier 3-4

### Phase 3 Metrics (Weeks 5-6)
- **Pattern Detection**: 80%+ of recurring patterns (3+ occurrences) detected
- **Rule Quality**: Generated rules would prevent 80%+ of matched mistakes
- **Learning Velocity**: 1-2 high-quality rules generated per week
- **Overall Improvement**: 70% reduction in repeated mistakes

### System-Wide Metrics (Ongoing)
- **Total Overhead**: <100ms added to tool execution
- **Availability**: 99%+ uptime (graceful degradation)
- **False Positive Rate**: <5% incorrect validations
- **Developer Satisfaction**: Measured via feedback surveys

---

## Configuration

### Phase 1 Config
```yaml
# ~/.claude/hooks/config.yaml
reflex_arc:
  enabled: true

  intent_dispatcher:
    enabled: true
    classification_confidence_threshold: 0.7
    max_similar_mistakes: 5

  mistake_memory:
    enabled: true
    storage_backend: 'qdrant'  # or 'sqlite'
    qdrant_url: 'http://localhost:6333'
    embedding_model: 'text-embedding-3-small'
    retention_days: 90
```

### Phase 2 Config
```yaml
  smart_triage:
    enabled: true

    validation_tiers:
      tier_1_timeout_ms: 50
      tier_2_timeout_ms: 200
      tier_3_timeout_ms: 2000
      tier_4_timeout_ms: 5000

    auto_fix:
      enabled: true
      safe_categories: ['naming', 'formatting', 'simple_onex']
      max_attempts: 1

    root_cause_analysis:
      use_archon: true
      archon_url: 'http://localhost:8053'
      fallback_to_heuristics: true
```

### Phase 3 Config
```yaml
  learning:
    enabled: true

    pattern_detection:
      time_window_days: 7
      min_occurrences: 3
      clustering_threshold: 0.85

    rule_generation:
      enabled: true
      auto_approve: false  # Require human approval
      prevention_threshold: 0.8

    dashboard:
      report_schedule: 'weekly'
      export_to_archon: true
```

---

## Quick Start Checklist

### Week 1
- [ ] Day 1: Create `lib/dispatcher/intent_classifier.py`
- [ ] Day 2: Test intent classification on 20 common tool uses
- [ ] Day 3: Create `lib/memory/mistake_store.py`
- [ ] Day 4: Set up Qdrant collection or SQLite fallback
- [ ] Day 5: Create `lib/dispatcher/intent_dispatcher.py`
- [ ] Day 6: Integrate dispatcher into `quality_enforcer.py`
- [ ] Day 7: Test end-to-end PreToolUse flow

### Week 2
- [ ] Day 8: Test mistake storage on 10 validation failures
- [ ] Day 9: Test similar mistake retrieval
- [ ] Day 10: Performance testing (target <50ms overhead)
- [ ] Day 11: Bug fixes and refinements
- [ ] Day 12: Documentation for Phase 1
- [ ] Day 13: Phase 1 demo and validation
- [ ] Day 14: Phase 1 release preparation

### Weeks 3-4
Follow similar daily breakdown for Phase 2 deliverables.

### Weeks 5-6
Follow similar daily breakdown for Phase 3 deliverables.

---

## Risk Mitigation

### Technical Risks
1. **Qdrant Unavailable**: Fallback to SQLite FTS5
2. **Archon MCP Down**: Use local heuristics for RCA
3. **Performance Degradation**: Circuit breakers with <100ms timeout
4. **False Positives**: Confidence thresholds + human review for new rules

### Process Risks
1. **Scope Creep**: Strict phase boundaries, no Phase 2 work in Phase 1
2. **Integration Complexity**: Incremental integration, maintain existing behavior
3. **Adoption Resistance**: Clear metrics, weekly improvement reports

---

## Post-Launch Plan

### Weeks 7-8: Refinement
- Tune confidence thresholds based on real usage
- Add more intent patterns and validation rules
- Optimize performance hotspots
- Expand agent routing logic

### Weeks 9-12: Advanced Features
- Multi-project mistake pattern sharing
- Collaborative rule voting (team-wide)
- Integration with CI/CD pipelines
- Real-time mistake prevention dashboard
