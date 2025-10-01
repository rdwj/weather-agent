#!/usr/bin/env python3
"""
Simple test agent to verify MCP connection and tool listing.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from src.core.base_agent import BaseAgent

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestMCPAgent(BaseAgent):
    """
    Minimal test agent to verify MCP connection.
    """

    def __init__(self):
        # Your MCP server URL
        mcp_url = "https://mcp-server-weather-mcp.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/mcp/"

        super().__init__(
            name="TestMCPAgent",
            description="Test agent for MCP connection verification",
            mcp_config=mcp_url  # Pass URL directly, will auto-detect as HTTP
        )

    async def execute(self, input_data: dict) -> dict:
        """
        Not needed for this test, but required by BaseAgent abstract class.
        """
        return {"status": "test"}


async def test_mcp_connection():
    """
    Test MCP connection and list available tools.
    """
    print("=" * 60)
    print("MCP Connection Test")
    print("=" * 60)

    # Create test agent
    agent = TestMCPAgent()

    print(f"\n1. Agent created: {agent.name}")
    print(f"   MCP configured: {agent.has_mcp_capability()}")

    # Use context manager to handle connection lifecycle
    async with agent:
        print("\n2. Attempting to connect to MCP server...")
        print(f"   URL: {agent.mcp_config.source if agent.mcp_config else 'Not configured'}")

        # Try to explicitly connect
        try:
            connected = await agent.connect_mcp()
            print(f"   Connection attempt result: {connected}")
        except Exception as e:
            print(f"   Connection error: {e}")

        # Check connection status
        print(f"   Connected: {agent.is_mcp_connected()}")

        if agent.is_mcp_connected():
            print("\n3. Successfully connected to MCP server!")

            # List available tools
            print("\n4. Listing available tools...")
            tools = await agent.list_tools()

            if tools:
                print(f"\n   Found {len(tools)} tools:")
                print("   " + "-" * 50)

                for i, tool in enumerate(tools, 1):
                    print(f"\n   Tool {i}: {tool['name']}")
                    print(f"   Description: {tool.get('description', 'No description')}")

                    # Show parameters if available
                    if 'parameters' in tool:
                        print(f"   Parameters: {tool['parameters']}")

                    # Show tags if available
                    if 'tags' in tool:
                        print(f"   Tags: {tool['tags']}")
            else:
                print("\n   No tools found or failed to list tools")

            # Also try to list resources and prompts
            print("\n5. Checking for resources...")
            resources = await agent.list_resources()
            print(f"   Found {len(resources)} resources")

            print("\n6. Checking for prompts...")
            prompts = await agent.list_prompts()
            print(f"   Found {len(prompts)} prompts")

        else:
            print("\n   Failed to connect to MCP server")
            print("   Check the URL and ensure the server is running")

    print("\n7. Agent context closed, connection cleaned up")
    print("=" * 60)


async def test_tool_execution():
    """
    If tools are found, test executing one.
    """
    print("\n" + "=" * 60)
    print("Tool Execution Test")
    print("=" * 60)

    agent = TestMCPAgent()

    async with agent:
        # Ensure we're connected
        if not agent.is_mcp_connected():
            connected = await agent.connect_mcp()
            print(f"Connection result: {connected}")

        if agent.is_mcp_connected():
            tools = await agent.list_tools()

            if tools:
                # Try to find a simple tool to test
                test_tool = None
                for tool in tools:
                    # Look for a weather-related tool
                    if 'weather' in tool['name'].lower() or 'geocode' in tool['name'].lower():
                        test_tool = tool
                        break

                if test_tool:
                    print(f"\nTesting tool: {test_tool['name']}")

                    # Prepare test arguments based on tool name
                    test_args = {}
                    if 'geocode' in test_tool['name'].lower():
                        test_args = {"city": "Seattle"}
                    elif 'weather' in test_tool['name'].lower():
                        test_args = {"location": "Seattle"}

                    print(f"With arguments: {test_args}")

                    # Execute the tool
                    result = await agent.call_tool(
                        test_tool['name'],
                        test_args,
                        raise_on_error=False
                    )

                    if result['success']:
                        print(f"\nTool executed successfully!")
                        print(f"Result: {result['data']}")
                    else:
                        print(f"\nTool execution failed: {result['error']}")


async def main():
    """
    Run all tests.
    """
    try:
        # Test basic connection and tool listing
        await test_mcp_connection()

        # Test tool execution if connection works
        await test_tool_execution()

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Starting MCP connection test...")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {Path.cwd()}")
    print()

    asyncio.run(main())