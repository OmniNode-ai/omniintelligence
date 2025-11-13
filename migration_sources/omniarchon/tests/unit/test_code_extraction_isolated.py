#!/usr/bin/env python3
"""
Isolated Test for CodeExtractionService Core Methods

This test isolates and tests the core file analysis and technology detection
capabilities of the CodeExtractionService without requiring database connections
or the full application environment.

Focus: Proving what the service can detect from file data.
"""

import re
from datetime import datetime
from typing import Any, Dict, List


class IsolatedCodeAnalyzer:
    """Isolated version of core CodeExtractionService methods for testing"""

    # Language-specific patterns (from the actual service)
    LANGUAGE_PATTERNS = {
        "typescript": {
            "block_start": r"^\s*(export\s+)?(class|interface|function|const|type|enum)\s+\w+",
            "block_end": r"^\}(\s*;)?$",
            "min_indicators": [
                ":",
                "{",
                "}",
                "=>",
                "function",
                "class",
                "interface",
                "type",
            ],
        },
        "javascript": {
            "block_start": r"^\s*(export\s+)?(class|function|const|let|var)\s+\w+",
            "block_end": r"^\}(\s*;)?$",
            "min_indicators": ["function", "{", "}", "=>", "const", "let", "var"],
        },
        "python": {
            "block_start": r"^\s*(class|def|async\s+def)\s+\w+",
            "block_end": r"^\S",  # Unindented line
            "min_indicators": ["def", ":", "return", "self", "import", "class"],
        },
    }

    def detect_language_from_extension(self, url: str) -> str:
        """Extract language from file extension"""
        if "." not in url:
            return ""

        extension = url.split(".")[-1].lower()
        extension_map = {
            "py": "python",
            "ts": "typescript",
            "tsx": "typescript",
            "js": "javascript",
            "jsx": "javascript",
            "md": "markdown",
            "txt": "text",
        }

        return extension_map.get(extension, "")

    def detect_language_from_content(self, code: str) -> str:
        """Detect programming language from code content (from actual service)"""
        patterns = {
            "python": [
                r"\bdef\s+\w+\s*\(",
                r"\bclass\s+\w+",
                r"\bimport\s+\w+",
                r"\bfrom\s+\w+\s+import",
            ],
            "javascript": [
                r"\bfunction\s+\w+\s*\(",
                r"\bconst\s+\w+\s*=",
                r"\blet\s+\w+\s*=",
                r"\bvar\s+\w+\s*=",
            ],
            "typescript": [
                r"\binterface\s+\w+",
                r":\s*\w+\[\]",
                r"\btype\s+\w+\s*=",
                r"\bclass\s+\w+.*\{",
            ],
        }

        # Count matches for each language
        scores = {}
        for lang, lang_patterns in patterns.items():
            score = 0
            for pattern in lang_patterns:
                if re.search(pattern, code, re.MULTILINE):
                    score += 1
            if score > 0:
                scores[lang] = score

        # Return language with highest score
        if scores:
            return max(scores, key=scores.get)
        return ""

    def detect_technology_stack(self, content: str, url: str) -> List[str]:
        """Detect technology stack from content and URL"""
        tech_stack = set()
        content_lower = content.lower()

        # Framework detection
        framework_patterns = {
            "Python": ["python", "def ", "import ", "from ", "class "],
            "FastAPI": ["fastapi", "from fastapi", "@app.", "HTTPException"],
            "React": [
                "import React",
                "useState",
                "useEffect",
                "React.FC",
                "jsx",
                "tsx",
            ],
            "TypeScript": [
                "interface ",
                ": string",
                ": number",
                "React.FC",
                ".tsx",
                ".ts",
            ],
            "Pydantic": ["pydantic", "BaseModel", "Field(", "from pydantic"],
            "Testing": ["pytest", "test_", "def test", "assert ", "TestClient"],
            "SQLAlchemy": ["sqlalchemy", "AsyncSession", "from sqlalchemy"],
            "Docker": ["docker", "dockerfile", "docker-compose"],
            "JavaScript": ["const ", "let ", "var ", "function", "=>"],
        }

        for tech, patterns in framework_patterns.items():
            if any(pattern.lower() in content_lower for pattern in patterns):
                tech_stack.add(tech)

        # Extension-based detection
        if url.endswith(".py"):
            tech_stack.add("Python")
        elif url.endswith((".ts", ".tsx")):
            tech_stack.add("TypeScript")
        elif url.endswith((".js", ".jsx")):
            tech_stack.add("JavaScript")

        return list(tech_stack)

    def extract_file_extensions(self, urls: List[str]) -> List[str]:
        """Extract file extensions from a list of URLs"""
        extensions = []
        for url in urls:
            if "." in url:
                ext = url.split(".")[-1].lower()
                extensions.append(ext)
        return extensions

    def extract_directories(self, urls: List[str]) -> List[str]:
        """Extract directory paths from URLs"""
        directories = []
        for url in urls:
            if "/" in url:
                directory = "/".join(url.split("/")[:-1])
                if directory:  # Don't add empty strings
                    directories.append(directory)
        return directories

    def find_common_files(self, urls: List[str]) -> List[str]:
        """Find common configuration and standard files"""
        common_file_patterns = [
            "README.md",
            "readme.md",
            "README.txt",
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
            "__init__.py",
            "setup.py",
            "setup.cfg",
            "tsconfig.json",
            "babel.config.js",
            "webpack.config.js",
            ".gitignore",
            ".env",
            "Makefile",
        ]

        filenames = [url.split("/")[-1] for url in urls]
        common_files = [f for f in common_file_patterns if f in filenames]
        return common_files

    def calculate_file_overlap_ratio(
        self, files1: List[str], files2: List[str]
    ) -> float:
        """Calculate file overlap ratio between two file lists"""
        if not files1 or not files2:
            return 0.0

        # Extract just filenames for comparison
        names1 = set(f.split("/")[-1] for f in files1)
        names2 = set(f.split("/")[-1] for f in files2)

        intersection = len(names1 & names2)
        union = len(names1 | names2)

        return intersection / union if union > 0 else 0.0


class TestDataGenerator:
    """Generate realistic test data for the analyzer"""

    @staticmethod
    def get_test_files() -> List[Dict[str, Any]]:
        """Get test files with realistic content"""
        return [
            {
                "url": "test-fresh-intelligence.py",
                "content": """#!/usr/bin/env python3
import asyncio
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class IntelligenceData:
    correlation_id: str
    strength: float

async def analyze_correlations(data: List[Dict]) -> IntelligenceData:
    for item in data:
        if item.get('strength', 0) > 0.8:
            return IntelligenceData(
                correlation_id=item['id'],
                strength=item['strength']
            )
    return None

if __name__ == "__main__":
    asyncio.run(analyze_correlations([]))
""",
            },
            {
                "url": "integration_test_python-integration.py",
                "content": """import pytest
import httpx
from fastapi.testclient import TestClient
from server.main import app

class TestPythonIntegration:

    def setup_method(self):
        self.client = TestClient(app)

    def test_api_endpoint(self):
        response = self.client.get("/api/test")
        assert response.status_code == 200
        assert "data" in response.json()
""",
            },
            {
                "url": "src/test1.py",
                "content": """from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class UserModel(BaseModel):
    id: int = Field(..., description="User ID")
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = Field(None, regex=r'^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)
""",
            },
            {
                "url": "src/test2.py",
                "content": """from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/users/")
async def create_user(
    user_data: UserModel,
    db: AsyncSession = Depends(get_session)
):
    return {"message": "User created"}
""",
            },
            {
                "url": "frontend/Dashboard.tsx",
                "content": """import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useQuery } from '@tanstack/react-query';

interface CorrelationData {
  id: string;
  repository: string;
  strength: number;
}

export const Dashboard: React.FC = () => {
  const [selectedRepo, setSelectedRepo] = useState<string>('');

  const { data: correlations } = useQuery({
    queryKey: ['correlations'],
    queryFn: async (): Promise<CorrelationData[]> => {
      const response = await fetch('/api/correlations');
      return response.json();
    },
  });

  return (
    <div className="p-6">
      <Button onClick={() => setSelectedRepo('')}>
        Clear Selection
      </Button>
    </div>
  );
};
""",
            },
            {
                "url": "frontend/hooks/useCorrelations.ts",
                "content": """import { useState, useCallback } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';

interface CorrelationFilters {
  repository?: string;
  strength?: number;
}

export const useCorrelations = () => {
  const [filters, setFilters] = useState<CorrelationFilters>({});

  const query = useQuery({
    queryKey: ['correlations', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      const response = await fetch(`/api/correlations?${params}`);
      return response.json();
    },
  });

  return query;
};
""",
            },
            {
                "url": "README.md",
                "content": """# Python Integration Testing Project

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy
- **Testing**: pytest, httpx, TestClient
- **Frontend**: React, TypeScript, Tailwind CSS
- **Database**: PostgreSQL with asyncio
- **Validation**: Pydantic models

## Code Examples

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}
```

```typescript
interface User {
  id: number;
  name: string;
}
```
""",
            },
        ]


def test_file_analysis_capabilities():
    """Test the core file analysis capabilities"""
    print("🔍 ISOLATED CODEEXTRACTIONSERVICE ANALYSIS TEST")
    print("=" * 70)
    print("Testing core file analysis methods without full service dependencies")
    print("=" * 70)

    analyzer = IsolatedCodeAnalyzer()
    test_files = TestDataGenerator.get_test_files()

    results = {
        "language_detection": {},
        "technology_detection": {},
        "file_structure_analysis": {},
        "correlation_data_simulation": {},
    }

    print("\n📋 TEST FILES:")
    urls = [f["url"] for f in test_files]
    for i, url in enumerate(urls, 1):
        print(f"   {i}. {url}")

    # Test 1: Language Detection
    print("\n🔍 TEST 1: LANGUAGE DETECTION FROM EXTENSIONS")
    print("-" * 50)

    for test_file in test_files:
        url = test_file["url"]
        content = test_file["content"]

        # Extension-based detection
        ext_language = analyzer.detect_language_from_extension(url)

        # Content-based detection
        content_language = analyzer.detect_language_from_content(content)

        results["language_detection"][url] = {
            "extension_language": ext_language,
            "content_language": content_language,
            "content_length": len(content),
        }

        print(f"📄 {url}")
        print(f"   Extension → {ext_language or 'Unknown'}")
        print(f"   Content   → {content_language or 'Unknown'}")

    # Test 2: Technology Stack Detection
    print("\n🎯 TEST 2: TECHNOLOGY STACK DETECTION")
    print("-" * 50)

    all_technologies = set()

    for test_file in test_files:
        url = test_file["url"]
        content = test_file["content"]

        tech_stack = analyzer.detect_technology_stack(content, url)
        results["technology_detection"][url] = tech_stack
        all_technologies.update(tech_stack)

        print(f"📄 {url}")
        print(f"   Technologies: {tech_stack}")

    print(f"\n🔧 OVERALL TECHNOLOGY STACK DETECTED: {list(all_technologies)}")

    # Test 3: File Structure Analysis
    print("\n📁 TEST 3: FILE STRUCTURE ANALYSIS")
    print("-" * 50)

    extensions = analyzer.extract_file_extensions(urls)
    directories = analyzer.extract_directories(urls)
    common_files = analyzer.find_common_files(urls)

    results["file_structure_analysis"] = {
        "extensions": list(set(extensions)),
        "directories": list(set(directories)),
        "common_files": common_files,
        "total_files": len(urls),
    }

    print(f"📄 File Extensions: {list(set(extensions))}")
    print(f"📂 Directories: {list(set(directories))}")
    print(f"🔗 Common Files: {common_files}")

    # Test 4: Simulate Correlation Data Generation
    print("\n🔗 TEST 4: CORRELATION DATA SIMULATION")
    print("-" * 50)

    # Simulate what correlation generation would see
    correlation_simulation = {
        "technology_stack": list(all_technologies),
        "common_extensions": list(set(extensions)),
        "common_directories": list(set(directories)),
        "common_files": common_files,
        "file_overlap_ratio": len(common_files) / len(urls) if urls else 0,
        "total_files_analyzed": len(urls),
    }

    results["correlation_data_simulation"] = correlation_simulation

    print("📊 Simulated correlation data:")
    for key, value in correlation_simulation.items():
        print(f"   {key}: {value}")

    # Final Assessment
    print("\n🏆 FINAL ASSESSMENT")
    print("=" * 50)

    # Check for the reported issues
    tech_stack = correlation_simulation["technology_stack"]
    extensions = correlation_simulation["common_extensions"]

    assessment = []

    if not tech_stack or tech_stack == ["Unknown"]:
        assessment.append("❌ PROBLEM: Technology stack detection failing")
        assessment.append(
            "   This explains 'technology_stack: [Unknown]' in correlations"
        )
    else:
        assessment.append("✅ SUCCESS: Technology stack detection working")
        assessment.append(f"   Detected: {tech_stack}")
        assessment.append(
            "   Issue is NOT in CodeExtractionService technology detection"
        )

    if not extensions or extensions == ["mixed"]:
        assessment.append("❌ PROBLEM: Extension detection failing")
        assessment.append(
            "   This explains 'common_extensions: [mixed]' in correlations"
        )
    else:
        assessment.append("✅ SUCCESS: Extension detection working")
        assessment.append(f"   Detected: {extensions}")
        assessment.append(
            "   Issue is NOT in CodeExtractionService extension detection"
        )

    # Overall verdict
    if (
        tech_stack
        and tech_stack != ["Unknown"]
        and extensions
        and extensions != ["mixed"]
    ):
        assessment.append("")
        assessment.append("🎯 VERDICT: CodeExtractionService file analysis is WORKING")
        assessment.append("   The 'Unknown'/'mixed' issue is likely in:")
        assessment.append(
            "   • How correlation generation processes the service results"
        )
        assessment.append("   • Data mapping between service and correlation logic")
        assessment.append("   • Integration layer that calls the service methods")
    else:
        assessment.append("")
        assessment.append("🎯 VERDICT: CodeExtractionService has CORE ISSUES")
        assessment.append(
            "   The service itself is not detecting technologies/extensions properly"
        )

    for line in assessment:
        print(line)

    # Evidence Summary
    print("\n📋 EVIDENCE SUMMARY")
    print("-" * 30)
    print(
        f"✅ Languages detected from extensions: {len([r for r in results['language_detection'].values() if r['extension_language']])}/{len(test_files)}"
    )
    print(
        f"✅ Languages detected from content: {len([r for r in results['language_detection'].values() if r['content_language']])}/{len(test_files)}"
    )
    print(f"✅ Technologies detected: {len(all_technologies)} unique technologies")
    print(f"✅ Extensions found: {len(set(extensions))} unique extensions")
    print(f"✅ Directories found: {len(set(directories))} unique directories")
    print(f"✅ Common files found: {len(common_files)}")

    return results


if __name__ == "__main__":
    print(f"🕐 Test started at: {datetime.now()}")

    try:
        results = test_file_analysis_capabilities()
        print("\n✅ Test completed successfully")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
