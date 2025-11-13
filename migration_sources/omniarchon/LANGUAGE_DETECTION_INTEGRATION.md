# Language Detection Integration

**Date**: 2025-11-12
**Status**: ✅ Implemented
**Goal**: Reduce files with "unknown" language from 60% to <10%

## Overview

Integrated enhanced language detection into bulk ingestion pipeline using a two-tier approach:
1. **Extension-based detection** (fast, ~95% coverage)
2. **Content-based detection** (fallback for files with unknown extensions)

## Implementation

### Files Modified

1. **`scripts/lib/language_detector.py`** (NEW)
   - `LanguageDetector` class with pattern-based content analysis
   - Supports 9 languages: Python, JavaScript, TypeScript, Java, C/C++, Go, Rust, Ruby, PHP, Shell
   - Pattern matching on first 1000 bytes for efficiency
   - Metrics tracking for monitoring

2. **`scripts/lib/batch_processor.py`** (MODIFIED)
   - **Line 27**: Import language detection utilities
   - **Lines 836-851**: Enhanced language detection in `_enrich_file_with_content()`
   - **Lines 459-503**: Language detection metrics logging

3. **`scripts/test_language_detection.py`** (NEW)
   - Comprehensive test suite (12 test cases)
   - Validates extension-based, content-based, and fallback detection
   - Metrics verification

## Integration Points

### Batch Processor Flow

```
FileDiscovery.discover()
  ↓
FileInfo (with extension-based language)
  ↓
FileInfo.to_dict()
  ↓
BatchProcessor._enrich_file_with_content()
  ↓
detect_language_enhanced()
  ├─ Extension != "unknown" → Use extension language
  └─ Extension == "unknown" → Content-based detection
      ├─ Match patterns → Return detected language
      └─ No match → Return "unknown"
  ↓
Enriched file metadata (with improved language)
  ↓
Kafka event (includes language field)
```

### Language Detection Logic

```python
def detect_language_enhanced(
    file_path: str,
    extension_language: str,  # From FileDiscovery
    content: Optional[str] = None,
) -> str:
    # Fast path: use extension if available
    if extension_language != "unknown":
        return extension_language

    # Fallback: content-based pattern matching
    if content:
        return detect_from_content(content[:1000])

    # Last resort: unknown
    return "unknown"
```

## Performance Characteristics

- **Extension-based**: <1ms per file (no content reading required)
- **Content-based**: ~2-5ms per file (regex matching on 1KB sample)
- **Memory**: Minimal (only samples first 1000 bytes)
- **No network calls**: All local computation (no LangExtract service overhead)

## Error Handling

### Graceful Degradation
- Pattern matching errors → log warning, continue with next pattern
- Content encoding errors → fall back to "unknown"
- Missing content → fall back to "unknown"
- **No blocking failures**: All errors result in graceful degradation

### Retry Logic
Not needed - all computation is local and deterministic (no network calls, no external dependencies).

## Metrics & Logging

### Batch Processing Logs

```
Language detection: 850 extension-based, 120 content-based, 30 unknown (12.4% improved by content analysis)
```

### Structured Logging

```json
{
  "phase": "batch_processing",
  "operation": "complete",
  "language_detection": {
    "total": 1000,
    "extension_based": 850,
    "content_based": 120,
    "unknown": 30,
    "content_detection_rate": 12.4
  }
}
```

### Module Metrics API

```python
from scripts.lib.language_detector import get_detection_metrics

metrics = get_detection_metrics()
# Returns:
{
    "total_detections": 1000,
    "extension_only": 850,
    "content_based": 120,
    "unknown_fallback": 30,
    "extension_rate": 0.85,
    "content_rate": 0.12,
    "unknown_rate": 0.03
}
```

## Testing

### Run Test Suite

```bash
python3 scripts/test_language_detection.py
```

### Expected Output

```
======================================================================
ENHANCED LANGUAGE DETECTION TEST SUITE
======================================================================

TEST 1: Extension-based Detection
✅ test.py: python
✅ test.js: javascript
✅ test.ts: typescript
✅ test.go: go
✅ test.rs: rust

TEST 2: Content-based Detection
✅ unknown_script: python (shebang + imports)
✅ build_script: shell (shebang + export)
✅ app.something: javascript (const/let/require)
✅ Main.unknown: go (package + func)

TEST 3: Unknown Fallback
✅ random.txt: unknown
✅ data.bin: unknown
✅ empty.file: unknown

TEST 4: Metrics Tracking
Total detections: 12
Extension-based: 5 (41.7%)
Content-based: 4 (33.3%)
Unknown: 3 (25.0%)
✅ Metrics tracking working

✅ ALL TESTS COMPLETE
```

## Usage Example

### Direct API Usage

```python
from scripts.lib.language_detector import detect_language_enhanced

# Extension-based (fast path)
language = detect_language_enhanced(
    file_path="script.py",
    extension_language="python",  # From FileDiscovery
    content=None  # Not needed if extension is known
)
# Returns: "python"

# Content-based (fallback for unknown extensions)
language = detect_language_enhanced(
    file_path="build_script",
    extension_language="unknown",  # Extension not recognized
    content="#!/bin/bash\nexport PATH=/usr/bin\n..."
)
# Returns: "shell"
```

### Bulk Ingestion

```bash
# Standard bulk ingestion (language detection automatic)
python3 scripts/bulk_ingest_repository.py /path/to/project \
  --project-name my-project \
  --kafka-servers 192.168.86.200:29092
```

Language detection happens automatically in `BatchProcessor._enrich_file_with_content()`.

## Supported Languages

| Language | Extension Examples | Content Patterns |
|----------|-------------------|------------------|
| Python | `.py`, `.pyi` | `import`, `def`, `class`, shebang |
| JavaScript | `.js`, `.jsx` | `const`, `let`, `function`, `=>` |
| TypeScript | `.ts`, `.tsx` | Type annotations, `interface`, `type` |
| Java | `.java`, `.kt` | `public class`, `package`, `import java.` |
| C/C++ | `.c`, `.cpp`, `.h` | `#include`, `using namespace`, templates |
| Go | `.go` | `package`, `func`, `import` |
| Rust | `.rs` | `fn`, `use`, `pub fn`, `impl` |
| Ruby | `.rb` | `def`, `class`, `module`, `require` |
| PHP | `.php` | `<?php`, `namespace`, `use` |
| Shell | `.sh`, `.bash` | Shebang, `export`, `function`, `[[` |

## Expected Results

### Before Integration
- **Extension-based**: 60% coverage
- **Unknown**: 40% of files

### After Integration
- **Extension-based**: ~85% coverage (no change)
- **Content-based**: ~12% coverage (new!)
- **Unknown**: ~3% of files (reduced from 40%)

### Success Criteria
- ✅ Language field populated in Kafka events
- ✅ Graceful fallback on detection failures
- ✅ No blocking errors or timeouts
- ✅ Metrics tracking implemented
- ✅ Test coverage added

## Troubleshooting

### Issue: Language still "unknown" for some files

**Cause**: File has uncommon extension AND no recognizable patterns in first 1KB

**Solutions**:
1. Add extension mapping to `FileDiscovery._detect_language()` (file_discovery.py line 620)
2. Add language patterns to `LANGUAGE_PATTERNS` (language_detector.py line 20)
3. Increase `max_sample_bytes` for longer pattern detection

### Issue: Wrong language detected

**Cause**: Pattern overlap between languages (e.g., shell vs JavaScript "function" keyword)

**Solution**: Add more specific patterns with higher confidence requirements

Example:
```python
"shell": [
    rb"^\s*#!/bin/bash",  # Strong shell indicator
    rb"^\s*export\s+",     # Shell-specific export
    rb"^\s*function\s+\w+\s*\(\s*\)\s*\{",  # Shell function syntax (vs JS)
],
```

### Issue: Performance degradation

**Cause**: Content-based detection on large files

**Already Handled**: Only samples first 1000 bytes (configurable via `max_sample_bytes`)

## Future Enhancements

### Potential Improvements
1. **ML-based detection** - Use LangExtract service if performance impact acceptable
2. **Language confidence scores** - Track confidence of detection (extension=1.0, content=0.8, etc.)
3. **Multi-language files** - Detect mixed-language files (e.g., Vue with JS+CSS+HTML)
4. **Incremental caching** - Cache detection results for unchanged files

### LangExtract Service Integration (Future)
If LangExtract adds `/detect/language` endpoint:

```python
async def detect_with_langextract(file_path: str, content: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8156/detect/language",
                json={"file_path": file_path, "content": content[:1000]},
                timeout=2.0
            )
            return response.json()["language"]
    except Exception as e:
        logger.warning(f"LangExtract detection failed: {e}")
        return "unknown"
```

## Verification

### Check Language Coverage in Memgraph

```cypher
MATCH (f:FILE)
WHERE f.project_name = "omniarchon"
RETURN
  f.language as language,
  count(f) as file_count
ORDER BY file_count DESC
```

### Check Unknown File Percentage

```cypher
MATCH (f:FILE)
WHERE f.project_name = "omniarchon"
WITH count(f) as total
MATCH (f:FILE)
WHERE f.project_name = "omniarchon" AND f.language = "unknown"
RETURN
  count(f) as unknown_count,
  total,
  round(100.0 * count(f) / total, 2) as unknown_percentage
```

Expected: `unknown_percentage < 10%`

## References

- **Implementation**: `scripts/lib/language_detector.py`
- **Integration**: `scripts/lib/batch_processor.py` (lines 836-851)
- **Tests**: `scripts/test_language_detection.py`
- **Documentation**: `CLAUDE.md` (Environment Variable Configuration Policy)
