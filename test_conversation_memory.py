#!/usr/bin/env python3
"""
Test script for conversation memory and weather report formatting.

This script tests:
1. Weather report formatting with LLM
2. Multi-turn conversation memory
3. Context retention across queries
"""

import asyncio
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.weather_agent import WeatherAgent


async def test_conversation_memory():
    """Test conversation memory with multi-turn dialogue."""
    print("=" * 70)
    print("TESTING CONVERSATION MEMORY & FORMATTING")
    print("=" * 70)

    # Initialize agent
    agent = WeatherAgent()
    initialized = await agent.initialize()

    if not initialized:
        print("❌ Agent initialization failed")
        return

    print("\n✅ Agent initialized successfully")
    print(f"   LLM Available: {agent.llm_client.is_available()}")
    print(f"   MCP Connected: {agent.is_mcp_connected()}")

    # Test 1: First query - get weather
    print("\n" + "=" * 70)
    print("TEST 1: Initial weather query")
    print("=" * 70)

    result1 = await agent.chat(
        message="What's the weather in Seattle, WA?"
    )

    print(f"\n✅ Response received")
    print(f"   Thread ID: {result1.get('thread_id')}")
    print(f"   Success: {result1.get('success')}")
    print(f"\nFormatted Response:")
    print("-" * 70)
    print(result1.get('response', 'No response'))
    print("-" * 70)

    thread_id = result1.get('thread_id')

    # Test 2: Follow-up query referencing previous context
    print("\n" + "=" * 70)
    print("TEST 2: Follow-up query (should remember Seattle)")
    print("=" * 70)

    result2 = await agent.chat(
        message="Now format that into a nice weather report",
        thread_id=thread_id
    )

    print(f"\n✅ Response received")
    print(f"   Thread ID: {result2.get('thread_id')}")
    print(f"   Success: {result2.get('success')}")
    print(f"\nFormatted Response:")
    print("-" * 70)
    print(result2.get('response', 'No response'))
    print("-" * 70)

    # Test 3: Another follow-up
    print("\n" + "=" * 70)
    print("TEST 3: Another follow-up (testing continued context)")
    print("=" * 70)

    result3 = await agent.chat(
        message="What about tomorrow?",
        thread_id=thread_id
    )

    print(f"\n✅ Response received")
    print(f"   Thread ID: {result3.get('thread_id')}")
    print(f"   Success: {result3.get('success')}")
    print(f"\nFormatted Response:")
    print("-" * 70)
    print(result3.get('response', 'No response'))
    print("-" * 70)

    # Test 4: Check thread summary
    print("\n" + "=" * 70)
    print("TEST 4: Thread summary")
    print("=" * 70)

    summary = agent._memory_manager.get_thread_summary(thread_id)
    print(f"\n✅ Thread Summary:")
    print(f"   Thread ID: {summary.get('thread_id')}")
    print(f"   Message Count: {summary.get('message_count')}")
    print(f"   Conversation Turns: {summary.get('conversation_turns')}")
    print(f"   Current Location: {summary.get('current_location')}")
    print(f"   Previous Locations: {summary.get('previous_locations')}")
    print(f"   Has Weather Data: {summary.get('has_weather_data')}")
    print(f"   Last Updated: {summary.get('last_updated')}")

    # Test 5: New thread (different location)
    print("\n" + "=" * 70)
    print("TEST 5: New conversation thread")
    print("=" * 70)

    result4 = await agent.chat(
        message="How's the weather in Austin, TX?"
    )

    print(f"\n✅ Response received")
    print(f"   Thread ID: {result4.get('thread_id')}")
    print(f"   Different from previous: {result4.get('thread_id') != thread_id}")
    print(f"\nFormatted Response:")
    print("-" * 70)
    print(result4.get('response', 'No response'))
    print("-" * 70)

    # Cleanup
    await agent.close()

    print("\n" + "=" * 70)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 70)


async def test_formatting_only():
    """Test just the weather report formatting."""
    print("=" * 70)
    print("TESTING WEATHER REPORT FORMATTING ONLY")
    print("=" * 70)

    # Initialize agent
    agent = WeatherAgent()
    initialized = await agent.initialize()

    if not initialized:
        print("❌ Agent initialization failed")
        return

    # Get weather data
    weather_result = await agent.get_weather("Portland, OR")

    if weather_result["success"]:
        print("\n✅ Weather data retrieved")
        print("\nRaw JSON:")
        print("-" * 70)
        import json
        print(json.dumps(weather_result["data"], indent=2))
        print("-" * 70)

        print("\nFormatted Narrative (from get_weather):")
        print("-" * 70)
        print(weather_result.get("narrative", "No narrative"))
        print("-" * 70)
    else:
        print(f"❌ Failed to get weather: {weather_result.get('error')}")

    await agent.close()


async def main():
    """Run tests."""
    import os

    # Check if LLM is configured
    if not os.getenv("LLM_URL"):
        print("\n⚠️  WARNING: LLM_URL not set in environment")
        print("   Formatting will use simple template instead of LLM")
        print("   Set LLM_URL and LLM_API_KEY in .env to test full formatting\n")

    # Run tests
    choice = input("Select test:\n1. Full conversation memory test\n2. Formatting only\n3. Both\n\nChoice (1/2/3): ").strip()

    if choice == "1":
        await test_conversation_memory()
    elif choice == "2":
        await test_formatting_only()
    elif choice == "3":
        await test_formatting_only()
        print("\n\n")
        await test_conversation_memory()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
