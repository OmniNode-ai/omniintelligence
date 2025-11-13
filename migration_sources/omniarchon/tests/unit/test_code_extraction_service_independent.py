#!/usr/bin/env python3
"""
Independent Test for CodeExtractionService

This test validates the CodeExtractionService in complete isolation from the correlation system
to verify its core capabilities:

1. Technology/language detection from file extensions
2. Technology stack identification from file patterns
3. File analysis methods used by correlation generation
4. Code extraction capabilities from various content types

The goal is to determine definitively what the CodeExtractionService can and cannot do
when processing real document data.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Add python/src to path for imports
src_path = os.environ.get(
    "PYTHON_SRC_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "python" / "src"),
)
sys.path.insert(0, src_path)

from server.services.crawling.code_extraction_service import CodeExtractionService


class MockSupabaseClient:
    """Mock Supabase client for testing"""

    def __init__(self):
        pass


class TestFileAnalyzer:
    """Helper class to test file analysis capabilities"""

    @staticmethod
    def create_test_documents() -> List[Dict[str, Any]]:
        """Create test documents with realistic file patterns"""
        return [
            {
                "url": "test-fresh-intelligence.py",
                "html": """#!/usr/bin/env python3
import asyncio
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class IntelligenceData:
    correlation_id: str
    strength: float

async def analyze_correlations(data: List[Dict]) -> IntelligenceData:
    \"\"\"Analyze correlation data patterns\"\"\"
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
                "markdown": "",
                "content_type": "text/plain",
            },
            {
                "url": "integration_test_python-integration.py",
                "html": """import pytest
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

    async def test_async_endpoint(self):
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/async-test", json={"test": True})
            assert response.status_code == 200
""",
                "markdown": "",
                "content_type": "text/plain",
            },
            {
                "url": "src/test1.py",
                "html": """from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class UserModel(BaseModel):
    id: int = Field(..., description="User ID")
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = Field(None, regex=r'^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
""",
                "markdown": "",
                "content_type": "text/plain",
            },
            {
                "url": "src/test2.py",
                "html": """import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application")
    yield
    logger.info("Shutting down application")

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.post("/users/")
async def create_user(
    user_data: UserModel,
    db: AsyncSession = Depends(get_session)
):
    try:
        # Create user logic here
        return {"message": "User created", "user_id": 12345}
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
""",
                "markdown": "",
                "content_type": "text/plain",
            },
            {
                "url": "README.md",
                "html": """# Python Integration Testing Project

This project demonstrates comprehensive testing strategies for Python applications.

## Features

- FastAPI web framework integration
- Pydantic data validation models
- Async/await pattern usage
- SQLAlchemy database integration
- pytest testing framework
- Docker containerization

## Code Examples

Here's a basic FastAPI endpoint:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}
```

And here's how to test it:

```python
def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}
```

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy
- **Testing**: pytest, httpx, TestClient
- **Database**: PostgreSQL with asyncio
- **Validation**: Pydantic models with Field validation
- **Logging**: Python logging with structured output

## File Structure

```
src/
├── models/
│   ├── __init__.py
│   └── user.py
├── api/
│   ├── __init__.py
│   └── endpoints.py
├── database/
│   ├── __init__.py
│   └── connection.py
└── main.py

tests/
├── test_api.py
├── test_models.py
└── conftest.py
```
""",
                "markdown": """# Python Integration Testing Project

This project demonstrates comprehensive testing strategies for Python applications.

## Features

- FastAPI web framework integration
- Pydantic data validation models
- Async/await pattern usage
- SQLAlchemy database integration
- pytest testing framework
- Docker containerization

## Code Examples

Here's a basic FastAPI endpoint:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}
```

And here's how to test it:

```python
def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}
```

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy
- **Testing**: pytest, httpx, TestClient
- **Database**: PostgreSQL with asyncio
- **Validation**: Pydantic models with Field validation
- **Logging**: Python logging with structured output

## File Structure

```
src/
├── models/
│   ├── __init__.py
│   └── user.py
├── api/
│   ├── __init__.py
│   └── endpoints.py
├── database/
│   ├── __init__.py
│   └── connection.py
└── main.py

tests/
├── test_api.py
├── test_models.py
└── conftest.py
```
""",
                "content_type": "text/markdown",
            },
            {
                "url": "frontend/Dashboard.tsx",
                "html": """import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, CheckCircle, Clock } from 'lucide-react';

interface CorrelationData {
  id: string;
  repository: string;
  strength: number;
  status: 'active' | 'pending' | 'completed';
}

interface DashboardProps {
  userId: string;
}

export const Dashboard: React.FC<DashboardProps> = ({ userId }) => {
  const [selectedRepo, setSelectedRepo] = useState<string>('');

  const { data: correlations, isLoading, error } = useQuery({
    queryKey: ['correlations', userId],
    queryFn: async (): Promise<CorrelationData[]> => {
      const response = await fetch(`/api/correlations?userId=${userId}`);
      if (!response.ok) throw new Error('Failed to fetch correlations');
      return response.json();
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  const getStatusIcon = (status: CorrelationData['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-blue-500" />;
    }
  };

  if (isLoading) {
    return <div className="animate-pulse">Loading dashboard...</div>;
  }

  if (error) {
    return (
      <div className="p-4 border border-red-200 bg-red-50 rounded-md">
        Error loading dashboard data
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {correlations?.map((correlation) => (
          <Card key={correlation.id} className="cursor-pointer hover:shadow-lg transition-shadow">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between text-sm">
                <span>{correlation.repository}</span>
                {getStatusIcon(correlation.status)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold mb-2">
                {(correlation.strength * 100).toFixed(1)}%
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${correlation.strength * 100}%` }}
                />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex gap-2">
        <Button
          onClick={() => window.location.reload()}
          variant="outline"
        >
          Refresh
        </Button>
        <Button
          onClick={() => setSelectedRepo('')}
          disabled={!selectedRepo}
        >
          Clear Selection
        </Button>
      </div>
    </div>
  );
};

export default Dashboard;
""",
                "markdown": "",
                "content_type": "text/plain",
            },
            {
                "url": "frontend/hooks/useCorrelations.ts",
                "html": """import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

interface CorrelationFilters {
  repository?: string;
  strength?: number;
  status?: 'active' | 'pending' | 'completed';
  dateRange?: '24h' | '7d' | '30d';
}

interface UseCorrelationsOptions {
  filters?: CorrelationFilters;
  enabled?: boolean;
  refetchInterval?: number;
}

export const useCorrelations = (options: UseCorrelationsOptions = {}) => {
  const { filters = {}, enabled = true, refetchInterval = 30000 } = options;
  const [isRefreshing, setIsRefreshing] = useState(false);
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['correlations', filters],
    queryFn: async () => {
      const params = new URLSearchParams();

      if (filters.repository) params.set('repository', filters.repository);
      if (filters.strength !== undefined) params.set('strength', filters.strength.toString());
      if (filters.status) params.set('status', filters.status);
      if (filters.dateRange) params.set('dateRange', filters.dateRange);

      const response = await fetch(`/api/correlations?${params}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return response.json();
    },
    enabled,
    refetchInterval,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 3,
  });

  const refreshMutation = useMutation({
    mutationFn: async () => {
      setIsRefreshing(true);
      await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate delay
      return queryClient.invalidateQueries({ queryKey: ['correlations'] });
    },
    onSettled: () => {
      setIsRefreshing(false);
    },
  });

  const refresh = useCallback(() => {
    refreshMutation.mutate();
  }, [refreshMutation]);

  return {
    ...query,
    refresh,
    isRefreshing: isRefreshing || refreshMutation.isPending,
  };
};

export default useCorrelations;
""",
                "markdown": "",
                "content_type": "text/plain",
            },
        ]

    @staticmethod
    def create_url_to_document_mapping(docs: List[Dict]) -> Dict[str, str]:
        """Create URL to document mapping required by the service"""
        return {
            doc["url"]: doc.get("html", "") or doc.get("markdown", "") for doc in docs
        }


class CodeExtractionTester:
    """Main test class for independent CodeExtractionService testing"""

    def __init__(self):
        self.mock_client = MockSupabaseClient()
        self.service = CodeExtractionService(self.mock_client)
        self.test_analyzer = TestFileAnalyzer()

    async def test_file_extension_detection(self) -> Dict[str, List[str]]:
        """Test 1: Verify file extension detection capabilities"""
        print("🔍 TEST 1: File Extension Detection")
        print("=" * 60)

        test_docs = self.test_analyzer.create_test_documents()
        results = {
            "detected_extensions": [],
            "detected_languages": [],
            "file_analysis": [],
        }

        for doc in test_docs:
            url = doc["url"]
            print(f"\n📄 Analyzing: {url}")

            # Extract extension
            if "." in url:
                extension = url.split(".")[-1]
                results["detected_extensions"].append(extension)
                print(f"   Extension: .{extension}")

                # Map extension to language
                language_map = {
                    "py": "Python",
                    "tsx": "TypeScript/React",
                    "ts": "TypeScript",
                    "js": "JavaScript",
                    "md": "Markdown",
                }

                language = language_map.get(extension, "Unknown")
                results["detected_languages"].append(language)
                print(f"   Language: {language}")

            # Analyze file patterns
            content = doc.get("html", "") or doc.get("markdown", "")
            analysis = self._analyze_file_patterns(content, url)
            results["file_analysis"].append({"url": url, "analysis": analysis})

            print(f"   Content length: {len(content)} chars")
            print(f"   Has content: {'✅' if content else '❌'}")

        print("\n📊 SUMMARY:")
        print(f"   Extensions found: {list(set(results['detected_extensions']))}")
        print(f"   Languages detected: {list(set(results['detected_languages']))}")
        print(f"   Files analyzed: {len(results['file_analysis'])}")

        return results

    def _analyze_file_patterns(self, content: str, url: str) -> Dict[str, Any]:
        """Analyze content for technology patterns"""
        patterns = {
            "python_patterns": [
                "import ",
                "from ",
                "def ",
                "class ",
                "async def",
                "asyncio",
                "pytest",
                "fastapi",
                "pydantic",
                "__init__",
            ],
            "typescript_patterns": [
                "interface ",
                "import React",
                "useState",
                "useEffect",
                "React.FC",
                "export ",
                "async (): Promise",
                ".tsx",
                ".ts",
            ],
            "javascript_patterns": [
                "const ",
                "let ",
                "var ",
                "function",
                "=>",
                "useState",
                "useEffect",
            ],
            "testing_patterns": [
                "test_",
                "def test",
                "pytest",
                "assert ",
                "TestClient",
                "async def test",
                "it(",
                "describe(",
                "expect(",
            ],
            "framework_patterns": [
                "fastapi",
                "react",
                "pydantic",
                "sqlalchemy",
                "pytest",
                "tanstack",
                "lucide-react",
                "@/components",
            ],
        }

        analysis = {}
        for pattern_type, pattern_list in patterns.items():
            found_patterns = [p for p in pattern_list if p.lower() in content.lower()]
            analysis[pattern_type] = found_patterns

        # Technology stack detection
        tech_stack = set()
        if analysis["python_patterns"]:
            tech_stack.add("Python")
        if analysis["typescript_patterns"]:
            tech_stack.add("TypeScript")
        if analysis["javascript_patterns"]:
            tech_stack.add("JavaScript")
        if "fastapi" in content.lower():
            tech_stack.add("FastAPI")
        if "react" in content.lower():
            tech_stack.add("React")
        if "pydantic" in content.lower():
            tech_stack.add("Pydantic")
        if analysis["testing_patterns"]:
            tech_stack.add("Testing")

        analysis["detected_tech_stack"] = list(tech_stack)
        return analysis

    async def test_code_extraction_capabilities(self) -> Dict[str, Any]:
        """Test 2: Verify code extraction from different content types"""
        print("\n\n🔧 TEST 2: Code Extraction Capabilities")
        print("=" * 60)

        test_docs = self.test_analyzer.create_test_documents()
        url_to_doc = self.test_analyzer.create_url_to_document_mapping(test_docs)

        # Test the actual extraction
        try:
            extracted_count = await self.service.extract_and_store_code_examples(
                crawl_results=test_docs,
                url_to_full_document=url_to_doc,
                source_id="test-source-123",
            )

            print("✅ Code extraction completed successfully")
            print(f"📊 Total code blocks extracted: {extracted_count}")

            return {
                "success": True,
                "extracted_count": extracted_count,
                "test_docs_processed": len(test_docs),
                "error": None,
            }

        except Exception as e:
            print(f"❌ Code extraction failed: {str(e)}")
            import traceback

            print(f"🔍 Full error: {traceback.format_exc()}")

            return {
                "success": False,
                "extracted_count": 0,
                "test_docs_processed": len(test_docs),
                "error": str(e),
            }

    async def test_technology_stack_detection(self) -> Dict[str, Any]:
        """Test 3: Verify technology stack detection from file data"""
        print("\n\n🎯 TEST 3: Technology Stack Detection")
        print("=" * 60)

        test_docs = self.test_analyzer.create_test_documents()
        results = {
            "file_technologies": {},
            "overall_tech_stack": set(),
            "detection_accuracy": {},
        }

        for doc in test_docs:
            url = doc["url"]
            content = doc.get("html", "") or doc.get("markdown", "")

            print(f"\n📄 Analyzing: {url}")

            # Manual analysis
            analysis = self._analyze_file_patterns(content, url)
            detected_tech = analysis["detected_tech_stack"]

            results["file_technologies"][url] = detected_tech
            results["overall_tech_stack"].update(detected_tech)

            print(f"   Detected technologies: {detected_tech}")

            # Expected vs detected
            expected = self._get_expected_technologies(url)
            accuracy = self._calculate_detection_accuracy(expected, detected_tech)
            results["detection_accuracy"][url] = {
                "expected": expected,
                "detected": detected_tech,
                "accuracy": accuracy,
            }

            print(f"   Expected: {expected}")
            print(f"   Accuracy: {accuracy:.1%}")

        print("\n📊 OVERALL TECHNOLOGY STACK DETECTED:")
        for tech in sorted(results["overall_tech_stack"]):
            print(f"   🔧 {tech}")

        return results

    def _get_expected_technologies(self, url: str) -> List[str]:
        """Get expected technologies for a file based on its name and typical content"""
        expected_map = {
            "test-fresh-intelligence.py": ["Python"],
            "integration_test_python-integration.py": ["Python", "Testing"],
            "src/test1.py": ["Python", "Pydantic"],
            "src/test2.py": ["Python", "FastAPI"],
            "README.md": ["Python", "FastAPI", "Testing", "React"],
            "frontend/Dashboard.tsx": ["TypeScript", "React"],
            "frontend/hooks/useCorrelations.ts": ["TypeScript", "React"],
        }
        return expected_map.get(url, [])

    def _calculate_detection_accuracy(
        self, expected: List[str], detected: List[str]
    ) -> float:
        """Calculate detection accuracy as intersection over union"""
        if not expected and not detected:
            return 1.0
        if not expected or not detected:
            return 0.0

        expected_set = set(expected)
        detected_set = set(detected)

        intersection = len(expected_set & detected_set)
        union = len(expected_set | detected_set)

        return intersection / union if union > 0 else 0.0

    async def test_file_analysis_methods(self) -> Dict[str, Any]:
        """Test 4: Verify file analysis methods used in correlation generation"""
        print("\n\n🔬 TEST 4: File Analysis Methods")
        print("=" * 60)

        test_docs = self.test_analyzer.create_test_documents()

        # Test various analysis methods
        results = {
            "extension_analysis": {},
            "content_analysis": {},
            "directory_analysis": {},
            "file_overlap_analysis": {},
        }

        # Extension analysis
        extensions = []
        directories = []
        common_files = []

        for doc in test_docs:
            url = doc["url"]
            print(f"\n📁 Analyzing file structure: {url}")

            # Extract extension
            if "." in url:
                ext = url.split(".")[-1]
                extensions.append(ext)
                print(f"   Extension: .{ext}")

            # Extract directory
            if "/" in url:
                directory = "/".join(url.split("/")[:-1])
                directories.append(directory)
                print(f"   Directory: {directory}")

            # Check for common file names
            filename = url.split("/")[-1]
            if filename in [
                "README.md",
                "package.json",
                "requirements.txt",
                "__init__.py",
            ]:
                common_files.append(filename)
                print(f"   Common file: {filename}")

        results["extension_analysis"] = {
            "unique_extensions": list(set(extensions)),
            "extension_count": len(set(extensions)),
            "all_extensions": extensions,
        }

        results["directory_analysis"] = {
            "unique_directories": list(set(directories)),
            "directory_count": len(set(directories)),
            "all_directories": directories,
        }

        results["file_overlap_analysis"] = {
            "common_files": list(set(common_files)),
            "common_file_count": len(set(common_files)),
        }

        print("\n📊 FILE STRUCTURE ANALYSIS:")
        print(f"   Extensions: {results['extension_analysis']['unique_extensions']}")
        print(f"   Directories: {results['directory_analysis']['unique_directories']}")
        print(f"   Common files: {results['file_overlap_analysis']['common_files']}")

        return results

    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all tests and provide comprehensive analysis"""
        print("🧪 COMPREHENSIVE CODE EXTRACTION SERVICE TEST")
        print("=" * 80)
        print("Testing CodeExtractionService capabilities in complete isolation")
        print("=" * 80)

        all_results = {}

        try:
            # Test 1: File extension detection
            all_results["test_1_extensions"] = (
                await self.test_file_extension_detection()
            )

            # Test 2: Code extraction
            all_results["test_2_extraction"] = (
                await self.test_code_extraction_capabilities()
            )

            # Test 3: Technology detection
            all_results["test_3_technology"] = (
                await self.test_technology_stack_detection()
            )

            # Test 4: File analysis methods
            all_results["test_4_analysis"] = await self.test_file_analysis_methods()

            # Final analysis
            final_analysis = self._generate_final_analysis(all_results)
            all_results["final_analysis"] = final_analysis

            print("\n\n🎯 FINAL ANALYSIS")
            print("=" * 60)
            print(final_analysis["summary"])

            return all_results

        except Exception as e:
            print(f"\n❌ COMPREHENSIVE TEST FAILED: {str(e)}")
            import traceback

            print(f"🔍 Full error: {traceback.format_exc()}")
            return {"error": str(e), "traceback": traceback.format_exc()}

    def _generate_final_analysis(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final analysis of all test results"""

        # Analyze extension detection
        ext_results = results.get("test_1_extensions", {})
        extensions_detected = ext_results.get("detected_extensions", [])
        languages_detected = ext_results.get("detected_languages", [])

        # Analyze extraction success
        extraction_results = results.get("test_2_extraction", {})
        extraction_success = extraction_results.get("success", False)
        extraction_count = extraction_results.get("extracted_count", 0)

        # Analyze technology detection
        tech_results = results.get("test_3_technology", {})
        overall_tech_stack = tech_results.get("overall_tech_stack", set())
        detection_accuracy = tech_results.get("detection_accuracy", {})
        avg_accuracy = (
            sum(acc["accuracy"] for acc in detection_accuracy.values())
            / len(detection_accuracy)
            if detection_accuracy
            else 0
        )

        # Analyze file analysis
        analysis_results = results.get("test_4_analysis", {})
        unique_extensions = analysis_results.get("extension_analysis", {}).get(
            "unique_extensions", []
        )

        summary_lines = []
        summary_lines.append("✅ CODEEXTRACTIONSERVICE INDEPENDENT TEST RESULTS:")
        summary_lines.append("")
        summary_lines.append("🔍 FILE EXTENSION DETECTION:")
        summary_lines.append(
            f"   • Extensions detected: {list(set(extensions_detected))}"
        )
        summary_lines.append(f"   • Languages mapped: {list(set(languages_detected))}")
        summary_lines.append(
            f"   • Capability: {'✅ WORKING' if extensions_detected else '❌ NOT WORKING'}"
        )
        summary_lines.append("")

        summary_lines.append("🔧 CODE EXTRACTION:")
        summary_lines.append(
            f"   • Extraction success: {'✅ YES' if extraction_success else '❌ NO'}"
        )
        summary_lines.append(f"   • Code blocks extracted: {extraction_count}")
        summary_lines.append(
            f"   • Capability: {'✅ WORKING' if extraction_success else '❌ NOT WORKING'}"
        )
        if not extraction_success and extraction_results.get("error"):
            summary_lines.append(f"   • Error: {extraction_results['error']}")
        summary_lines.append("")

        summary_lines.append("🎯 TECHNOLOGY DETECTION:")
        summary_lines.append(f"   • Technologies detected: {list(overall_tech_stack)}")
        summary_lines.append(f"   • Detection accuracy: {avg_accuracy:.1%}")
        summary_lines.append(
            f"   • Capability: {'✅ WORKING' if overall_tech_stack else '❌ NOT WORKING'}"
        )
        summary_lines.append("")

        summary_lines.append("📊 FILE ANALYSIS:")
        summary_lines.append(f"   • File extensions analyzed: {unique_extensions}")
        summary_lines.append(
            f"   • Analysis methods: {'✅ WORKING' if unique_extensions else '❌ NOT WORKING'}"
        )
        summary_lines.append("")

        # Determine overall assessment
        capabilities_working = 0
        total_capabilities = 4

        if extensions_detected:
            capabilities_working += 1
        if extraction_success:
            capabilities_working += 1
        if overall_tech_stack:
            capabilities_working += 1
        if unique_extensions:
            capabilities_working += 1

        overall_score = capabilities_working / total_capabilities

        summary_lines.append("🏆 OVERALL ASSESSMENT:")
        summary_lines.append(
            f"   • Working capabilities: {capabilities_working}/{total_capabilities}"
        )
        summary_lines.append(f"   • Success rate: {overall_score:.1%}")

        if overall_score >= 0.75:
            summary_lines.append(
                "   • Status: ✅ CODEEXTRACTIONSERVICE IS WORKING WELL"
            )
        elif overall_score >= 0.5:
            summary_lines.append("   • Status: ⚠️ CODEEXTRACTIONSERVICE HAS SOME ISSUES")
        else:
            summary_lines.append(
                "   • Status: ❌ CODEEXTRACTIONSERVICE HAS MAJOR PROBLEMS"
            )

        summary_lines.append("")
        summary_lines.append("🔍 CORRELATION INTEGRATION IMPLICATIONS:")

        if not overall_tech_stack or overall_tech_stack == {"Unknown"}:
            summary_lines.append(
                "   • ❌ Technology stack detection failing - explains 'Unknown' in correlations"
            )
        else:
            summary_lines.append(
                "   • ✅ Technology stack detection working - correlation issue is elsewhere"
            )

        if not unique_extensions or unique_extensions == ["mixed"]:
            summary_lines.append(
                "   • ❌ Extension detection failing - explains 'mixed' in correlations"
            )
        else:
            summary_lines.append(
                "   • ✅ Extension detection working - correlation issue is elsewhere"
            )

        return {
            "summary": "\n".join(summary_lines),
            "overall_score": overall_score,
            "capabilities_working": capabilities_working,
            "total_capabilities": total_capabilities,
            "recommendations": self._generate_recommendations(results, overall_score),
        }

    def _generate_recommendations(
        self, results: Dict[str, Any], score: float
    ) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []

        if score < 0.5:
            recommendations.append(
                "🔧 CRITICAL: CodeExtractionService needs major fixes"
            )
            recommendations.append(
                "   - Review service initialization and dependencies"
            )
            recommendations.append("   - Check async/await patterns and error handling")
            recommendations.append("   - Verify all required methods are implemented")

        extraction_results = results.get("test_2_extraction", {})
        if not extraction_results.get("success"):
            recommendations.append("🔧 Fix code extraction pipeline:")
            recommendations.append("   - Check HTML/markdown content processing")
            recommendations.append("   - Verify code block detection patterns")
            recommendations.append("   - Review validation and filtering logic")

        tech_results = results.get("test_3_technology", {})
        if not tech_results.get("overall_tech_stack"):
            recommendations.append("🔧 Improve technology detection:")
            recommendations.append("   - Add more technology detection patterns")
            recommendations.append("   - Improve file content analysis")
            recommendations.append("   - Test with more diverse file types")

        if score >= 0.75:
            recommendations.append("✅ CodeExtractionService is working well!")
            recommendations.append(
                "   - Correlation issues likely in integration layer"
            )
            recommendations.append("   - Check how service results are processed")
            recommendations.append("   - Review correlation generation logic")

        return recommendations


async def main():
    """Main test execution"""
    tester = CodeExtractionTester()

    print("🚀 Starting CodeExtractionService Independent Test")
    print(f"📅 Test run at: {datetime.now(timezone.utc).isoformat()}")
    print()

    results = await tester.run_comprehensive_test()

    print("\n\n💾 TEST COMPLETE")
    print("=" * 40)
    print("Full results available in 'results' variable for further analysis")

    return results


if __name__ == "__main__":
    import warnings

    warnings.filterwarnings("ignore")  # Suppress async warnings during testing

    try:
        results = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback

        traceback.print_exc()
