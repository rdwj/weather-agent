#!/usr/bin/env python3
"""
Command-line test for MCP weather tools.
Usage: python test_weather.py "Seattle" "WA"
       python test_weather.py "Austin" "Texas"
       python test_weather.py "New York"
"""

import asyncio
import sys
import json
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from src.core.base_agent import BaseAgent


class WeatherTestAgent(BaseAgent):
    """
    Simple weather test agent.
    """

    def __init__(self):
        # Your MCP server URL
        mcp_url = "https://mcp-server-weather-mcp.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/mcp/"

        super().__init__(
            name="WeatherTestAgent",
            description="Test agent for weather MCP tools",
            mcp_config=mcp_url
        )

    async def execute(self, input_data: dict) -> dict:
        """Not needed for this test."""
        return {"status": "test"}


async def test_weather(city: str, state: str = None):
    """
    Test weather lookup for a city.

    Args:
        city: City name
        state: Optional state name or code
    """
    print("=" * 70)
    print("MCP Weather Tool Test")
    print("=" * 70)

    # Create location string
    if state:
        location = f"{city}, {state}"
    else:
        location = city

    print(f"\n📍 Location: {location}")
    print("-" * 70)

    # Create agent
    agent = WeatherTestAgent()

    async with agent:
        # Connect to MCP
        print("\n🔌 Connecting to MCP server...")
        connected = await agent.connect_mcp()

        if not connected:
            print("❌ Failed to connect to MCP server")
            return

        print("✅ Connected successfully!")

        # Test 1: Direct weather lookup
        print(f"\n🌤️  Testing get_weather for '{location}'...")
        print("-" * 70)

        result = await agent.call_tool(
            "get_weather",
            {"location": location},
            raise_on_error=False
        )

        print(f"\n📊 Full Response:")
        print(json.dumps(result, indent=2, default=str))

        if result["success"]:
            print("\n✅ get_weather succeeded!")
            print("\n🌡️  Weather Data:")
            data = result["data"]
            if isinstance(data, dict):
                for key, value in data.items():
                    print(f"   {key}: {value}")
        else:
            print(f"\n⚠️  get_weather failed: {result['error']}")

            # Try geocoding first
            print(f"\n🗺️  Trying geocode_location for '{city}'...")

            geocode_args = {"city": city}
            if state:
                geocode_args["state"] = state

            geocode_result = await agent.call_tool(
                "geocode_location",
                geocode_args,
                raise_on_error=False
            )

            print(f"\n📊 Geocode Response:")
            print(json.dumps(geocode_result, indent=2, default=str))

            if geocode_result["success"]:
                coords = geocode_result["data"]
                print(f"\n📍 Coordinates found: lat={coords.get('lat')}, lon={coords.get('lon')}")

                # Now try with coordinates
                print(f"\n🌤️  Testing get_weather_from_coordinates...")

                weather_coords_result = await agent.call_tool(
                    "get_weather_from_coordinates",
                    {"lat": coords["lat"], "lon": coords["lon"]},
                    raise_on_error=False
                )

                print(f"\n📊 Weather from Coordinates Response:")
                print(json.dumps(weather_coords_result, indent=2, default=str))

                if weather_coords_result["success"]:
                    print("\n✅ get_weather_from_coordinates succeeded!")
                    print("\n🌡️  Weather Data:")
                    data = weather_coords_result["data"]
                    if isinstance(data, dict):
                        for key, value in data.items():
                            print(f"   {key}: {value}")
                else:
                    print(f"\n❌ get_weather_from_coordinates failed: {weather_coords_result['error']}")
            else:
                print(f"\n❌ geocode_location failed: {geocode_result['error']}")

        print("\n" + "=" * 70)


def main():
    """
    Main entry point.
    """
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python test_weather.py <city> [state]")
        print("\nExamples:")
        print('  python test_weather.py "Seattle" "WA"')
        print('  python test_weather.py "Austin" "Texas"')
        print('  python test_weather.py "New York"')
        print('  python test_weather.py "London"')
        sys.exit(1)

    city = sys.argv[1]
    state = sys.argv[2] if len(sys.argv) > 2 else None

    # Run the async test
    asyncio.run(test_weather(city, state))


if __name__ == "__main__":
    main()