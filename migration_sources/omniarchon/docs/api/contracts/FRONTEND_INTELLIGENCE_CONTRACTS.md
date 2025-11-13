# Frontend Intelligence Dashboard Contracts

## Overview
This document defines the exact data contracts expected by the React Intelligence Dashboard component for displaying file-level correlation information.

## React Component Contract (`IntelligencePage.tsx`)

### Expected API Response Structure

#### Complete Intelligence Document
```typescript
interface IntelligenceDocument {
    id: string;
    created_at: string;
    repository: string;
    commit_sha: string;
    author: string;
    change_type: string;
    intelligence_data: {
        diff_analysis: {
            total_changes: number;
            added_lines: number;
            removed_lines: number;
            modified_files: string[];
        };
        correlation_analysis: {
            temporal_correlations: TemporalCorrelation[];
            semantic_correlations: SemanticCorrelation[];
            breaking_changes: BreakingChange[];
        };
        security_analysis?: SecurityAnalysis;
    };
}
```

#### Semantic Correlation Structure (Critical for File Info Display)
```typescript
interface SemanticCorrelation {
    repository: string;
    commit_sha: string;
    semantic_similarity: number;           // 0.0-1.0
    common_keywords: string[];
    file_information: FileInformation | null;  // MUST NOT BE NULL for display
}
```

#### File Information Structure (Langextract-style Analysis)
```typescript
interface FileInformation {
    common_files: string[];                // Exact file matches between repos
    common_extensions: string[];           // File extensions: ["py", "ts", "json"]
    common_directories: string[];          // Directory patterns: ["src", "api"]
    file_overlap_ratio: number;            // 0.0-1.0 percentage
    technology_stack: string[];            // Technologies: ["Python", "TypeScript"]
}
```

### React Component Rendering Logic

#### File Information Display Component
```tsx
{corr.file_information && (
    <div className="flex items-center space-x-3 text-xs text-gray-500 ml-4">

        {/* Technology Stack Display */}
        {corr.file_information.technology_stack &&
         corr.file_information.technology_stack.length > 0 && (
            <div className="flex items-center space-x-1">
                <span className="text-gray-400">Tech:</span>
                <span>{corr.file_information.technology_stack.slice(0, 2).join(', ')}</span>
            </div>
        )}

        {/* File Extensions Display */}
        {corr.file_information.common_extensions &&
         corr.file_information.common_extensions.length > 0 && (
            <div className="flex items-center space-x-1">
                <span className="text-gray-400">Files:</span>
                <span>.{corr.file_information.common_extensions.slice(0, 3).join(', .')}</span>
            </div>
        )}

        {/* File Overlap Ratio Display */}
        {corr.file_information.file_overlap_ratio > 0 && (
            <div className="flex items-center space-x-1">
                <span className="text-gray-400">Overlap:</span>
                <span>{(corr.file_information.file_overlap_ratio * 100).toFixed(0)}%</span>
            </div>
        )}

    </div>
)}
```

### Expected Display Examples

#### Example 1: Python/TypeScript Correlation
```
omniagent (api_service, python_toolkit) 42%
  Tech: Python, TypeScript
  Files: .py, .ts, .json  
  Overlap: 25%
```

#### Example 2: No File Overlap
```
archon-ui (react_components, ui_system) 38%
  Tech: TypeScript, React
  Files: .tsx, .css
  Overlap: 0%
```

#### Example 3: High Overlap
```
omnibase-core (core_services, spi_protocol) 67%
  Tech: Python
  Files: .py, .toml
  Overlap: 85%
```

## API Endpoint Contract

### GET `/api/intelligence/documents`

**Expected Response for Frontend:**
```json
{
    "success": true,
    "total_documents": 10,
    "documents": [
        {
            "id": "doc-123",
            "created_at": "2025-09-05T16:00:00Z",
            "repository": "archon",
            "commit_sha": "abc123",
            "author": "developer",
            "change_type": "enhanced_code_changes_with_correlation",
            "intelligence_data": {
                "diff_analysis": {
                    "total_changes": 3,
                    "added_lines": 50,
                    "removed_lines": 10,
                    "modified_files": ["src/api/service.py", "ui/components.tsx"]
                },
                "correlation_analysis": {
                    "semantic_correlations": [
                        {
                            "repository": "omniagent",
                            "commit_sha": "def456",
                            "semantic_similarity": 0.42,
                            "common_keywords": ["api", "service", "python"],
                            "file_information": {
                                "common_files": [],
                                "common_extensions": ["py", "tsx"],
                                "common_directories": ["src", "api"],
                                "file_overlap_ratio": 0.25,
                                "technology_stack": ["Python", "TypeScript"]
                            }
                        }
                    ],
                    "temporal_correlations": [],
                    "breaking_changes": []
                }
            }
        }
    ]
}
```

## Frontend State Management

### Intelligence Dashboard State
```typescript
interface IntelligenceState {
    documents: IntelligenceDocument[];
    loading: boolean;
    error: string | null;
    selectedRepository: string;
    timeRange: string;
    stats: {
        totalChanges: number;
        correlations: number;
        avgCorrelation: number;
        breakingChanges: number;
    };
}
```

### File Information Rendering Conditions
```typescript
// File information only renders when:
1. corr.file_information !== null
2. corr.file_information !== undefined  
3. At least one of these arrays has content:
   - technology_stack.length > 0
   - common_extensions.length > 0
   - file_overlap_ratio > 0
```

## Debugging Frontend Issues

### Common Problems & Solutions

#### Issue: File information not displaying
**Check:**
1. API response contains `file_information` object (not null)
2. Object has at least one non-empty field
3. React component conditional rendering logic
4. Browser console for JavaScript errors

#### Issue: Technology stack not showing
**Check:**
1. `file_information.technology_stack` is array with strings
2. Array length > 0
3. Values are meaningful (not just ["Unknown"])

#### Issue: File extensions not displaying  
**Check:**
1. `file_information.common_extensions` is array with strings
2. Extensions don't include dots (just "py", not ".py")
3. Extensions are meaningful (not just ["mixed"])

### Debug API Response
```bash
# Check complete API response structure
curl -s "http://localhost:8181/api/intelligence/documents?limit=1" | \
jq '.documents[0].intelligence_data.correlation_analysis.semantic_correlations[0]'

# Expected output should include file_information object:
{
  "repository": "omniagent",
  "semantic_similarity": 0.42,
  "common_keywords": ["api", "service"],
  "file_information": {
    "technology_stack": ["Python", "TypeScript"],
    "common_extensions": ["py", "ts"],
    "file_overlap_ratio": 0.25
  }
}
```

## Testing Frontend Display

### Manual Tests
1. Open Intelligence Dashboard
2. Look for correlations with percentages (e.g., "omniagent 42%")
3. Below correlation, expect to see:
   - "Tech: Python, TypeScript"
   - "Files: .py, .ts"
   - "Overlap: 25%" (if > 0)

### Automated Tests (Jest/React Testing Library)
```typescript
describe('Semantic Correlation File Information', () => {
    it('displays technology stack when present', () => {
        const correlation = {
            repository: 'omniagent',
            semantic_similarity: 0.42,
            common_keywords: ['api'],
            file_information: {
                technology_stack: ['Python', 'TypeScript'],
                common_extensions: ['py', 'ts'],
                file_overlap_ratio: 0.25
            }
        };

        render(<SemanticCorrelationDisplay correlation={correlation} />);

        expect(screen.getByText('Tech: Python, TypeScript')).toBeInTheDocument();
        expect(screen.getByText('Files: .py, .ts')).toBeInTheDocument();
        expect(screen.getByText('Overlap: 25%')).toBeInTheDocument();
    });

    it('hides file information when null', () => {
        const correlation = {
            repository: 'omniagent',
            semantic_similarity: 0.42,
            common_keywords: ['api'],
            file_information: null
        };

        render(<SemanticCorrelationDisplay correlation={correlation} />);

        expect(screen.queryByText(/Tech:/)).not.toBeInTheDocument();
        expect(screen.queryByText(/Files:/)).not.toBeInTheDocument();
    });
});
```

## Success Criteria

### File Information Display Working When:
- [ ] API returns `file_information` object (not null)
- [ ] Object contains meaningful data (not defaults like ["Unknown"])
- [ ] React component renders file info below correlation percentage
- [ ] Technology stack shows inferred languages/frameworks
- [ ] File extensions show common file types
- [ ] Overlap percentage shows when > 0
- [ ] Display updates after correlation regeneration

### Complete User Experience:
```
Cross-Repository Intelligence Correlations
Semantic Correlations (2)

├─ omniagent (api_service, python_toolkit) 42%
│   Tech: Python, TypeScript
│   Files: .py, .ts, .json
│   Overlap: 25%
│
└─ archon-ui (react_components, ui_system) 38%  
    Tech: TypeScript, React
    Files: .tsx, .css
    Overlap: 0%
```
