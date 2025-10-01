#!/usr/bin/env python3
"""
Example agents that demonstrate MCP tool usage with the BaseAgent class.

This module shows how to create agents that leverage MCP servers for
external capabilities like weather data, database access, and more.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

from .base_agent import BaseAgent, MCPConfig, MCPTransportType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherMCPAgent(BaseAgent):
    """
    Agent that uses MCP tools to fetch and analyze weather data.
    """

    def __init__(self, mcp_url: Optional[str] = None):
        """
        Initialize weather agent with MCP server connection.

        Args:
            mcp_url: Optional MCP server URL (defaults to environment variable)
        """
        super().__init__(
            name="WeatherMCPAgent",
            description="Agent that fetches and analyzes weather data using MCP tools",
            system_prompt="You are a weather assistant that helps users understand weather conditions and forecasts.",
            mcp_config=mcp_url  # Will auto-detect as HTTP transport
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process weather queries using MCP tools.

        Args:
            input_data: Should contain 'query' with the weather question

        Returns:
            Weather information and analysis
        """
        query = input_data.get("query", "")

        # First, extract location from the query
        extraction_schema = {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The location to get weather for"
                },
                "info_type": {
                    "type": "string",
                    "enum": ["current", "forecast", "alerts"],
                    "description": "Type of weather information requested"
                }
            },
            "required": ["location"]
        }

        # Use LLM to understand the query
        extracted = await self.extract(
            text=query,
            extraction_schema=extraction_schema
        )

        location = extracted.get("location", "unknown")
        info_type = extracted.get("info_type", "current")

        # Call MCP weather tool
        weather_result = await self.call_tool(
            "get_weather",
            {"location": location}
        )

        if not weather_result["success"]:
            # Fallback to geocoding if direct lookup fails
            logger.info(f"Direct weather lookup failed, trying geocoding for: {location}")

            # Try to geocode the location
            geocode_result = await self.call_tool(
                "geocode_location",
                {"city": location}
            )

            if geocode_result["success"]:
                coords = geocode_result["data"]
                # Get weather from coordinates
                weather_result = await self.call_tool(
                    "get_weather_from_coordinates",
                    {"lat": coords["lat"], "lon": coords["lon"]}
                )

        # Generate natural language response
        if weather_result["success"]:
            weather_data = weather_result["data"]
            response = await self.think(
                f"User asked: {query}\n\n"
                f"Weather data: {weather_data}\n\n"
                "Provide a helpful, natural response about the weather."
            )
        else:
            response = f"I'm sorry, I couldn't fetch weather data for {location}. Error: {weather_result['error']}"

        return {
            "success": weather_result["success"],
            "query": query,
            "location": location,
            "weather_data": weather_result.get("data"),
            "response": response,
            "agent_metrics": self.get_metrics()
        }

    async def get_forecast_with_alerts(self, location: str) -> Dict[str, Any]:
        """
        Get weather forecast and check for any alerts.

        Args:
            location: Location to check

        Returns:
            Forecast and alert information
        """
        # Get weather data
        weather_result = await self.call_tool(
            "get_weather",
            {"location": location}
        )

        if not weather_result["success"]:
            return {
                "success": False,
                "error": f"Could not fetch weather for {location}"
            }

        weather_data = weather_result["data"]

        # Analyze for potential alerts
        alert_keywords = ["warning", "watch", "advisory", "severe", "dangerous"]
        forecast_text = str(weather_data.get("forecast", ""))

        alerts = []
        for keyword in alert_keywords:
            if keyword.lower() in forecast_text.lower():
                alerts.append({
                    "type": keyword,
                    "description": forecast_text
                })
                break

        return {
            "success": True,
            "location": location,
            "current": weather_data.get("temperature"),
            "conditions": weather_data.get("conditions"),
            "forecast": weather_data.get("forecast"),
            "alerts": alerts,
            "has_alerts": len(alerts) > 0
        }


class MultiToolAgent(BaseAgent):
    """
    Agent that can use multiple MCP servers and tools.
    """

    def __init__(self, mcp_config: Optional[Dict] = None):
        """
        Initialize agent with multi-server MCP configuration.

        Args:
            mcp_config: MCP configuration dictionary
        """
        # Example multi-server configuration
        default_config = {
            "mcpServers": {
                "weather": {
                    "url": "https://weather-mcp.example.com/mcp",
                    "transport": "http"
                },
                "database": {
                    "command": "python",
                    "args": ["./db_server.py"],
                    "env": {"DB_URL": "postgresql://localhost/mydb"}
                }
            }
        }

        super().__init__(
            name="MultiToolAgent",
            description="Agent that coordinates multiple MCP servers",
            mcp_config=mcp_config or default_config
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task using multiple MCP tools.

        Args:
            input_data: Task specification

        Returns:
            Execution results from multiple tools
        """
        task = input_data.get("task", "")

        # List all available tools from all servers
        all_tools = await self.list_tools()

        logger.info(f"Available tools across all servers: {len(all_tools)}")
        for tool in all_tools:
            logger.info(f"  - {tool['name']}: {tool.get('description', 'N/A')}")

        # Decide which tool to use based on the task
        decision = await self.decide(
            question=f"Which tool should I use for this task: {task}",
            options=[tool["name"] for tool in all_tools],
            context=f"Available tools: {all_tools}"
        )

        selected_tool = decision["selected_option"]
        logger.info(f"Selected tool: {selected_tool} (confidence: {decision['confidence']})")

        # Execute the selected tool
        # Note: For multi-server configs, tool names are prefixed with server name
        result = await self.call_tool(selected_tool, input_data.get("arguments", {}))

        return {
            "task": task,
            "selected_tool": selected_tool,
            "reasoning": decision["reasoning"],
            "result": result,
            "metrics": self.get_metrics()
        }


class LocalMCPAgent(BaseAgent):
    """
    Agent that uses a local MCP server via STDIO transport.
    """

    def __init__(self, server_script: str, env_vars: Optional[Dict[str, str]] = None):
        """
        Initialize agent with local MCP server.

        Args:
            server_script: Path to the MCP server script
            env_vars: Environment variables for the server
        """
        mcp_config = MCPConfig(
            transport_type=MCPTransportType.STDIO,
            source=server_script,
            env=env_vars or {}
        )

        super().__init__(
            name="LocalMCPAgent",
            description="Agent using local MCP server via STDIO",
            mcp_config=mcp_config
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task using local MCP server.
        """
        # Connect to local server (launches subprocess)
        if not await self.connect_mcp():
            return {
                "success": False,
                "error": "Failed to connect to local MCP server"
            }

        # Discover and use tools
        tools = await self.list_tools()
        logger.info(f"Local server provides {len(tools)} tools")

        # Execute first available tool as demonstration
        if tools:
            first_tool = tools[0]["name"]
            result = await self.call_tool(
                first_tool,
                input_data.get("arguments", {})
            )
            return {
                "success": result["success"],
                "tool_used": first_tool,
                "result": result,
                "available_tools": [t["name"] for t in tools]
            }

        return {
            "success": False,
            "error": "No tools available from local server"
        }


class InMemoryMCPAgent(BaseAgent):
    """
    Agent that uses an in-memory FastMCP server (great for testing).
    """

    def __init__(self):
        """
        Initialize agent with in-memory MCP server.
        """
        # This would work if you have a FastMCP server instance
        # For demonstration, we're showing the structure
        super().__init__(
            name="InMemoryMCPAgent",
            description="Agent using in-memory MCP server for testing",
            # mcp_config would be a FastMCP instance:
            # mcp_config=my_fastmcp_server
        )

    async def setup_test_server(self):
        """
        Set up an in-memory test server.
        """
        try:
            from fastmcp import FastMCP

            # Create a test server
            mcp = FastMCP("TestServer")

            # Define a simple tool
            @mcp.tool
            def echo(message: str) -> str:
                """Echo the message back."""
                return f"Echo: {message}"

            @mcp.tool
            def calculate(a: float, b: float, operation: str = "add") -> float:
                """Perform calculation on two numbers."""
                operations = {
                    "add": a + b,
                    "subtract": a - b,
                    "multiply": a * b,
                    "divide": a / b if b != 0 else None
                }
                return operations.get(operation, a + b)

            # Update agent's MCP config
            self.mcp_config = MCPConfig(
                transport_type=MCPTransportType.IN_MEMORY,
                source=mcp
            )

            return True
        except ImportError:
            logger.error("FastMCP not installed")
            return False

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task using in-memory MCP server.
        """
        # Set up the test server
        if not await self.setup_test_server():
            return {"success": False, "error": "Could not set up test server"}

        # Connect to the in-memory server
        if not await self.connect_mcp():
            return {"success": False, "error": "Failed to connect to in-memory server"}

        # Test the echo tool
        echo_result = await self.call_tool(
            "echo",
            {"message": input_data.get("message", "Hello MCP!")}
        )

        # Test the calculate tool
        calc_result = await self.call_tool(
            "calculate",
            {
                "a": input_data.get("a", 10),
                "b": input_data.get("b", 5),
                "operation": input_data.get("operation", "add")
            }
        )

        return {
            "success": True,
            "echo_result": echo_result,
            "calc_result": calc_result,
            "metrics": self.get_metrics()
        }


async def example_weather_mcp():
    """
    Demonstrate weather agent with MCP tools.
    """
    print("\n=== Weather MCP Agent Example ===\n")

    # Assuming MCP_URL is set in environment
    agent = WeatherMCPAgent()

    async with agent:
        # Check available tools
        tools = await agent.list_tools()
        print(f"Available weather tools: {[t['name'] for t in tools]}")

        # Get weather for a location
        result = await agent.execute({
            "query": "What's the weather like in Seattle today?"
        })

        print(f"Query: {result['query']}")
        print(f"Location: {result['location']}")
        print(f"Response: {result['response'][:200]}...")

        # Get forecast with alerts
        forecast = await agent.get_forecast_with_alerts("Miami, FL")
        if forecast["has_alerts"]:
            print(f"⚠️ Weather alerts for {forecast['location']}!")


async def example_local_mcp():
    """
    Demonstrate local MCP server via STDIO.
    """
    print("\n=== Local MCP Agent Example ===\n")

    # Assuming you have a local MCP server script
    agent = LocalMCPAgent(
        server_script="python weather_mcp_server.py",
        env_vars={"LOG_LEVEL": "INFO"}
    )

    async with agent:
        result = await agent.execute({
            "arguments": {"location": "New York"}
        })

        if result["success"]:
            print(f"Available tools: {result.get('available_tools', [])}")
            print(f"Result: {result['result']}")


async def example_retry_logic():
    """
    Demonstrate retry logic for unreliable tools.
    """
    print("\n=== MCP Tool Retry Example ===\n")

    agent = WeatherMCPAgent()

    async with agent:
        # Call tool with automatic retry
        result = await agent.call_tool_with_retry(
            "get_weather",
            {"location": "London"},
            max_retries=3,
            retry_delay=2.0
        )

        if result["success"]:
            print("Successfully got weather after retries")
        else:
            print(f"Failed even after retries: {result['error']}")


async def main():
    """
    Run all MCP agent examples.
    """
    print("=" * 60)
    print("MCP Agent Examples")
    print("=" * 60)

    try:
        # Run examples
        await example_weather_mcp()
        await example_local_mcp()
        await example_retry_logic()

        # In-memory example
        in_memory_agent = InMemoryMCPAgent()
        async with in_memory_agent:
            result = await in_memory_agent.execute({
                "message": "Hello World!",
                "a": 15,
                "b": 25,
                "operation": "multiply"
            })
            print("\n=== In-Memory MCP Results ===")
            print(f"Echo: {result.get('echo_result', {}).get('data')}")
            print(f"Calculation: {result.get('calc_result', {}).get('data')}")

    except Exception as e:
        print(f"\nNote: Some examples require MCP server configuration. Error: {e}")
        print("\nTo run these examples:")
        print("1. Set MCP_URL environment variable to your MCP server")
        print("2. Or provide a local MCP server script")
        print("3. Install fastmcp: pip install fastmcp")


if __name__ == "__main__":
    asyncio.run(main())