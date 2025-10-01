#!/usr/bin/env python3
"""
Complete examples demonstrating MCP tools, resources, and prompts in agents.

This module shows how agents can leverage all MCP capabilities including
tools, resources, and prompts for comprehensive functionality.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from .base_agent import BaseAgent, MCPConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigurableAgent(BaseAgent):
    """
    Agent that uses MCP resources for configuration and prompts for behavior.
    """

    def __init__(self, mcp_config: Optional[Any] = None):
        """
        Initialize agent with MCP capabilities.

        Args:
            mcp_config: MCP configuration
        """
        super().__init__(
            name="ConfigurableAgent",
            description="Agent that adapts behavior based on MCP resources and prompts",
            mcp_config=mcp_config
        )
        self.config: Optional[Dict[str, Any]] = None

    async def load_configuration(self) -> bool:
        """
        Load configuration from MCP resources.

        Returns:
            True if configuration loaded successfully
        """
        # List available resources
        resources = await self.list_resources()
        logger.info(f"Available resources: {len(resources)}")

        # Look for configuration resource
        config_resource = None
        for resource in resources:
            if "config" in resource.get("tags", []) or "settings" in resource["uri"]:
                config_resource = resource
                break

        if not config_resource:
            logger.warning("No configuration resource found")
            return False

        # Read configuration
        self.config = await self.read_json_resource(config_resource["uri"])

        if self.config:
            logger.info(f"Loaded configuration: {list(self.config.keys())}")
            return True

        return False

    async def get_custom_behavior(self, context: str) -> str:
        """
        Get behavior instructions from MCP prompts.

        Args:
            context: Current context

        Returns:
            Behavior instructions
        """
        # List available prompts
        prompts = await self.list_prompts()

        # Look for behavior prompt
        behavior_prompt = None
        for prompt in prompts:
            if "behavior" in prompt.get("tags", []) or "system" in prompt["name"]:
                behavior_prompt = prompt
                break

        if behavior_prompt:
            # Get system prompt with context
            system_prompt = await self.get_system_prompt_from_mcp(
                behavior_prompt["name"],
                {"context": context, "config": self.config}
            )
            return system_prompt or "Default behavior"

        return "No custom behavior available"

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task using configuration and prompts.
        """
        # Load configuration if not loaded
        if not self.config:
            await self.load_configuration()

        # Get custom behavior
        task = input_data.get("task", "")
        behavior = await self.get_custom_behavior(task)

        # Use behavior as system prompt for LLM
        response = await self.call_llm(
            prompt=f"Task: {task}",
            system_prompt=behavior
        )

        return {
            "task": task,
            "config_loaded": self.config is not None,
            "custom_behavior": behavior[:100] + "...",
            "response": response,
            "metrics": self.get_metrics()
        }


class DocumentProcessorAgent(BaseAgent):
    """
    Agent that processes documents using MCP resources.
    """

    def __init__(self, mcp_config: Optional[Any] = None):
        super().__init__(
            name="DocumentProcessor",
            description="Agent that reads and processes documents from MCP resources",
            mcp_config=mcp_config
        )

    async def process_all_documents(self) -> List[Dict[str, Any]]:
        """
        Process all available document resources.

        Returns:
            List of processed document summaries
        """
        # Get all resources
        resources = await self.list_resources()

        # Filter for document resources
        doc_resources = [
            r for r in resources
            if any(ext in r["uri"] for ext in [".txt", ".md", ".json", ".yaml"])
        ]

        logger.info(f"Found {len(doc_resources)} document resources")

        # Process each document
        results = []
        for resource in doc_resources:
            content = await self.read_resource(resource["uri"])

            if content and content.text:
                # Summarize the document
                summary = await self.summarize(
                    content.text,
                    max_length=100,
                    style="concise"
                )

                results.append({
                    "uri": resource["uri"],
                    "name": resource["name"],
                    "size": len(content.text),
                    "summary": summary
                })

        return results

    async def export_resources(self, output_dir: str) -> int:
        """
        Export all resources to local files.

        Args:
            output_dir: Directory to save resources

        Returns:
            Number of resources exported
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        resources = await self.list_resources()
        exported = 0

        for resource in resources:
            # Create safe filename from URI
            safe_name = resource["uri"].replace("://", "_").replace("/", "_")
            file_path = output_path / safe_name

            if await self.save_resource_to_file(resource["uri"], str(file_path)):
                exported += 1
                logger.info(f"Exported: {resource['uri']} -> {file_path}")

        return exported

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process documents based on input.
        """
        action = input_data.get("action", "list")

        if action == "process":
            summaries = await self.process_all_documents()
            return {
                "action": "process",
                "documents_processed": len(summaries),
                "summaries": summaries
            }

        elif action == "export":
            output_dir = input_data.get("output_dir", "./mcp_resources")
            exported = await self.export_resources(output_dir)
            return {
                "action": "export",
                "exported": exported,
                "output_dir": output_dir
            }

        else:
            # Just list resources
            resources = await self.list_resources()
            return {
                "action": "list",
                "resources": resources
            }


class PromptDrivenAgent(BaseAgent):
    """
    Agent that uses MCP prompts to structure all interactions.
    """

    def __init__(self, mcp_config: Optional[Any] = None):
        super().__init__(
            name="PromptDrivenAgent",
            description="Agent driven entirely by MCP prompt templates",
            mcp_config=mcp_config
        )

    async def run_conversation_flow(
        self,
        flow_name: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Run a conversation flow from MCP prompts.

        Args:
            flow_name: Name of the conversation flow prompt
            context: Context for the conversation

        Returns:
            List of conversation messages
        """
        # Get conversation template
        conversation = await self.get_conversation_from_mcp(flow_name, context)

        if not conversation:
            logger.warning(f"Conversation flow '{flow_name}' not found")
            return []

        # Process each message through LLM if needed
        processed_messages = []
        for msg in conversation:
            if msg["role"] == "assistant" and "{generate}" in msg["content"]:
                # Generate content using LLM
                generated = await self.think(
                    f"Context: {context}\nGenerate: {msg['content']}"
                )
                msg["content"] = generated

            processed_messages.append(msg)

        return processed_messages

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute using prompt-driven workflows.
        """
        workflow = input_data.get("workflow", "default")
        context = input_data.get("context", {})

        # List available prompts
        prompts = await self.list_prompts()
        available_workflows = [p["name"] for p in prompts]

        # Run the workflow
        if workflow in available_workflows:
            conversation = await self.run_conversation_flow(workflow, context)
            return {
                "workflow": workflow,
                "conversation": conversation,
                "success": True
            }
        else:
            return {
                "workflow": workflow,
                "error": f"Workflow not found. Available: {available_workflows}",
                "success": False
            }


class IntegratedMCPAgent(BaseAgent):
    """
    Agent that demonstrates full integration of tools, resources, and prompts.
    """

    def __init__(self, mcp_config: Optional[Any] = None):
        super().__init__(
            name="IntegratedMCPAgent",
            description="Fully integrated MCP agent using all capabilities",
            mcp_config=mcp_config
        )

    async def discover_capabilities(self) -> Dict[str, Any]:
        """
        Discover all MCP capabilities.

        Returns:
            Summary of available capabilities
        """
        # Discover all capabilities
        tools = await self.list_tools()
        resources = await self.list_resources()
        templates = await self.list_resource_templates()
        prompts = await self.list_prompts()

        return {
            "tools": {
                "count": len(tools),
                "names": [t["name"] for t in tools]
            },
            "resources": {
                "count": len(resources),
                "types": list(set(r.get("mime_type", "unknown") for r in resources))
            },
            "templates": {
                "count": len(templates),
                "names": [t["name"] for t in templates]
            },
            "prompts": {
                "count": len(prompts),
                "names": [p["name"] for p in prompts]
            }
        }

    async def execute_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complex workflow using all MCP capabilities.

        Args:
            workflow: Workflow specification

        Returns:
            Workflow execution results
        """
        results = {}

        # Step 1: Load configuration from resources
        if "config_resource" in workflow:
            config = await self.read_json_resource(workflow["config_resource"])
            results["config"] = config

        # Step 2: Get system prompt from MCP
        if "system_prompt" in workflow:
            system_prompt = await self.get_system_prompt_from_mcp(
                workflow["system_prompt"],
                workflow.get("prompt_args", {})
            )
            results["system_prompt"] = system_prompt

        # Step 3: Execute tools
        if "tools_to_run" in workflow:
            tool_results = {}
            for tool_spec in workflow["tools_to_run"]:
                tool_name = tool_spec["name"]
                tool_args = tool_spec.get("args", {})

                result = await self.call_tool(tool_name, tool_args)
                tool_results[tool_name] = result

            results["tool_results"] = tool_results

        # Step 4: Process with LLM using gathered context
        if "final_task" in workflow:
            response = await self.call_llm(
                prompt=workflow["final_task"],
                system_prompt=results.get("system_prompt")
            )
            results["final_response"] = response

        return results

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute integrated MCP operations.
        """
        action = input_data.get("action", "discover")

        if action == "discover":
            capabilities = await self.discover_capabilities()
            return {
                "action": "discover",
                "capabilities": capabilities
            }

        elif action == "workflow":
            workflow = input_data.get("workflow", {})
            results = await self.execute_workflow(workflow)
            return {
                "action": "workflow",
                "results": results
            }

        else:
            return {
                "action": action,
                "error": "Unknown action"
            }


async def example_configurable_agent():
    """
    Demonstrate configurable agent with resources and prompts.
    """
    print("\n=== Configurable Agent Example ===\n")

    agent = ConfigurableAgent()

    async with agent:
        # Load and use configuration
        result = await agent.execute({
            "task": "Process user request with custom configuration"
        })

        print(f"Configuration loaded: {result['config_loaded']}")
        print(f"Custom behavior: {result['custom_behavior']}")


async def example_document_processor():
    """
    Demonstrate document processing with resources.
    """
    print("\n=== Document Processor Example ===\n")

    agent = DocumentProcessorAgent()

    async with agent:
        # Process all documents
        result = await agent.execute({"action": "process"})

        print(f"Documents processed: {result['documents_processed']}")
        for summary in result.get("summaries", [])[:3]:
            print(f"  - {summary['name']}: {summary['summary'][:50]}...")

        # Export resources
        export_result = await agent.execute({
            "action": "export",
            "output_dir": "./exported_resources"
        })

        print(f"Exported {export_result['exported']} resources")


async def example_prompt_driven():
    """
    Demonstrate prompt-driven workflows.
    """
    print("\n=== Prompt-Driven Agent Example ===\n")

    agent = PromptDrivenAgent()

    async with agent:
        # Run a conversation flow
        result = await agent.execute({
            "workflow": "customer_support",
            "context": {
                "customer_name": "Alice",
                "issue": "Cannot access account",
                "priority": "high"
            }
        })

        if result["success"]:
            print("Conversation flow:")
            for msg in result.get("conversation", []):
                print(f"  {msg['role']}: {msg['content'][:100]}...")


async def example_integrated():
    """
    Demonstrate fully integrated MCP usage.
    """
    print("\n=== Integrated MCP Agent Example ===\n")

    agent = IntegratedMCPAgent()

    async with agent:
        # Discover capabilities
        discovery = await agent.execute({"action": "discover"})
        caps = discovery["capabilities"]

        print(f"MCP Server Capabilities:")
        print(f"  Tools: {caps['tools']['count']}")
        print(f"  Resources: {caps['resources']['count']}")
        print(f"  Templates: {caps['templates']['count']}")
        print(f"  Prompts: {caps['prompts']['count']}")

        # Execute complex workflow
        workflow_result = await agent.execute({
            "action": "workflow",
            "workflow": {
                "config_resource": "resource://config/settings.json",
                "system_prompt": "assistant_behavior",
                "prompt_args": {"role": "helpful"},
                "tools_to_run": [
                    {"name": "get_data", "args": {"type": "metrics"}},
                    {"name": "analyze", "args": {"data": "metrics"}}
                ],
                "final_task": "Summarize the analysis results"
            }
        })

        print(f"\nWorkflow completed: {workflow_result.get('results', {}).keys()}")


async def main():
    """
    Run all MCP capability examples.
    """
    print("=" * 60)
    print("MCP Complete Integration Examples")
    print("=" * 60)

    try:
        await example_configurable_agent()
        await example_document_processor()
        await example_prompt_driven()
        await example_integrated()

    except Exception as e:
        print(f"\nNote: Examples require MCP server configuration. Error: {e}")
        print("\nTo run these examples:")
        print("1. Configure an MCP server with tools, resources, and prompts")
        print("2. Set MCP_URL environment variable or pass configuration")
        print("3. Install fastmcp: pip install fastmcp")


if __name__ == "__main__":
    asyncio.run(main())