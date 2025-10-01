#!/usr/bin/env python3
"""
Example usage of the BaseAgent class.

This module demonstrates how to use the BaseAgent class to simplify
agent development and LLM interactions.
"""

import asyncio
import logging
from typing import Dict, Any

from .base_agent import BaseAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherAnalysisAgent(BaseAgent):
    """
    Example agent that analyzes weather queries using the BaseAgent framework.
    """

    def __init__(self):
        super().__init__(
            name="WeatherAnalyst",
            description="An agent specialized in analyzing weather-related queries",
            system_prompt="You are a weather analysis expert. Help users understand weather patterns and conditions.",
            temperature=0.4
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a weather query and extract key information.

        Args:
            input_data: Should contain 'query' key with user's weather question

        Returns:
            Analysis results with extracted location, time, and intent
        """
        query = input_data.get("query", "")

        # Define extraction schema
        extraction_schema = {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The location mentioned in the query"
                },
                "temporal_context": {
                    "type": "string",
                    "enum": ["now", "today", "tomorrow", "week", "specific_date"],
                    "description": "When the user wants weather information for"
                },
                "weather_aspects": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["temperature", "precipitation", "wind", "humidity", "conditions", "alerts"]
                    },
                    "description": "What weather aspects the user is interested in"
                },
                "intent": {
                    "type": "string",
                    "enum": ["current", "forecast", "historical", "comparison", "alert_check"],
                    "description": "The primary intent of the query"
                }
            },
            "required": ["intent"]
        }

        # Extract structured information
        extracted = await self.extract(
            text=query,
            extraction_schema=extraction_schema,
            instructions="Extract weather-related information from the user's query. If location is not mentioned, leave it null."
        )

        # Generate a natural language response
        response = await self.think(
            f"User asked: {query}\n\nExtracted info: {extracted}\n\nProvide a brief acknowledgment of what they're asking for."
        )

        return {
            "success": True,
            "query": query,
            "extracted_info": extracted,
            "response": response,
            "agent_metrics": self.get_metrics()
        }


class DecisionMakingAgent(BaseAgent):
    """
    Example agent that makes decisions based on context.
    """

    def __init__(self):
        super().__init__(
            name="DecisionMaker",
            description="An agent that makes informed decisions based on available data",
            temperature=0.3
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a decision based on provided context and options.
        """
        question = input_data.get("question", "What should we do?")
        options = input_data.get("options", ["option1", "option2"])
        context = input_data.get("context", "")

        # Make a decision
        decision = await self.decide(
            question=question,
            options=options,
            context=context
        )

        return {
            "success": True,
            "decision": decision,
            "agent_metrics": self.get_metrics()
        }


class ReasoningAgent(BaseAgent):
    """
    Example agent that uses chain-of-thought reasoning.
    """

    def __init__(self):
        super().__init__(
            name="Reasoner",
            description="An agent that solves problems through step-by-step reasoning",
            temperature=0.4
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Solve a problem using chain-of-thought reasoning.
        """
        problem = input_data.get("problem", "")
        steps = input_data.get("reasoning_steps", 3)

        # Use chain-of-thought reasoning
        solution = await self.chain_thought(
            problem=problem,
            steps=steps
        )

        return {
            "success": True,
            "problem": problem,
            "solution": solution,
            "agent_metrics": self.get_metrics()
        }


async def example_basic_usage():
    """
    Demonstrate basic usage of the BaseAgent class.
    """
    print("\n=== Basic Agent Usage ===\n")

    # Create a simple agent
    agent = SimpleAgent(
        name="Assistant",
        description="A helpful assistant for general tasks"
    )

    # Execute a task
    result = await agent.execute({
        "task": "Explain the benefits of using a BaseAgent class",
        "context": "We're refactoring our codebase to reduce complexity"
    })

    print(f"Response: {result['response'][:200]}...")
    print(f"Metrics: {result['metrics']}")


async def example_weather_agent():
    """
    Demonstrate the weather analysis agent.
    """
    print("\n=== Weather Analysis Agent ===\n")

    agent = WeatherAnalysisAgent()

    # Analyze different weather queries
    queries = [
        "What's the weather like in Seattle today?",
        "Will it rain tomorrow in New York?",
        "Check for weather alerts in Miami"
    ]

    for query in queries:
        print(f"\nQuery: {query}")
        result = await agent.execute({"query": query})
        print(f"Extracted: {result['extracted_info']}")
        print(f"Response: {result['response'][:150]}...")


async def example_decision_agent():
    """
    Demonstrate the decision-making agent.
    """
    print("\n=== Decision Making Agent ===\n")

    agent = DecisionMakingAgent()

    result = await agent.execute({
        "question": "Which caching strategy should we use?",
        "options": ["Redis with TTL", "In-memory cache", "Database caching", "No caching"],
        "context": "We have a weather API with 1000 requests per minute, data changes every 15 minutes"
    })

    print(f"Decision: {result['decision']['selected_option']}")
    print(f"Reasoning: {result['decision']['reasoning']}")
    print(f"Confidence: {result['decision']['confidence']}")


async def example_reasoning_agent():
    """
    Demonstrate the reasoning agent.
    """
    print("\n=== Chain-of-Thought Reasoning Agent ===\n")

    agent = ReasoningAgent()

    result = await agent.execute({
        "problem": "How can we optimize our weather agent to handle 10x more traffic?",
        "reasoning_steps": 4
    })

    print(f"Problem: {result['problem']}")
    print(f"\nReasoning Steps:")
    for step in result['solution']['reasoning_steps']:
        print(f"  Step {step['step_number']}: {step['thought'][:100]}...")
    print(f"\nFinal Answer: {result['solution']['final_answer'][:200]}...")
    print(f"Confidence: {result['solution']['confidence']}")


async def example_with_context_manager():
    """
    Demonstrate using agent as a context manager.
    """
    print("\n=== Using Agent with Context Manager ===\n")

    async with SimpleAgent(name="ContextAgent") as agent:
        # Multiple calls within the context
        await agent.think("How does context management help with resource cleanup?")
        await agent.summarize("Long text about weather patterns...", max_length=50)

        # Metrics are automatically logged on exit
        print(f"Mid-session metrics: {agent.get_metrics()}")

    # Cleanup happens automatically


async def main():
    """
    Run all examples.
    """
    print("=" * 60)
    print("BaseAgent Class Usage Examples")
    print("=" * 60)

    # Note: These examples would need actual LLM client configuration
    # For demonstration, they show the structure and API

    try:
        await example_basic_usage()
        await example_weather_agent()
        await example_decision_agent()
        await example_reasoning_agent()
        await example_with_context_manager()
    except Exception as e:
        print(f"\nNote: Examples require configured LLM client. Error: {e}")
        print("\nTo run these examples:")
        print("1. Set up your LLM_URL and LLM_API_KEY environment variables")
        print("2. Ensure the LLM service is running")
        print("3. Run this script again")


if __name__ == "__main__":
    asyncio.run(main())