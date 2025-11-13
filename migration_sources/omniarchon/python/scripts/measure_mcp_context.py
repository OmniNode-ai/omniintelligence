#!/usr/bin/env python3
"""
Token Measurement Script for Archon MCP Menu System PoC

This script measures the token usage of current MCP tool definitions versus
a proposed menu-based system to validate the 80%+ token reduction premise.

TRACK-1: Token Reduction Measurement & Validation (PREREQUISITE)
"""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tiktoken
except ImportError:
    print("Error: tiktoken is required. Install with: pip install tiktoken")
    sys.exit(1)


@dataclass
class ToolInfo:
    """Information about a single MCP tool"""

    name: str
    description: str
    parameters: dict
    file_path: str
    token_count: int = 0


@dataclass
class MeasurementResult:
    """Results of token measurement"""

    current_state_tokens: int
    menu_tool_tokens: int
    reduction_percentage: float
    tool_count: int
    tools: list[ToolInfo]
    go_no_go_decision: str
    decision_reason: str


class MCPTokenMeasurer:
    """Measures token usage for MCP tools"""

    def __init__(self):
        # Use cl100k_base encoding (same as GPT-4/Claude 3.5)
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.project_root = Path(__file__).parent.parent

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string"""
        return len(self.encoder.encode(text))

    def extract_tool_from_function(
        self, file_path: Path, function_text: str
    ) -> ToolInfo:
        """Extract tool information from a function definition"""
        # Extract function name
        name_match = re.search(r"async def (\w+)\(", function_text)
        if not name_match:
            name_match = re.search(r"def (\w+)\(", function_text)
        name = name_match.group(1) if name_match else "unknown"

        # Extract docstring
        docstring_match = re.search(r'"""(.*?)"""', function_text, re.DOTALL)
        description = docstring_match.group(1).strip() if docstring_match else ""

        # Extract parameters from function signature
        # Match both with and without return type annotations
        params_match = re.search(
            r"(?:async\s+def|def)\s+\w+\((.*?)\)\s*:", function_text, re.DOTALL
        )
        params_text = params_match.group(1) if params_match else ""

        # Parse parameters
        parameters = {}
        if params_text:
            # Simple parameter extraction (name: type pattern)
            param_matches = re.findall(r"(\w+):\s*([^,=\)]+)", params_text)
            for param_name, param_type in param_matches:
                if param_name != "ctx":  # Skip context parameter
                    parameters[param_name] = {"type": param_type.strip()}

        # Create tool schema similar to MCP format
        tool_schema = {
            "name": name,
            "description": description,
            "parameters": parameters,
        }

        # Calculate tokens for this tool
        tool_json = json.dumps(tool_schema, indent=2)
        token_count = self.count_tokens(tool_json)

        return ToolInfo(
            name=name,
            description=description,
            parameters=parameters,
            file_path=str(file_path.relative_to(self.project_root)),
            token_count=token_count,
        )

    def extract_tools_from_file(self, file_path: Path) -> list[ToolInfo]:
        """Extract all tools from a Python file"""
        tools = []

        try:
            content = file_path.read_text()

            # Find all @mcp.tool() decorated functions
            # Pattern: @mcp.tool() followed by async def or def
            pattern = r"@mcp\.tool\(\)(.*?)(async def|def) (\w+)\(.*?\).*?(?=@mcp\.tool\(\)|def register_|$)"
            matches = re.finditer(pattern, content, re.DOTALL)

            for match in matches:
                function_text = match.group(0)
                tool = self.extract_tool_from_function(file_path, function_text)
                tools.append(tool)

        except Exception as e:
            print(f"Warning: Error processing {file_path}: {e}")

        return tools

    def measure_current_tools(self) -> tuple[list[ToolInfo], int]:
        """Measure tokens for all current MCP tools"""
        print("📊 Measuring current MCP tool definitions...")

        all_tools = []

        # Directories to scan for MCP tools
        tool_dirs = [
            self.project_root / "src" / "mcp_server" / "features",
            self.project_root / "src" / "mcp_server" / "modules",
            self.project_root / "src" / "mcp_server" / "tools",
            self.project_root / "src" / "mcp_server" / "registry",
        ]

        # Also include the main server file
        main_server = self.project_root / "src" / "mcp_server" / "mcp_server.py"
        if main_server.exists():
            tools = self.extract_tools_from_file(main_server)
            all_tools.extend(tools)
            print(f"  ✓ Found {len(tools)} tools in mcp_server.py")

        # Scan all Python files in tool directories
        for tool_dir in tool_dirs:
            if not tool_dir.exists():
                continue

            for py_file in tool_dir.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue

                tools = self.extract_tools_from_file(py_file)
                if tools:
                    all_tools.extend(tools)
                    print(
                        f"  ✓ Found {len(tools)} tools in {py_file.relative_to(self.project_root)}"
                    )

        # Calculate total tokens
        total_tokens = sum(tool.token_count for tool in all_tools)

        return all_tools, total_tokens

    def design_menu_tool(self) -> dict:
        """Design the proposed menu-based tool schema"""
        menu_tool_schema = {
            "name": "archon_menu",
            "description": """
Navigate Archon's capabilities through an interactive menu system.

This tool provides organized access to all Archon MCP capabilities through
a hierarchical menu structure. Use this to explore available features and
execute specific operations.

Usage:
1. Call with no arguments to see the main menu
2. Call with menu_path to navigate to a specific category
3. Call with menu_path and operation to execute an operation

Main Categories:
- projects: Project management (create, list, update, delete)
- tasks: Task management (create, list, update, delete, status tracking)
- documents: Document management (create, list, update, delete)
- versions: Version control (create, list, restore)
- intelligence: AI-powered intelligence (quality, performance, freshness, patterns)
- research: Research and RAG (queries, code examples, search)
- vector: Vector search operations (search, index, optimize)
- cache: Cache management (invalidate, metrics, health)

Examples:
- archon_menu() → Shows main menu
- archon_menu(menu_path="tasks") → Shows task operations
- archon_menu(menu_path="tasks", operation="list", parameters={"filter_by": "status", "filter_value": "todo"})
- archon_menu(menu_path="research", operation="rag_query", parameters={"query": "ONEX architecture", "match_count": 5})
            """.strip(),
            "parameters": {
                "menu_path": {
                    "type": "string",
                    "description": "Path to menu category (e.g., 'tasks', 'research', 'intelligence')",
                    "optional": True,
                },
                "operation": {
                    "type": "string",
                    "description": "Specific operation to execute within the category",
                    "optional": True,
                },
                "parameters": {
                    "type": "object",
                    "description": "Parameters for the operation (JSON object)",
                    "optional": True,
                },
            },
        }

        return menu_tool_schema

    def measure_menu_tool(self) -> int:
        """Measure tokens for the proposed menu tool"""
        print("\n📊 Measuring proposed menu tool...")

        menu_schema = self.design_menu_tool()
        menu_json = json.dumps(menu_schema, indent=2)
        token_count = self.count_tokens(menu_json)

        print(f"  ✓ Menu tool schema: {token_count} tokens")

        return token_count

    def make_decision(self, reduction_percentage: float) -> tuple[str, str]:
        """Make GO/NO-GO decision based on reduction percentage"""
        if reduction_percentage >= 80.0:
            decision = "🟢 GO - PROCEED WITH IMPLEMENTATION"
            reason = f"Token reduction of {reduction_percentage:.1f}% exceeds 80% threshold. Menu system validation successful."
        elif reduction_percentage >= 70.0:
            decision = "🟡 INVESTIGATE - REVIEW REQUIRED"
            reason = (
                f"Token reduction of {reduction_percentage:.1f}% is below target but promising. "
                "Recommend architectural review before proceeding."
            )
        else:
            decision = "🔴 NO-GO - STOP AND REASSESS"
            reason = f"Token reduction of {reduction_percentage:.1f}% is below 70% threshold. Menu system does not provide sufficient benefits."

        return decision, reason

    def generate_report(self, result: MeasurementResult) -> str:
        """Generate comprehensive measurement report"""
        report = f"""
# Archon MCP Menu System - Token Reduction Validation Report
**TRACK-1: Token Reduction Measurement & Validation (PREREQUISITE)**

## Executive Summary

**Decision**: {result.go_no_go_decision}

**Token Reduction**: {result.reduction_percentage:.1f}% ({result.current_state_tokens:,} → {result.menu_tool_tokens:,} tokens)

**Reason**: {result.decision_reason}

## Detailed Measurements

### Current State
- **Total Tools**: {result.tool_count}
- **Total Tokens**: {result.current_state_tokens:,} tokens
- **Average per Tool**: {(result.current_state_tokens // result.tool_count) if result.tool_count else 0:,} tokens

### Proposed Menu System
- **Menu Tool**: 1 tool
- **Total Tokens**: {result.menu_tool_tokens:,} tokens
- **Token Reduction**: {result.current_state_tokens - result.menu_tool_tokens:,} tokens saved

### Token Reduction Analysis
- **Reduction Percentage**: {result.reduction_percentage:.1f}%
- **Tokens Saved**: {result.current_state_tokens - result.menu_tool_tokens:,}
- **Efficiency Gain**: {result.current_state_tokens / result.menu_tool_tokens:.1f}x

## Tool Breakdown

### Top 10 Most Token-Heavy Tools
"""

        # Sort tools by token count and show top 10
        sorted_tools = sorted(result.tools, key=lambda t: t.token_count, reverse=True)
        for i, tool in enumerate(sorted_tools[:10], 1):
            report += f"""
{i}. **{tool.name}** ({tool.token_count:,} tokens)
   - File: `{tool.file_path}`
   - Description: {tool.description[:100]}...
"""

        report += f"""

### Complete Tool List ({result.tool_count} tools)
"""

        # Group tools by category (based on file path)
        tools_by_category: dict[str, list[ToolInfo]] = {}
        for tool in result.tools:
            if "intelligence" in tool.file_path:
                category = "Intelligence"
            elif "rag_module" in tool.file_path or "search" in tool.file_path:
                category = "Research/Search"
            elif (
                "projects" in tool.file_path
                or "tasks" in tool.file_path
                or "documents" in tool.file_path
            ):
                category = "Project Management"
            elif "cache" in tool.file_path:
                category = "Cache"
            else:
                category = "Core"

            if category not in tools_by_category:
                tools_by_category[category] = []
            tools_by_category[category].append(tool)

        for category, tools in sorted(tools_by_category.items()):
            total_category_tokens = sum(t.token_count for t in tools)
            report += f"""
#### {category} ({len(tools)} tools, {total_category_tokens:,} tokens)
"""
            for tool in sorted(tools, key=lambda t: t.name):
                report += f"- {tool.name} ({tool.token_count:,} tokens)\n"

        report += f"""

## Menu Tool Design

The proposed menu system consolidates all {result.tool_count} tools into a single
navigable interface with hierarchical organization:

```json
{json.dumps(self.design_menu_tool(), indent=2)}
```

## Benefits Analysis

### Token Efficiency
- **{result.reduction_percentage:.1f}% reduction** in context window usage
- Frees up **{result.current_state_tokens - result.menu_tool_tokens:,} tokens** for:
  - Longer conversations
  - More complex prompts
  - Additional context
  - Improved reasoning

### Organizational Benefits
- **Single entry point** for all Archon capabilities
- **Progressive disclosure** of functionality
- **Reduced cognitive load** for users
- **Easier discovery** of available operations

### Architectural Benefits
- **Extensibility**: Add new operations without increasing token count
- **Maintainability**: Single tool definition to update
- **Consistency**: Uniform interface across all operations
- **Documentation**: Self-documenting through menu structure

## Next Steps

"""

        if "GO" in result.go_no_go_decision:
            report += f"""
### Recommended: Proceed to TRACK-2

With validated token reduction of {result.reduction_percentage:.1f}%, we recommend proceeding to:

1. **TRACK-2**: Menu Tool Implementation (Core)
2. **TRACK-3**: Operation Registry & Routing
3. **TRACK-4**: Testing & Validation
4. **TRACK-5**: Documentation & Migration

### Implementation Checklist
- [ ] Review menu tool design with stakeholders
- [ ] Create operation registry structure
- [ ] Implement menu navigation logic
- [ ] Build operation routing system
- [ ] Write comprehensive tests
- [ ] Update documentation
- [ ] Plan migration strategy

"""
        elif "INVESTIGATE" in result.go_no_go_decision:
            report += """
### Recommended: Architecture Review

Token reduction is promising but below target. Recommend:

1. Review menu tool design for optimization opportunities
2. Analyze token distribution across current tools
3. Consider hybrid approach (menu + high-frequency tools)
4. Re-validate with optimized design
5. Make final GO/NO-GO decision

### Investigation Areas
- [ ] Optimize menu tool description
- [ ] Analyze parameter complexity
- [ ] Consider tiered menu structure
- [ ] Evaluate partial migration strategy
- [ ] Re-measure with optimizations

"""
        else:
            report += """
### Recommended: Reassess Approach

Token reduction below threshold. Consider alternative approaches:

1. **Hybrid System**: Keep frequently-used tools, menu for rest
2. **Tool Consolidation**: Merge related tools without full menu
3. **Lazy Loading**: Load tool definitions on-demand
4. **Parameter Optimization**: Reduce parameter complexity
5. **Alternative Menu Design**: Explore different menu architectures

### Alternative Strategies
- [ ] Identify high-frequency tools to keep exposed
- [ ] Evaluate tool consolidation opportunities
- [ ] Research lazy-loading feasibility
- [ ] Prototype hybrid approaches
- [ ] Re-validate with best alternative

"""

        report += f"""

## Validation Metadata

- **Measurement Date**: {self._get_timestamp()}
- **Project**: Archon MCP Server
- **Task ID**: 1434d419-846c-4d86-9b3b-c81f01f08825
- **Track**: TRACK-1 (Token Reduction Measurement)
- **Encoder**: tiktoken cl100k_base
- **Python Version**: {sys.version.split()[0]}
- **Script**: {Path(__file__).name}

---

**Report Generated**: {self._get_timestamp()}
"""

        return report

    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime

        return datetime.now().isoformat()

    def run_measurement(self) -> MeasurementResult:
        """Run complete token measurement analysis"""
        print("🚀 Archon MCP Menu System - Token Reduction Validation")
        print("=" * 70)

        # Measure current tools
        tools, current_tokens = self.measure_current_tools()
        print(f"\n✓ Current state: {len(tools)} tools, {current_tokens:,} tokens")

        # Measure menu tool
        menu_tokens = self.measure_menu_tool()
        print(f"✓ Menu system: 1 tool, {menu_tokens:,} tokens")

        # Calculate reduction
        if current_tokens == 0:
            reduction_percentage = 0.0
        else:
            reduction_percentage = (
                (current_tokens - menu_tokens) / current_tokens
            ) * 100
        print(f"\n📊 Token Reduction: {reduction_percentage:.1f}%")

        # Make decision
        decision, reason = self.make_decision(reduction_percentage)
        print(f"\n{decision}")
        print(f"📝 {reason}")

        return MeasurementResult(
            current_state_tokens=current_tokens,
            menu_tool_tokens=menu_tokens,
            reduction_percentage=reduction_percentage,
            tool_count=len(tools),
            tools=tools,
            go_no_go_decision=decision,
            decision_reason=reason,
        )


def main():
    """Main entry point"""
    measurer = MCPTokenMeasurer()
    result = measurer.run_measurement()

    # Generate report
    print("\n" + "=" * 70)
    print("📄 Generating detailed report...")
    report = measurer.generate_report(result)

    # Save report
    report_dir = Path(__file__).parent.parent.parent / "docs" / "menu_poc"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_file = report_dir / "TRACK-1_token_reduction_report.md"
    report_file.write_text(report)

    print(f"✓ Report saved to: {report_file}")

    # Save JSON data
    json_file = report_dir / "TRACK-1_measurement_data.json"
    json_data = {
        "current_state_tokens": result.current_state_tokens,
        "menu_tool_tokens": result.menu_tool_tokens,
        "reduction_percentage": result.reduction_percentage,
        "tool_count": result.tool_count,
        "decision": result.go_no_go_decision,
        "reason": result.decision_reason,
        "tools": [
            {
                "name": tool.name,
                "token_count": tool.token_count,
                "file_path": tool.file_path,
                "description": tool.description[:200],
            }
            for tool in result.tools
        ],
    }
    json_file.write_text(json.dumps(json_data, indent=2))
    print(f"✓ JSON data saved to: {json_file}")

    # Print summary
    print("\n" + "=" * 70)
    print("📊 MEASUREMENT SUMMARY")
    print("=" * 70)
    print(
        f"Current State:  {result.current_state_tokens:>10,} tokens ({result.tool_count} tools)"
    )
    print(f"Menu System:    {result.menu_tool_tokens:>10,} tokens (1 tool)")
    print(f"Reduction:      {result.reduction_percentage:>10.1f}%")
    print(
        f"Tokens Saved:   {result.current_state_tokens - result.menu_tool_tokens:>10,} tokens"
    )
    print("=" * 70)
    print(f"\n{result.go_no_go_decision}")
    print(f"📝 {result.decision_reason}")
    print("\n" + "=" * 70)

    # Return exit code based on decision
    if "GO" in result.go_no_go_decision and "NO-GO" not in result.go_no_go_decision:
        return 0  # Success - proceed
    elif "INVESTIGATE" in result.go_no_go_decision:
        return 1  # Review required
    else:
        return 2  # Stop and reassess


if __name__ == "__main__":
    sys.exit(main())
