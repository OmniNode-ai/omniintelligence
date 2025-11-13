# Memgraph Schema Diagram

**Date**: 2025-11-09
**Purpose**: Visual representation of current Memgraph schema and entity_id formats

---

## Current Schema Structure (BROKEN STATE)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MEMGRAPH DATABASE                                │
│                         Total: 6,996 nodes                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                ┌───────────────────┴────────────────────┐
                │                                        │
                ▼                                        ▼
    ┌────────────────────────┐              ┌────────────────────────┐
    │   FILE NODES (1,179)   │              │  ENTITY NODES (5,817)  │
    └────────────────────────┘              └────────────────────────┘
                │                                        │
    ┌───────────┴────────────┐              ┌───────────┴────────────┐
    │                        │              │                        │
    ▼                        ▼              ▼                        ▼
┌─────────┐           ┌──────────┐    ┌──────────┐           ┌──────────┐
│  REAL   │           │PLACEHOLDER│   │   FULL   │           │   STUB   │
│  FILES  │           │  FILES   │    │ ENTITIES │           │ ENTITIES │
│         │           │          │    │          │           │          │
│  343    │           │   842    │    │  5,812   │           │    5     │
│  nodes  │           │  nodes   │    │  nodes   │           │  nodes   │
└─────────┘           └──────────┘    └──────────┘           └──────────┘
     │                      │                │                      │
     │                      │                └──────────┬───────────┘
     │                      │                           │
     ▼                      ▼                           ▼
┌─────────┐           ┌──────────┐              ┌──────────┐
│ entity_ │           │file:proj:│              │entity_   │
│ id:     │           │entity_id:│              │id:       │
│         │           │          │              │          │
│file_HASH│    ┌──────┤file:proj:│◄──┐          │entity_XX │
│         │    │      │ module   │   │          │  _YY     │
│15 props │    │      │          │   │          │          │
│         │    │      │4 props   │   │          │11 props  │
│         │    │      └──────────┘   │          │          │
│ORPHANED │    │                     │          │CONNECTED │
│ (0 rels)│    │      ┌──────────┐   │          │          │
│         │    │      │file:proj:│   │          │          │
│         │    └─────►│ path     │   │          │          │
│         │           │          │   │          │          │
└─────────┘           │4 props   │◄──┘          └──────────┘
                      └──────────┘                    │
                           │                          │
                           │                          │
                      ┌────┴─────┐              ┌─────┴─────┐
                      │          │              │           │
                      ▼          ▼              ▼           ▼
               ┌──────────────────────┐  ┌──────────────────────┐
               │  IMPORTS (1,505)     │  │   RELATES (1,047)    │
               │  Relationships       │  │   Relationships      │
               │                      │  │                      │
               │ PLACEHOLDER→PLACEHOLDER│ │   Entity→Entity     │
               └──────────────────────┘  └──────────────────────┘
```

---

## Entity_ID Format Breakdown

### REAL FILE Nodes (343 nodes)

```
┌──────────────────────────────────────────────────────────┐
│  REAL FILE NODE                                          │
│  Label: FILE                                             │
├──────────────────────────────────────────────────────────┤
│  entity_id: "file_91f521860bc3"    ◄── 12-char hash     │
│           └─────┬─────┘                                  │
│                 │                                        │
│           Derived from:                                  │
│           - File content hash (first 12 chars)           │
│           - Or BLAKE3 hash (first 12 chars)              │
├──────────────────────────────────────────────────────────┤
│  Properties (15):                                        │
│  ✓ name: "LANGUAGE_FIELD_INVESTIGATION_REPORT.md"       │
│  ✓ path: "archon://projects/omniarchon/documents/..."   │
│  ✓ project_name: "omniarchon"                           │
│  ✓ content_type: "documentation"                        │
│  ✓ language: "markdown"                                 │
│  ✓ file_size: 12151                                     │
│  ✓ line_count: 387                                      │
│  ✓ entity_count: 44                                     │
│  ✓ import_count: 3                                      │
│  ✓ file_hash: "2f0bdce11210a5f1"                        │
│  ✓ indexed_at: "2025-11-09T22:50:47.866679+00:00"       │
│  ✓ created_at: "2025-11-09T22:50:47.866679+00:00"       │
│  ✓ last_modified: "2025-11-09T22:50:47.866676+00:00"    │
│  ✓ relative_path: "archon:/projects/..."                │
├──────────────────────────────────────────────────────────┤
│  Relationships: NONE (ORPHANED)                          │
│  Status: ❌ NOT CONNECTED TO GRAPH                       │
└──────────────────────────────────────────────────────────┘
```

---

### PLACEHOLDER FILE Nodes - Import Type (636 nodes)

```
┌──────────────────────────────────────────────────────────┐
│  PLACEHOLDER FILE NODE (Import Reference)                │
│  Label: FILE                                             │
├──────────────────────────────────────────────────────────┤
│  entity_id: "file:omniarchon:asyncio"                    │
│           └─────┬────┬────────┬─────┘                    │
│                 │    │        │                          │
│              prefix project  module                      │
├──────────────────────────────────────────────────────────┤
│  Properties (4):                                         │
│  ✓ entity_id: "file:omniarchon:asyncio"                 │
│  ✓ name: "unknown"           ◄── Always "unknown"       │
│  ✓ path: "file:omniarchon:asyncio"                      │
│  ✓ created_at: "2025-11-09T23:01:13.877623+00:00"       │
├──────────────────────────────────────────────────────────┤
│  Relationships: IMPORTS (1,505 total)                    │
│  Status: ✅ CONNECTED (but minimal data)                 │
└──────────────────────────────────────────────────────────┘

Example modules with this format:
  • file:omniarchon:asyncio
  • file:omniarchon:httpx
  • file:omniarchon:json
  • file:omniarchon:typing.Any
  • file:omniarchon:sys
```

---

### PLACEHOLDER FILE Nodes - Path Type (206 nodes)

```
┌──────────────────────────────────────────────────────────┐
│  PLACEHOLDER FILE NODE (Path Reference)                  │
│  Label: FILE                                             │
├──────────────────────────────────────────────────────────┤
│  entity_id: "file:omniarchon:archon://projects/..."      │
│           └─────┬────┬───────────┬────────────┘          │
│                 │    │           │                       │
│              prefix project  full_path                   │
├──────────────────────────────────────────────────────────┤
│  Properties (4):                                         │
│  ✓ entity_id: "file:omniarchon:archon://projects/..."   │
│  ✓ name: "unknown"           ◄── Always "unknown"       │
│  ✓ path: "file:omniarchon:archon://projects/..."        │
│  ✓ created_at: "2025-11-09T23:01:13.877623+00:00"       │
├──────────────────────────────────────────────────────────┤
│  Relationships: IMPORTS (part of 1,505 total)            │
│  Status: ✅ CONNECTED (but minimal data)                 │
└──────────────────────────────────────────────────────────┘
```

---

### Full ENTITY Nodes (5,812 nodes)

```
┌──────────────────────────────────────────────────────────┐
│  FULL ENTITY NODE                                        │
│  Label: Entity                                           │
├──────────────────────────────────────────────────────────┤
│  entity_id: "entity_7275cb2b_f839d8c2"                   │
│           └───────┬────────┬──────────┘                  │
│                   │        │                             │
│             content_hash file_hash                       │
│               (8 chars)  (8 chars)                       │
├──────────────────────────────────────────────────────────┤
│  Properties (11):                                        │
│  ✓ entity_id: "entity_7275cb2b_f839d8c2"                │
│  ✓ name: "Task Complete: Relationship Storage..."       │
│  ✓ description: "Markdown heading (level 1): Task..."   │
│  ✓ entity_type: "CONCEPT"                               │
│  ✓ confidence_score: 0.8                                │
│  ✓ extraction_method: "enhanced_semantic_extraction"    │
│  ✓ file_hash: "039eab9890fecbd907c265bb594b8d62"        │
│  ✓ source_path: "archon://projects/omniarchon/..."      │
│  ✓ source_line_number: 3                                │
│  ✓ properties: "{...}"    ◄── JSON with context, etc.   │
│  ✓ created_at: "2025-11-09T22:46:57.020458+00:00"       │
├──────────────────────────────────────────────────────────┤
│  Relationships: RELATES (1,047 total)                    │
│  Status: ✅ CONNECTED                                     │
└──────────────────────────────────────────────────────────┘

Entity Types:
  • CONCEPT (headings, key ideas)
  • FUNCTION (code functions)
  • CLASS (code classes)
  • VARIABLE (code variables)
  • And more...
```

---

### Stub ENTITY Nodes (5 nodes)

```
┌──────────────────────────────────────────────────────────┐
│  STUB ENTITY NODE                                        │
│  Label: Entity                                           │
├──────────────────────────────────────────────────────────┤
│  entity_id: "httpx"       ◄── Simple name, no prefix    │
├──────────────────────────────────────────────────────────┤
│  Properties (4):                                         │
│  ✓ entity_id: "httpx"                                   │
│  ✓ name: "httpx"                                        │
│  ✓ entity_type: "reference"    ◄── Always "reference"   │
│  ✓ is_stub: True               ◄── Marked as stub       │
├──────────────────────────────────────────────────────────┤
│  Relationships: RELATES (as target)                      │
│  Status: ✅ CONNECTED (relationship target)              │
└──────────────────────────────────────────────────────────┘

Known stub entities:
  • httpx
  • inline
  • time
  • json
  • sys
```

---

## Relationship Flow Diagrams

### IMPORTS Relationships (1,505 total)

```
┌──────────────────┐                      ┌──────────────────┐
│  PLACEHOLDER     │                      │  PLACEHOLDER     │
│  FILE            │                      │  FILE            │
│                  │                      │                  │
│  entity_id:      │      ─IMPORTS─►     │  entity_id:      │
│  "file:omni-     │                      │  "file:omni-     │
│   archon:        │                      │   archon:        │
│   asyncio"       │                      │   archon://..."  │
│                  │                      │                  │
│  4 properties    │                      │  4 properties    │
└──────────────────┘                      └──────────────────┘

Example:
  (file:omniarchon:asyncio)
    -[IMPORTS]->
  (file:omniarchon:archon://projects/omniarchon/documents/.../test_kafka_event_flow.py)
```

**Problem**: These relationships connect PLACEHOLDER nodes, not REAL FILE nodes!

---

### RELATES Relationships (1,047 total)

```
┌──────────────────┐                      ┌──────────────────┐
│  STUB ENTITY     │                      │  STUB ENTITY     │
│                  │                      │                  │
│  entity_id:      │      ─RELATES─►     │  entity_id:      │
│  "inline"        │                      │  "httpx"         │
│                  │                      │                  │
│  4 properties    │                      │  4 properties    │
│  is_stub: True   │                      │  is_stub: True   │
└──────────────────┘                      └──────────────────┘

Relationship properties:
  • confidence_score: 1.0
  • relationship_type: "RELATES_TO"
  • properties: {
      bidirectional: false,
      evidence: ["import httpx"],
      source_position: 0,
      target_position: 0
    }
```

---

## The Disconnection Problem

### Current Broken Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  INDEXING PIPELINE                                              │
│  (Creates REAL FILE nodes)                                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  REAL FILE NODE     │
              │  entity_id:         │
              │  "file_91f521860bc3"│ ◄──┐
              │                     │    │
              │  15 properties      │    │ ORPHANED
              │  Full metadata      │    │ (No relationships
              └─────────────────────┘    │  connect here)
                         ▲               │
                         │               │
                         │ Should connect│
                         │ but doesn't   │
                         │               │
┌─────────────────────────────────────────────────────────────────┐
│  RELATIONSHIP CREATION                                          │
│  (Creates PLACEHOLDER nodes)                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  PLACEHOLDER FILE   │
              │  entity_id:         │
              │  "file:omniarchon:  │
              │   asyncio"          │
              │                     │
              │  4 properties       │
              │  name="unknown"     │
              └─────────────────────┘
                         │
                         │ Relationships
                         │ connect here
                         ▼
              ┌─────────────────────┐
              │  IMPORTS            │
              │  Relationships      │
              └─────────────────────┘
```

**Result**: Graph traversal queries return PLACEHOLDER nodes with minimal data instead of REAL FILE nodes with full metadata.

---

## Target Schema Structure (AFTER FIX)

```
┌─────────────────────────────────────────────────────────────────┐
│  INDEXING PIPELINE                                              │
│  (Creates REAL FILE nodes with standardized entity_id)          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  REAL FILE NODE     │
              │  entity_id:         │
              │  "file_91f521860bc3"│ ◄──┐
              │                     │    │
              │  15 properties      │    │ CONNECTED
              │  Full metadata      │    │ (Relationships
              └─────────────────────┘    │  target this)
                         ▲               │
                         │               │
                         │ Relationships │
                         │ connect here  │
                         │               │
┌─────────────────────────────────────────────────────────────────┐
│  RELATIONSHIP CREATION (WITH LOOKUP)                            │
│  1. Checks if REAL node exists                                  │
│  2. Uses REAL node's entity_id if found                         │
│  3. Creates PLACEHOLDER only if not found                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Lookup service
                         │ finds existing
                         │ entity_id
                         ▼
              ┌─────────────────────┐
              │  IMPORTS            │
              │  Relationships      │
              │  (target REAL nodes)│
              └─────────────────────┘
```

**Result**: Graph traversal returns REAL FILE nodes with full metadata.

---

## Statistics Summary

### Node Distribution

```
Total Nodes: 6,996
┌─────────────────────────────────────────────────┐
│ FILE Nodes (1,179)                              │
│ ┌─────────────────────────────────────────────┐ │
│ │ REAL (343)          ██████                  │ │  29%
│ └─────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────┐ │
│ │ PLACEHOLDER (842)   ██████████████          │ │  71%
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Entity Nodes (5,817)                            │
│ ┌─────────────────────────────────────────────┐ │
│ │ FULL (5,812)        ████████████████████████│ │  99.9%
│ └─────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────┐ │
│ │ STUB (5)            █                       │ │  0.1%
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### Relationship Distribution

```
Total Relationships: 2,552
┌─────────────────────────────────────────────────┐
│ IMPORTS (1,505)         ███████████████         │  59%
└─────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────┐
│ RELATES (1,047)         ██████████              │  41%
└─────────────────────────────────────────────────┘
```

### Orphaned Nodes

```
REAL FILE Nodes with 0 relationships: 343 (100% of REAL files)
┌─────────────────────────────────────────────────┐
│ ORPHANED (343)          ████████████████████████│  100%
└─────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────┐
│ CONNECTED (0)                                   │  0%
└─────────────────────────────────────────────────┘
```

**Critical Issue**: Every single REAL FILE node is orphaned!

---

## Visual Property Comparison

### REAL FILE Node vs PLACEHOLDER FILE Node

```
┌───────────────────────────┬───────────────────────────┐
│  REAL FILE NODE           │  PLACEHOLDER FILE NODE    │
├───────────────────────────┼───────────────────────────┤
│  entity_id ✓              │  entity_id ✓              │
│  name ✓                   │  name ✓ (always "unknown")│
│  path ✓                   │  path ✓                   │
│  project_name ✓           │  created_at ✓             │
│  content_type ✓           │                           │
│  language ✓               │  [4 properties total]     │
│  file_size ✓              │                           │
│  line_count ✓             │                           │
│  entity_count ✓           │                           │
│  import_count ✓           │                           │
│  file_hash ✓              │                           │
│  indexed_at ✓             │                           │
│  created_at ✓             │                           │
│  last_modified ✓          │                           │
│  relative_path ✓          │                           │
│                           │                           │
│  [15 properties total]    │                           │
└───────────────────────────┴───────────────────────────┘

Property difference: 11 properties (73% more data in REAL nodes)
```

---

## Conclusion Diagram

```
                      ┌─────────────────────┐
                      │   CURRENT PROBLEM   │
                      └──────────┬──────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ REAL FILE nodes │   │ PLACEHOLDER     │   │ Relationships   │
│ (343 nodes)     │   │ FILE nodes      │   │ target          │
│                 │   │ (842 nodes)     │   │ PLACEHOLDERs    │
│ Full metadata   │   │                 │   │                 │
│ (15 props)      │   │ Minimal data    │   │ Result: BROKEN  │
│                 │   │ (4 props)       │   │ graph traversal │
│ ORPHANED        │   │                 │   │                 │
│ (0 rels)        │   │ CONNECTED       │   │                 │
└─────────────────┘   └─────────────────┘   └─────────────────┘
        ▲                      ▲                      ▲
        │                      │                      │
        └──────────────────────┴──────────────────────┘
                               │
                               ▼
                      ┌─────────────────────┐
                      │  FIX: Standardize   │
                      │  entity_id format   │
                      │  + Add lookup       │
                      │  service            │
                      └─────────────────────┘
```

---

**Report**: See `MEMGRAPH_SCHEMA_ANALYSIS_REPORT.md` for complete analysis
**Reference**: See `ENTITY_ID_FORMAT_REFERENCE.md` for developer guide
**Last Updated**: 2025-11-09
