#!/usr/bin/env python3
"""
Demo script for Weather Agent API.

This script demonstrates all the capabilities of the Weather Agent.
"""

import asyncio
import aiohttp
import json
import os
from typing import Dict, Any


class WeatherAPIDemo:
    """Demo client for Weather API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def run_demo(self):
        """Run complete demo of all API endpoints."""
        async with aiohttp.ClientSession() as session:
            print("=" * 70)
            print("🌤️  WEATHER AGENT API DEMO")
            print("=" * 70)

            # 1. Health Check
            print("\n1️⃣  Health Check")
            print("-" * 70)
            async with session.get(f"{self.base_url}/health") as resp:
                health = await resp.json()
                print(f"✅ Status: {health['status']}")
                print(f"🔌 MCP Connected: {health['mcp_connected']}")
                print(f"🤖 LLM Available: {health['llm_available']}")

            # 2. Get Weather
            print("\n2️⃣  Get Weather for Multiple Cities")
            print("-" * 70)
            cities = ["Seattle, WA", "Austin, TX", "Miami, FL"]
            for city in cities:
                async with session.get(
                    f"{self.base_url}/weather",
                    params={"location": city}
                ) as resp:
                    weather = await resp.json()
                    if weather.get("success"):
                        data = weather["data"]
                        cached = "📦 (cached)" if weather.get("cached") else "🔄 (fresh)"
                        print(f"\n📍 {city} {cached}")
                        print(f"   🌡️  {data.get('temperature')}")
                        print(f"   ☁️  {data.get('conditions')}")
                        print(f"   💧 {data.get('humidity')}")

            # 3. Compare Locations
            print("\n3️⃣  Compare Weather Between Cities")
            print("-" * 70)
            async with session.post(
                f"{self.base_url}/weather/compare",
                json={"locations": cities}
            ) as resp:
                comparison = await resp.json()
                if comparison.get("success"):
                    print("✅ Comparison completed")
                    weather_data = comparison.get("weather_data", {})

                    # Find warmest and coolest
                    temps = {}
                    for loc, data in weather_data.items():
                        temp_str = data.get("temperature", "")
                        if temp_str:
                            # Extract Fahrenheit value
                            try:
                                temp_f = float(temp_str.split("°F")[0])
                                temps[loc] = temp_f
                            except:
                                pass

                    if temps:
                        warmest = max(temps, key=temps.get)
                        coolest = min(temps, key=temps.get)
                        print(f"   🔥 Warmest: {warmest} ({temps[warmest]}°F)")
                        print(f"   ❄️  Coolest: {coolest} ({temps[coolest]}°F)")

            # 4. Get Forecast
            print("\n4️⃣  Get 5-Day Forecast for Seattle")
            print("-" * 70)
            async with session.get(
                f"{self.base_url}/forecast",
                params={"location": "Seattle, WA", "days": 5}
            ) as resp:
                forecast = await resp.json()
                if forecast.get("success"):
                    print("✅ Forecast retrieved")
                    current = forecast.get("current", {})
                    print(f"   Current: {current.get('temperature')}, {current.get('conditions')}")
                    print(f"   Forecast: {forecast.get('forecast_text', 'N/A')[:100]}...")

            # 5. List Tools
            print("\n5️⃣  Available MCP Tools")
            print("-" * 70)
            async with session.get(f"{self.base_url}/tools") as resp:
                tools_resp = await resp.json()
                tools = tools_resp.get("tools", [])
                print(f"✅ Found {len(tools)} tools:")
                for tool in tools:
                    print(f"   🔧 {tool.get('name')}")

            # 6. Cache Statistics
            print("\n6️⃣  Cache Statistics")
            print("-" * 70)
            async with session.get(f"{self.base_url}/cache/stats") as resp:
                cache = await resp.json()
                print(f"📊 Cache Entries: {cache.get('entries', 0)}")
                print(f"📍 Cached Locations: {', '.join(cache.get('locations', []))}")
                print(f"⏱️  Cache Duration: {cache.get('cache_duration_minutes', 0)} minutes")

            # 7. Test Chat (if LLM configured)
            print("\n7️⃣  Chat Interface Test")
            print("-" * 70)
            if health.get("llm_available"):
                async with session.post(
                    f"{self.base_url}/chat",
                    json={"message": "What's the weather like in Portland?"}
                ) as resp:
                    chat = await resp.json()
                    if chat.get("success"):
                        print("✅ Chat response:")
                        print(f"   {chat.get('response', 'N/A')[:200]}...")
            else:
                print("⚠️  LLM not configured - chat features disabled")
                print("   To enable: Set LLM_URL and LLM_API_KEY in .env")

            print("\n" + "=" * 70)
            print("✅ DEMO COMPLETE")
            print("=" * 70)


async def main():
    """Main entry point."""
    # Check if API is running
    try:
        demo = WeatherAPIDemo()
        await demo.run_demo()
    except aiohttp.ClientConnectorError:
        print("❌ Could not connect to Weather API at http://localhost:8000")
        print("\nPlease start the API server first:")
        print("  python -m uvicorn src.api.weather_api:app --reload --port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())