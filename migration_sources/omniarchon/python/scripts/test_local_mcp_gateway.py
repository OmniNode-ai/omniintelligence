#!/usr/bin/env python3
"""
Test Local MCP Server with External Gateway

This script tests the local MCP server running on port 8151
to verify external gateway initialization and tool discovery.
"""

import asyncio
import json

import httpx


async def test_mcp_discover():
    """Test the discover operation to trigger gateway initialization."""

    print("🧪 Testing Local MCP Server with External Gateway\n")
    print("=" * 60)

    # MCP server endpoint
    mcp_url = "http://localhost:8151/mcp"

    print(f"\n📡 Connecting to MCP server: {mcp_url}")

    # Create MCP request for discover operation
    # Using SSE initialization format
    mcp_init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Send initialize request
            print("\n🔌 Sending initialize request...")
            response = await client.post(
                mcp_url,
                json=mcp_init_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )

            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                init_result = response.json()
                print(f"   ✓ Initialized: {json.dumps(init_result, indent=2)[:200]}...")

            # Now call tools/call with archon_menu discover
            print("\n🔍 Calling archon_menu(operation='discover')...")
            tools_call_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "archon_menu",
                    "arguments": {"operation": "discover"},
                },
            }

            response = await client.post(
                mcp_url,
                json=tools_call_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()

                # Extract tool result
                if "result" in result:
                    tool_result = result["result"]

                    # Parse the content (it's a JSON string)
                    if isinstance(tool_result.get("content"), list):
                        for content_item in tool_result["content"]:
                            if content_item.get("type") == "text":
                                text_content = content_item.get("text", "")
                                try:
                                    parsed_result = json.loads(text_content)

                                    print("\n" + "=" * 60)
                                    print("📊 DISCOVERY RESULTS")
                                    print("=" * 60)

                                    # Internal tools
                                    if "internal_tool_count" in parsed_result:
                                        print(
                                            f"\n✅ Internal Tools: {parsed_result['internal_tool_count']}"
                                        )

                                    # External tools
                                    if "external_tool_count" in parsed_result:
                                        print(
                                            f"✅ External Tools: {parsed_result['external_tool_count']}"
                                        )
                                        print(
                                            f"   Services: {', '.join(parsed_result.get('external_services', []))}"
                                        )
                                    elif "external_tools_available" in parsed_result:
                                        print(
                                            f"⚠️  External Tools: {parsed_result['external_tools_available']}"
                                        )

                                    # Total operations
                                    if "total_operations" in parsed_result:
                                        print(
                                            f"\n🎯 Total Operations: {parsed_result['total_operations']}"
                                        )

                                    # Show external catalog (truncated)
                                    if "external_catalog" in parsed_result:
                                        external_catalog = parsed_result[
                                            "external_catalog"
                                        ]
                                        print("\n📋 External Catalog Preview:")
                                        print(
                                            external_catalog[:500] + "..."
                                            if len(external_catalog) > 500
                                            else external_catalog
                                        )

                                    # Show any errors
                                    if "external_tools_error" in parsed_result:
                                        print(
                                            f"\n❌ External Tools Error: {parsed_result['external_tools_error']}"
                                        )

                                    print("\n" + "=" * 60)

                                    # Save full result to file
                                    with open(
                                        "/tmp/mcp_discovery_result.json", "w"
                                    ) as f:
                                        json.dump(parsed_result, f, indent=2)
                                    print(
                                        "💾 Full results saved to: /tmp/mcp_discovery_result.json"
                                    )

                                except json.JSONDecodeError:
                                    print(
                                        f"\n⚠️  Could not parse result as JSON:\n{text_content[:500]}"
                                    )

                else:
                    print(
                        f"\n❌ Unexpected response format: {json.dumps(result, indent=2)[:500]}"
                    )
            else:
                print(f"\n❌ Request failed with status {response.status_code}")
                print(f"   Response: {response.text[:500]}")

    except httpx.ConnectError as e:
        print(f"\n❌ Connection Error: {e}")
        print("   Is the MCP server running on port 8151?")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_mcp_discover())
