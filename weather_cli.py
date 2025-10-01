#!/usr/bin/env python3
"""
CLI client for Weather Agent API.

This client provides a command-line interface to interact with
the Weather Agent REST API for testing and demonstration.
"""

import asyncio
import argparse
import json
import sys
from typing import Dict, Any, Optional
import aiohttp
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Rich console for formatted output
console = Console()


class WeatherAPIClient:
    """
    Client for Weather Agent API.
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize API client.

        Args:
            base_url: Base URL of the Weather API
        """
        self.base_url = base_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Enter async context."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self.session:
            await self.session.close()

    async def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        async with self.session.get(f"{self.base_url}/health") as resp:
            return await resp.json()

    async def get_weather(self, location: str, use_cache: bool = True) -> Dict[str, Any]:
        """Get weather for a location."""
        params = {"location": location, "use_cache": use_cache}
        async with self.session.get(f"{self.base_url}/weather", params=params) as resp:
            return await resp.json()

    async def analyze_weather(
        self,
        weather_data: Dict[str, Any],
        analysis_type: str = "general"
    ) -> Dict[str, Any]:
        """Analyze weather data."""
        payload = {
            "weather_data": weather_data,
            "analysis_type": analysis_type
        }
        async with self.session.post(
            f"{self.base_url}/weather/analyze",
            json=payload
        ) as resp:
            return await resp.json()

    async def compare_locations(self, locations: list) -> Dict[str, Any]:
        """Compare weather between locations."""
        payload = {"locations": locations}
        async with self.session.post(
            f"{self.base_url}/weather/compare",
            json=payload
        ) as resp:
            return await resp.json()

    async def get_forecast(self, location: str, days: int = 5) -> Dict[str, Any]:
        """Get weather forecast."""
        params = {"location": location, "days": days}
        async with self.session.get(f"{self.base_url}/forecast", params=params) as resp:
            return await resp.json()

    async def chat(
        self,
        message: str,
        history: Optional[list] = None
    ) -> Dict[str, Any]:
        """Send chat message."""
        payload = {
            "message": message,
            "conversation_history": history
        }
        async with self.session.post(f"{self.base_url}/chat", json=payload) as resp:
            return await resp.json()

    async def list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        async with self.session.get(f"{self.base_url}/tools") as resp:
            return await resp.json()

    async def clear_cache(self) -> Dict[str, Any]:
        """Clear weather cache."""
        async with self.session.post(f"{self.base_url}/cache/clear") as resp:
            return await resp.json()

    async def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self.session.get(f"{self.base_url}/cache/stats") as resp:
            return await resp.json()


def display_weather(data: Dict[str, Any]):
    """Display weather data in a formatted table."""
    weather = data.get("data", {})

    table = Table(title="🌤️  Weather Information")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    for key, value in weather.items():
        if key != "forecast":  # Skip long forecast text
            # Convert key to title case and ensure value is string
            table.add_row(str(key).replace("_", " ").title(), str(value))

    console.print(table)

    # Display forecast separately if present
    if "forecast" in weather:
        console.print(Panel(
            weather["forecast"],
            title="📅 Forecast",
            border_style="blue"
        ))

    # Show cache status
    if data.get("cached") is True:
        console.print(f"[dim]Data from cache (cached at: {data.get('cached_at')})[/dim]")


def display_analysis(data: Dict[str, Any]):
    """Display weather analysis."""
    analysis = data.get("analysis", "No analysis available")
    analysis_type = data.get("type", "general").title()

    console.print(Panel(
        analysis,
        title=f"🤖 {analysis_type} Analysis",
        border_style="green"
    ))


def display_comparison(data: Dict[str, Any]):
    """Display location comparison."""
    locations = data.get("locations", [])
    weather_data = data.get("weather_data", {})
    comparison = data.get("comparison", "No comparison available")

    # Display weather table
    table = Table(title="🌍 Location Weather Comparison")
    table.add_column("Location", style="cyan")
    table.add_column("Temperature", style="yellow")
    table.add_column("Conditions", style="white")
    table.add_column("Humidity", style="blue")

    for location in locations:
        if location in weather_data:
            weather = weather_data[location]
            table.add_row(
                location,
                str(weather.get("temperature", "N/A")),
                str(weather.get("conditions", "N/A")),
                str(weather.get("humidity", "N/A"))
            )

    console.print(table)

    # Display comparison analysis
    console.print(Panel(
        comparison,
        title="📊 Comparison Analysis",
        border_style="magenta"
    ))


def display_forecast(data: Dict[str, Any]):
    """Display forecast information."""
    location = data.get("location", "Unknown")
    current = data.get("current", {})
    forecast_text = data.get("forecast_text", "No forecast available")
    forecast_analysis = data.get("forecast_analysis", None)

    # Current conditions
    console.print(Panel(
        f"🌡️  Temperature: {current.get('temperature', 'N/A')}\n"
        f"☁️  Conditions: {current.get('conditions', 'N/A')}\n"
        f"💧 Humidity: {current.get('humidity', 'N/A')}\n"
        f"💨 Wind: {current.get('wind', 'N/A')}",
        title=f"Current Weather - {location}",
        border_style="cyan"
    ))

    # Forecast text
    console.print(Panel(
        forecast_text,
        title="📅 Official Forecast",
        border_style="blue"
    ))

    # LLM Analysis if available
    if forecast_analysis:
        console.print(Panel(
            forecast_analysis,
            title="🤖 AI Forecast Analysis",
            border_style="green"
        ))


async def interactive_chat(client: WeatherAPIClient):
    """Run interactive chat mode."""
    console.print(Panel(
        "💬 Weather Chat Mode\n"
        "Ask me anything about weather!\n"
        "Type 'exit' or 'quit' to leave chat mode.",
        title="Chat Interface",
        border_style="cyan"
    ))

    history = []

    while True:
        try:
            # Get user input
            message = console.input("\n[bold cyan]You:[/bold cyan] ")

            if message.lower() in ["exit", "quit"]:
                console.print("[yellow]Exiting chat mode...[/yellow]")
                break

            # Send message
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True
            ) as progress:
                progress.add_task("Thinking...", total=None)
                response = await client.chat(message, history)

            # Display response
            if response.get("success"):
                console.print(f"\n[bold green]Assistant:[/bold green] {response['response']}")

                # Update history
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": response['response']})

                # Show additional info if present
                if response.get("locations"):
                    console.print(f"[dim]Locations detected: {', '.join(response['locations'])}[/dim]")
                if response.get("intent"):
                    console.print(f"[dim]Intent: {response['intent']}[/dim]")
            else:
                console.print(f"[red]Error: {response.get('error', 'Unknown error')}[/red]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Chat interrupted.[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Weather Agent CLI - Test the Weather API"
    )

    parser.add_argument(
        "--api-url",
        default=os.getenv("WEATHER_API_URL", "http://localhost:8000"),
        help="Weather API base URL"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Health check
    subparsers.add_parser("health", help="Check API health")

    # Weather command
    weather_parser = subparsers.add_parser("weather", help="Get weather for location")
    weather_parser.add_argument("location", help="Location (e.g., 'Seattle, WA')")
    weather_parser.add_argument("--no-cache", action="store_true", help="Skip cache")
    weather_parser.add_argument("--analyze", action="store_true", help="Include analysis")
    weather_parser.add_argument(
        "--analysis-type",
        choices=["general", "safety", "activity", "travel"],
        default="general",
        help="Type of analysis"
    )

    # Forecast command
    forecast_parser = subparsers.add_parser("forecast", help="Get weather forecast")
    forecast_parser.add_argument("location", help="Location for forecast")
    forecast_parser.add_argument("--days", type=int, default=5, help="Number of days")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare weather locations")
    compare_parser.add_argument(
        "locations",
        nargs="+",
        help="Locations to compare (2-5 locations)"
    )

    # Chat command
    subparsers.add_parser("chat", help="Interactive chat mode")

    # Tools command
    subparsers.add_parser("tools", help="List available MCP tools")

    # Cache commands
    cache_parser = subparsers.add_parser("cache", help="Cache operations")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command")
    cache_subparsers.add_parser("clear", help="Clear cache")
    cache_subparsers.add_parser("stats", help="Show cache statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Create API client
    async with WeatherAPIClient(args.api_url) as client:
        try:
            if args.command == "health":
                with console.status("Checking health..."):
                    result = await client.health_check()

                console.print(Panel(
                    f"✅ Status: {result['status']}\n"
                    f"🔌 MCP Connected: {result['mcp_connected']}\n"
                    f"🤖 LLM Available: {result['llm_available']}\n"
                    f"📊 Cache Entries: {result['cache_stats']['entries']}",
                    title="API Health",
                    border_style="green"
                ))

            elif args.command == "weather":
                with console.status(f"Getting weather for {args.location}..."):
                    result = await client.get_weather(
                        args.location,
                        use_cache=not args.no_cache
                    )

                if result.get("success"):
                    display_weather(result)

                    # Optionally analyze
                    if args.analyze:
                        with console.status("Analyzing weather..."):
                            analysis = await client.analyze_weather(
                                result["data"],
                                args.analysis_type
                            )
                        if analysis.get("success"):
                            display_analysis(analysis)
                else:
                    console.print(f"[red]Error: {result.get('error')}[/red]")

            elif args.command == "forecast":
                with console.status(f"Getting forecast for {args.location}..."):
                    result = await client.get_forecast(args.location, args.days)

                if result.get("success"):
                    display_forecast(result)
                else:
                    console.print(f"[red]Error: {result.get('error')}[/red]")

            elif args.command == "compare":
                if len(args.locations) < 2:
                    console.print("[red]Need at least 2 locations to compare[/red]")
                    return

                with console.status("Comparing locations..."):
                    result = await client.compare_locations(args.locations)

                if result.get("success"):
                    display_comparison(result)
                else:
                    console.print(f"[red]Error: {result.get('error')}[/red]")

            elif args.command == "chat":
                await interactive_chat(client)

            elif args.command == "tools":
                with console.status("Fetching tools..."):
                    result = await client.list_tools()

                tools = result.get("tools", [])
                if tools:
                    table = Table(title="🔧 Available MCP Tools")
                    table.add_column("Tool", style="cyan")
                    table.add_column("Description", style="white")

                    for tool in tools:
                        table.add_row(
                            tool.get("name", "Unknown"),
                            tool.get("description", "No description")
                        )
                    console.print(table)
                else:
                    console.print("[yellow]No tools available[/yellow]")

            elif args.command == "cache":
                if args.cache_command == "clear":
                    with console.status("Clearing cache..."):
                        result = await client.clear_cache()
                    console.print(f"[green]{result.get('message', 'Cache cleared')}[/green]")

                elif args.cache_command == "stats":
                    with console.status("Getting cache stats..."):
                        result = await client.cache_stats()

                    console.print(Panel(
                        f"📊 Entries: {result.get('entries', 0)}\n"
                        f"📍 Locations: {', '.join(result.get('locations', []))}\n"
                        f"⏱️  Duration: {result.get('cache_duration_minutes', 15)} minutes",
                        title="Cache Statistics",
                        border_style="blue"
                    ))
                else:
                    console.print("[yellow]Use 'cache clear' or 'cache stats'[/yellow]")

        except aiohttp.ClientConnectorError:
            console.print(
                f"[red]❌ Could not connect to API at {args.api_url}[/red]\n"
                "[yellow]Make sure the API server is running:[/yellow]\n"
                "  python -m uvicorn src.api.weather_api:app --reload --port 8000"
            )
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    asyncio.run(main())