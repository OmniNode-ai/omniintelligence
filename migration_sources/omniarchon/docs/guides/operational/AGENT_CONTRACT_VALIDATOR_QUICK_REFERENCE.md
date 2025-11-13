# Agent Contract Validator - Quick Reference

## Activation Triggers

Use any of these to activate the agent:

```
validate contract
check contract
verify contract compliance
assess contract quality
validate contract with intelligence
check ONEX contract compliance
intelligent contract validation
contract quality assessment
```

## Basic Usage

### Simple Validation
```
@agent-contract-validator validate this contract
```

### With Intelligence
```
@agent-contract-validator perform intelligent validation on this contract
```

### Compliance Check
```
@agent-contract-validator check ONEX compliance for this contract
```

## Validation Output

### Comprehensive Report Includes:
- **Contract Quality Score**: 0.0-1.0 rating
- **ONEX Compliance**: Percentage (0-100%)
- **Completeness**: Percentage (0-100%)
- **Anti-Patterns**: List with severity levels
- **Missing Required Fields**: Specific field list
- **Implementation Feasibility**: High/Medium/Low
- **Improvement Suggestions**: Prioritized action items
- **Similar Successful Contracts**: Historical reference count

## Node Type Specific Validation

### Effect Node Requirements
- ✅ External I/O contracts required
- ✅ Error handling specified
- ✅ Timeout configuration
- ✅ Retry strategy defined
- ✅ Idempotency guaranteed

### Compute Node Requirements
- ✅ Pure function guarantee
- ✅ Clear input/output types
- ✅ Complexity bounds specified
- ✅ Test coverage expectations

### Reducer Node Requirements
- ✅ Clear state transition rules
- ✅ Aggregation logic specified
- ✅ Persistence strategy defined
- ✅ Consistency guarantees

### Orchestrator Node Requirements
- ✅ Complete dependency graph
- ✅ Clear coordination strategy
- ✅ Specified failure handling
- ✅ Defined workflow steps

## Success Criteria

Validation passes when:
- ✅ Contract quality ≥ 0.7
- ✅ ONEX compliance ≥ 70%
- ✅ Completeness ≥ 80%
- ✅ Zero critical anti-patterns
- ✅ All required fields present
- ✅ Implementation feasibility: High/Medium

## Common Anti-Patterns Detected

1. **Missing error handling** - No error handling strategy
2. **Vague descriptions** - Unclear contract purpose
3. **Missing validation rules** - No input validation
4. **Incomplete schemas** - Missing required schema fields
5. **Side effects in Compute** - Impure functions
6. **Missing idempotency** - No idempotency guarantee in Effects
7. **Unclear state transitions** - Undefined state changes

## Example Workflow

### Step 1: Initial Validation
```
@agent-contract-validator validate this contract
```

### Step 2: Review Report
Check:
- Quality score
- Compliance percentage
- Anti-patterns list
- Missing fields

### Step 3: Apply Improvements
Follow prioritized suggestions:
1. Add missing required fields
2. Fix critical anti-patterns
3. Improve descriptions
4. Add validation rules
5. Enhance error handling

### Step 4: Re-Validate
```
@agent-contract-validator re-validate updated contract
```

## Intelligence Features

### Historical Pattern Learning
Agent automatically:
- Queries successful contract patterns
- Learns required fields per node type
- Identifies effective validation rules
- Recognizes common issues
- Tracks implementation success

### Quality Assessment
Agent evaluates:
- Contract structure and syntax
- ONEX architecture compliance
- Completeness of specifications
- Anti-pattern presence
- Implementation feasibility

### Automated Suggestions
When quality < 0.7, agent provides:
- Specific field additions needed
- Anti-pattern fixes
- Description improvements
- Validation rule additions
- Error handling enhancements

## Integration Points

### Phase 4 Traceability
- Queries historical patterns: `/api/pattern-traceability/lineage/query`
- Tracks validation outcomes for learning
- Correlates with implementation success

### Intelligence Service
- Quality assessment: `assess_code_quality()`
- Compliance checking: `check_architectural_compliance()`
- Document analysis: `analyze_document_quality()`
- Pattern detection: `get_quality_patterns()`

## Tips for Best Results

1. **Provide Complete Context**
   - Include full contract definition
   - Specify node type clearly
   - Include related subcontracts

2. **Use Intelligence Features**
   - Request "intelligent validation"
   - Ask for historical patterns
   - Request improvement suggestions

3. **Iterate Based on Feedback**
   - Address critical issues first
   - Follow prioritized suggestions
   - Re-validate after changes

4. **Learn from History**
   - Request similar successful contracts
   - Review common patterns
   - Apply proven practices

## Quick Commands

```bash
# Basic validation
"validate this contract"

# Quality assessment
"assess contract quality with intelligence"

# ONEX compliance
"check ONEX compliance score"

# Full intelligence validation
"perform comprehensive intelligent validation"

# Get improvement suggestions
"analyze contract and suggest improvements"

# Compare with successful patterns
"validate against historical successful contracts"
```

## Scoring Reference

### Quality Score (0.0-1.0)
- **0.9-1.0**: Excellent
- **0.7-0.9**: Good
- **0.5-0.7**: Needs improvement
- **<0.5**: Major issues

### ONEX Compliance (0-100%)
- **90-100%**: Excellent
- **70-90%**: Good
- **50-70%**: Needs improvement
- **<50%**: Non-compliant

### Completeness (0-100%)
- **90-100%**: Complete
- **80-90%**: Mostly complete
- **60-80%**: Partially complete
- **<60%**: Incomplete

### Implementation Feasibility
- **High**: Clear requirements, proven patterns, low risk
- **Medium**: Some ambiguity, moderate complexity, manageable risk
- **Low**: Unclear requirements, high complexity, significant risk

## Getting Help

### For Validation Issues
```
@agent-contract-validator why did validation fail?
```

### For Improvement Guidance
```
@agent-contract-validator what are the most important improvements?
```

### For Pattern Examples
```
@agent-contract-validator show similar successful contracts
```

### For Compliance Details
```
@agent-contract-validator explain ONEX compliance scoring
```
