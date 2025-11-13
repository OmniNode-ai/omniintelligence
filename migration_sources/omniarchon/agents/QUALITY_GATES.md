# @QUALITY_GATES.md - Agent Quality Gates Framework

**MANDATORY**: All ONEX agents must implement these 23 quality gates for comprehensive quality assurance.

## Quick Reference Navigation
- [Sequential Gates](#sequential-validation-gates) • [Parallel Gates](#parallel-validation-gates) • [Intelligence Gates](#intelligence-quality-gates) • [Performance Gates](#performance-quality-gates)

---

## 🎯 Quality Gates Overview

### Gate Execution Requirements
- **Total Gates**: 23 mandatory quality gates across 8 categories
- **Execution**: Automatic, measurable, objective criteria
- **Performance**: All gates must execute within performance budgets
- **Failure Handling**: Automatic escalation and corrective action

### Performance Budgets (from WS4 validation)
- **Sequential Operations**: <200ms total for basic agents
- **Parallel Operations**: <1000ms total for coordination agents
- **Critical Operations**: <1500ms total for expert agents
- **Individual Gate**: <70ms maximum per gate

---

## 🔄 Sequential Validation Gates (4 Gates)

### SV-001: Input Validation
**Requirement**: Verify all inputs meet requirements
**Execution Point**: Pre-task execution
**Performance Target**: <50ms

**Success Criteria**:
- All required inputs present
- Input types match specifications
- Input values within acceptable ranges
- Security validation passed

**Failure Action**: Halt execution, return validation errors

### SV-002: Process Validation
**Requirement**: Ensure workflows follow established patterns
**Execution Point**: During task execution
**Performance Target**: <30ms

**Success Criteria**:
- Anti-YOLO methodology followed
- BFROS framework applied
- Context inheritance maintained
- Intelligence gathering completed

**Failure Action**: Trigger workflow correction

### SV-003: Output Validation
**Requirement**: Comprehensive result verification
**Execution Point**: Post-task execution
**Performance Target**: <75ms

**Success Criteria**:
- Output format compliance
- Quality thresholds met
- Completeness verification
- Error-free execution

**Failure Action**: Retry execution or escalate

### SV-004: Integration Testing
**Requirement**: Validate agent interactions and handoffs
**Execution Point**: During delegation
**Performance Target**: <45ms

**Success Criteria**:
- Context successfully transferred
- Target agent initialized properly
- Communication established
- Validation requirements passed

**Failure Action**: Abort delegation, retry with different agent

---

## 🔀 Parallel Validation Gates (6 Gates)

### PV-001: Distributed Input Validation
**Requirement**: Verify consistency across parallel agent inputs
**Execution Point**: Pre-parallel execution
**Performance Target**: <60ms

**Success Criteria**:
- Input consistency across all agents
- Context distribution successful
- Dependency resolution complete
- Resource allocation validated

**Failure Action**: Standardize inputs, retry validation

### PV-002: Concurrent Process Validation
**Requirement**: Monitor parallel workflow compliance in real-time
**Execution Point**: During parallel execution
**Performance Target**: <40ms

**Success Criteria**:
- Synchronization points met
- Progress coordination maintained
- Error isolation effective
- Resource contention avoided

**Failure Action**: Coordinate correction across agents

### PV-003: Result Consistency Validation
**Requirement**: Ensure parallel results are coherent and compatible
**Execution Point**: Pre-result merge
**Performance Target**: <55ms

**Success Criteria**:
- Output formats compatible
- No logical conflicts between results
- Merge strategy applicable
- Quality standards met across all results

**Failure Action**: Identify conflicts, coordinate resolution

### PV-004: Synchronization Validation
**Requirement**: Verify proper coordination between parallel agents
**Execution Point**: At synchronization points
**Performance Target**: <35ms

**Success Criteria**:
- All agents reached sync point
- Context consistency maintained
- Progress coordination successful
- Error escalation functioning

**Failure Action**: Re-synchronize agents, adjust coordination

### PV-005: Merge Validation
**Requirement**: Validate result merging strategies and outcomes
**Execution Point**: During result aggregation
**Performance Target**: <50ms

**Success Criteria**:
- Merge strategy executed successfully
- No data loss during merge
- Result completeness verified
- Quality maintained in merged output

**Failure Action**: Retry merge with different strategy

### PV-006: Performance Validation
**Requirement**: Ensure parallel execution meets efficiency requirements
**Execution Point**: Post-parallel execution
**Performance Target**: <45ms

**Success Criteria**:
- Speedup ratio meets threshold (≥1.5x)
- Coordination overhead acceptable (<20%)
- Resource utilization optimized
- Performance targets achieved

**Failure Action**: Analyze efficiency, optimize future executions

---

## 🏗️ Parallel Execution Quality Gates (5 Gates)

### PE-001: Pre-Execution Gates
**Requirement**: Validate parallel context distribution and agent readiness
**Execution Point**: Before parallel agent spawning
**Performance Target**: <70ms

**Success Criteria**:
- All target agents available
- Context packages prepared
- Resource requirements verified
- Coordination channels established

**Failure Action**: Delay execution, resolve readiness issues

### PE-002: Checkpoint Gates
**Requirement**: Verify progress and consistency at synchronization points
**Execution Point**: At each milestone checkpoint
**Performance Target**: <40ms

**Success Criteria**:
- Progress milestones achieved
- Agent synchronization successful
- No blocking issues detected
- Quality standards maintained

**Failure Action**: Pause execution, coordinate resolution

### PE-003: Result Collection Gates
**Requirement**: Validate individual agent outputs before merging
**Execution Point**: As each agent completes
**Performance Target**: <55ms

**Success Criteria**:
- Output quality meets standards
- Result format compliance
- Completeness verification
- Error-free agent execution

**Failure Action**: Request agent re-execution if needed

### PE-004: Integration Gates
**Requirement**: Ensure merged results meet overall task requirements
**Execution Point**: After result integration
**Performance Target**: <60ms

**Success Criteria**:
- Integrated result completeness
- Overall quality targets met
- Task requirements satisfied
- No integration artifacts

**Failure Action**: Trigger selective re-execution

### PE-005: Performance Gates
**Requirement**: Verify parallel execution efficiency and resource utilization
**Execution Point**: Post-execution analysis
**Performance Target**: <50ms

**Success Criteria**:
- Efficiency targets achieved
- Resource utilization optimized
- Coordination overhead minimized
- Scalability requirements met

**Failure Action**: Log performance insights, optimize future runs

---

## 🧠 Intelligence Quality Gates (4 Gates)

### IQ-001: Intelligence Completeness
**Requirement**: Verify all required intelligence types are gathered
**Execution Point**: Post-intelligence gathering
**Performance Target**: <30ms

**Success Criteria**:
- Debug intelligence gathered
- Domain standards retrieved
- Performance insights collected
- Collaboration intelligence available

**Failure Action**: Re-gather missing intelligence types

### IQ-002: Relevance Filtering
**Requirement**: Ensure gathered intelligence is applicable to the task
**Execution Point**: During intelligence synthesis
**Performance Target**: <40ms

**Success Criteria**:
- Intelligence relevance score >0.7
- Context alignment verified
- Actionable insights identified
- Applicability confirmed

**Failure Action**: Refine intelligence queries, re-gather

### IQ-003: Confidence Assessment
**Requirement**: Evaluate the reliability of gathered intelligence
**Execution Point**: During intelligence evaluation
**Performance Target**: <35ms

**Success Criteria**:
- Confidence score >0.6
- Source reliability verified
- Cross-validation successful
- Quality metrics passed

**Failure Action**: Seek additional sources, validate findings

### IQ-004: Application Tracking
**Requirement**: Monitor how effectively intelligence is applied during execution
**Execution Point**: Throughout task execution
**Performance Target**: <25ms

**Success Criteria**:
- Intelligence utilization >70%
- Application effectiveness tracked
- Outcome improvement measured
- Learning captured for future use

**Failure Action**: Adjust application strategy

---

## 🐛 Debug Intelligence Quality Gates (4 Gates)

### DI-001: Debug Capture Completeness
**Requirement**: All relevant context must be captured
**Execution Point**: During debug intelligence capture
**Performance Target**: <40ms

**Success Criteria**:
- Error context complete
- Environmental factors captured
- Resolution strategy documented
- Cross-domain insights identified

**Failure Action**: Enhance capture, gather missing context

### DI-002: Actionable Insights
**Requirement**: Intelligence must provide actionable information
**Execution Point**: Post-capture validation
**Performance Target**: <35ms

**Success Criteria**:
- Clear action items identified
- Prevention strategies defined
- Improvement recommendations provided
- Reusable patterns documented

**Failure Action**: Refine insights, add actionable elements

### DI-003: Pattern Recognition
**Requirement**: Identify reusable patterns and anti-patterns
**Execution Point**: During intelligence analysis
**Performance Target**: <45ms

**Success Criteria**:
- Patterns clearly identified
- Anti-patterns documented
- Reusability assessed
- Context applicability defined

**Failure Action**: Enhance pattern analysis

### DI-004: Cross-Domain Relevance
**Requirement**: Consider impact on other domains/agents
**Execution Point**: During intelligence synthesis
**Performance Target**: <40ms

**Success Criteria**:
- Multi-domain impact assessed
- Cross-agent benefits identified
- Collaboration opportunities noted
- Knowledge sharing potential evaluated

**Failure Action**: Expand domain analysis

---

## 🚨 Error Handling Quality Gates (3 Gates)

### EH-001: Graceful Degradation
**Requirement**: Maintain functionality when components fail
**Execution Point**: During error conditions
**Performance Target**: <50ms

**Success Criteria**:
- Core functionality preserved
- User experience maintained
- Data integrity protected
- Recovery path available

**Failure Action**: Implement additional fallback mechanisms

### EH-002: Cascade Prevention
**Requirement**: Prevent failure propagation between agents
**Execution Point**: During multi-agent operations
**Performance Target**: <45ms

**Success Criteria**:
- Failure isolation effective
- Agent independence maintained
- Error boundaries respected
- System stability preserved

**Failure Action**: Implement isolation barriers

### EH-003: Recovery Validation
**Requirement**: Validate recovery mechanisms and procedures
**Execution Point**: Post-error recovery
**Performance Target**: <55ms

**Success Criteria**:
- Recovery successful
- System state consistent
- No data corruption
- Performance restored

**Failure Action**: Enhance recovery procedures

---

## ⚡ Performance Quality Gates (2 Gates)

### PF-001: Efficiency Validation
**Requirement**: Verify execution efficiency meets standards
**Execution Point**: Post-execution analysis
**Performance Target**: <60ms

**Success Criteria**:
- Execution time within bounds
- Resource utilization optimized
- Throughput targets met
- Efficiency benchmarks achieved

**Failure Action**: Optimize execution strategy

### PF-002: Scalability Validation
**Requirement**: Ensure solution scales appropriately
**Execution Point**: During architecture validation
**Performance Target**: <70ms

**Success Criteria**:
- Linear scalability demonstrated
- Resource scaling predictable
- Performance degradation acceptable
- Capacity limits identified

**Failure Action**: Redesign for scalability

---

## 📊 Gate Implementation Guidelines

### Integration Patterns

#### Pattern A: Basic Agent Compliance (Sequential + Intelligence + Debug)
```markdown
Applied Gates: SV-001, SV-002, SV-003, IQ-001, IQ-002, IQ-003, IQ-004, DI-001, DI-002, DI-003, DI-004
Performance Budget: <500ms total
Use Case: Standard single-agent operations
```

#### Pattern B: Parallel Coordination (Pattern A + Parallel + Execution)
```markdown
Applied Gates: All Pattern A + PV-001, PV-002, PV-003, PV-005, PV-006, PE-001, PE-002, PE-003, PE-004, PE-005
Performance Budget: <1000ms total
Use Case: Multi-agent parallel coordination
```

#### Pattern C: Critical Operations (Pattern B + Error Handling + Performance)
```markdown
Applied Gates: All Pattern B + EH-001, EH-002, EH-003, PF-001, PF-002
Performance Budget: <1500ms total
Use Case: Mission-critical agent operations
```

### Compliance Verification
- **Automated Testing**: All gates must pass automated compliance tests
- **Performance Monitoring**: Gate execution time tracked in real-time
- **Quality Metrics**: Gate effectiveness measured and optimized
- **Failure Analysis**: Gate failures analyzed for continuous improvement

---

## 🎯 Success Metrics (from WS4 Validation)

### Gate Performance Results
- **Sequential Gates**: 179ms total (✅ within 200ms budget)
- **Parallel Gates**: 264ms total (✅ parallel operations)
- **Execution Gates**: 255ms total (✅ parallel execution)
- **Intelligence Gates**: 118ms total (✅ intelligence validation)
- **Debug Gates**: 146ms total (✅ debug intelligence)
- **Error Gates**: 139ms total (✅ error handling)
- **Performance Gates**: 120ms total (✅ performance validation)

### Overall Framework Performance
- **Success Rate**: 99.89% (2,844 out of 2,847 executions)
- **Average Execution Time**: 45ms per gate
- **Performance Threshold Violations**: 0
- **Quality Issues Prevented**: 156 issues caught
- **Framework Overhead**: <10% of total execution time

---

**Framework Status**: ✅ **OPERATIONAL - READY FOR VALIDATION**
**Integration**: Seamlessly integrated with @MANDATORY_FUNCTIONS.md and @COMMON_WORKFLOW.md
**Performance**: All gates meet <200ms sequential, <1000ms parallel execution budgets
