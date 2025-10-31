#!/usr/bin/env python3
"""
Base Agent class that provides a simplified interface for LLM and MCP interactions.

This module provides a foundation for all agents in the system, standardizing
how they interact with language models and MCP servers while reducing complexity.
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from ..utilities.call_model import CallModel
from ..utilities.llm_client import LLMClient, get_llm_client
from .mcp_prompts import MCPPromptHandler, PromptResult

# Import MCP handlers
from .mcp_resources import MCPResourceHandler, ResourceContent

# Type checking imports to avoid circular dependencies
if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MCPTransportType(Enum):
    """Supported MCP transport types."""
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"
    IN_MEMORY = "in_memory"
    CONFIG = "config"


@dataclass
class MCPConfig:
    """Configuration for MCP client connection."""
    transport_type: MCPTransportType | None = None
    source: str | dict | Any | None = None  # URL, file path, FastMCP instance, or config dict
    headers: dict[str, str] | None = None
    env: dict[str, str] | None = None
    timeout: float = 30.0
    auth_token: str | None = None


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    Provides standardized LLM and MCP interaction patterns, logging, and error handling.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_retries: int = 3,
        llm_client: LLMClient | None = None,
        mcp_config: MCPConfig | str | dict | None = None
    ):
        """
        Initialize the base agent with LLM and optional MCP capabilities.

        Args:
            name: Unique identifier for the agent
            description: Human-readable description of agent's purpose
            system_prompt: Default system prompt for this agent
            temperature: Default temperature for LLM calls
            max_retries: Maximum retries for schema-validated calls
            llm_client: Optional custom LLM client (defaults to singleton)
            mcp_config: Optional MCP configuration (MCPConfig, URL string, file path, or config dict)
        """
        self.name = name
        self.description = description
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.temperature = temperature
        self.max_retries = max_retries

        # Initialize LLM client
        self.llm_client = llm_client or get_llm_client()
        self.model_caller = CallModel(self.llm_client, max_retries=max_retries)

        # Initialize MCP configuration
        self.mcp_config = self._parse_mcp_config(mcp_config)
        self._mcp_client: Any | None = None  # Will be fastmcp.Client when initialized
        self._mcp_tools: list[Any] = []
        self._mcp_connected = False

        # Initialize MCP handlers
        self._resource_handler: MCPResourceHandler | None = None
        self._prompt_handler: MCPPromptHandler | None = None

        # Metrics tracking
        self.call_count = 0
        self.error_count = 0
        self.total_tokens = 0
        self.mcp_tool_calls = 0
        self.mcp_prompt_calls = 0
        self.last_call_metadata: dict[str, Any] | None = None

        # MCP operation history for the current session
        self.tool_call_history: list[dict[str, Any]] = []
        self.prompt_call_history: list[dict[str, Any]] = []

        logger.info(f"Initialized agent '{name}': {description}")

    def _get_default_system_prompt(self) -> str:
        """
        Get the default system prompt for this agent.

        Returns:
            Default system prompt string
        """
        return f"You are {self.name}, a helpful AI assistant. {self.description}"

    def _parse_mcp_config(self, config: MCPConfig | str | dict | None) -> MCPConfig | None:
        """
        Parse MCP configuration from various formats.

        Args:
            config: MCP configuration in various formats

        Returns:
            Parsed MCPConfig or None
        """
        if config is None:
            # Try to get from environment variables
            mcp_url = os.getenv("MCP_URL")
            if mcp_url:
                return MCPConfig(
                    transport_type=MCPTransportType.HTTP,
                    source=mcp_url,
                    auth_token=os.getenv("MCP_TOKEN"),
                    timeout=float(os.getenv("MCP_TIMEOUT", "30"))
                )
            return None

        if isinstance(config, MCPConfig):
            return config

        if isinstance(config, str):
            # Auto-detect transport type from string
            if config.startswith(("http://", "https://")):
                return MCPConfig(
                    transport_type=MCPTransportType.HTTP,
                    source=config,
                    auth_token=os.getenv("MCP_TOKEN")
                )
            elif config.endswith((".py", ".js")):
                return MCPConfig(
                    transport_type=MCPTransportType.STDIO,
                    source=config
                )
            else:
                logger.warning(f"Could not determine MCP transport type from: {config}")
                return None

        if isinstance(config, dict):
            # Check if it's an MCP JSON config format
            if "mcpServers" in config:
                return MCPConfig(
                    transport_type=MCPTransportType.CONFIG,
                    source=config
                )
            # Otherwise treat as config parameters
            return MCPConfig(**config)

        logger.warning(f"Invalid MCP configuration type: {type(config)}")
        return None

    async def connect_mcp(self) -> bool:
        """
        Connect to the MCP server if configured.

        Returns:
            True if connected successfully, False otherwise
        """
        if self._mcp_connected:
            return True

        if not self.mcp_config:
            logger.debug(f"Agent '{self.name}' has no MCP configuration")
            return False

        try:
            # Import FastMCP only when needed
            from fastmcp import Client

            # Create client based on configuration
            if self.mcp_config.source:
                # Add authentication if configured
                kwargs = {}
                if self.mcp_config.timeout:
                    kwargs['timeout'] = self.mcp_config.timeout

                # Create client with appropriate transport
                if self.mcp_config.auth_token and self.mcp_config.transport_type == MCPTransportType.HTTP:
                    from fastmcp.auth import BearerAuth
                    kwargs['auth'] = BearerAuth(self.mcp_config.auth_token)

                if self.mcp_config.headers and self.mcp_config.transport_type == MCPTransportType.HTTP:
                    # Use StreamableHttpTransport with headers and SSL verification
                    from fastmcp.transports import StreamableHttpTransport

                    # Determine SSL verification strategy
                    # Priority: SSL_CERT_FILE env var > service CA > system bundle
                    verify_ssl = os.getenv("SSL_CERT_FILE")
                    if not verify_ssl:
                        # Try service CA (for internal OpenShift services)
                        service_ca = "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
                        if os.path.exists(service_ca):
                            verify_ssl = service_ca
                            logger.info(f"Using OpenShift service CA for SSL verification: {service_ca}")
                        else:
                            # Fall back to system CA bundle
                            verify_ssl = "/etc/pki/tls/certs/ca-bundle.crt"
                            logger.info(f"Using system CA bundle for SSL verification: {verify_ssl}")
                    else:
                        logger.info(f"Using SSL_CERT_FILE environment variable: {verify_ssl}")

                    transport = StreamableHttpTransport(
                        url=self.mcp_config.source,
                        headers=self.mcp_config.headers,
                        verify=verify_ssl
                    )
                    self._mcp_client = Client(transport, **kwargs)
                elif self.mcp_config.transport_type == MCPTransportType.STDIO and self.mcp_config.env:
                    # Use StdioTransport with environment variables
                    import shlex

                    from fastmcp.transports import StdioTransport

                    # Parse command from source
                    parts = shlex.split(self.mcp_config.source)
                    command = parts[0]
                    args = parts[1:] if len(parts) > 1 else []

                    transport = StdioTransport(
                        command=command,
                        args=args,
                        env=self.mcp_config.env
                    )
                    self._mcp_client = Client(transport, **kwargs)
                else:
                    # Let FastMCP auto-detect transport
                    self._mcp_client = Client(self.mcp_config.source, **kwargs)

                # Connect and discover tools
                await self._mcp_client.__aenter__()
                self._mcp_tools = await self._mcp_client.list_tools()
                self._mcp_connected = True

                # Initialize handlers with connected client
                self._resource_handler = MCPResourceHandler(self._mcp_client)
                self._prompt_handler = MCPPromptHandler(self._mcp_client)

                logger.info(f"Agent '{self.name}' connected to MCP with {len(self._mcp_tools)} tools")
                for tool in self._mcp_tools:
                    logger.debug(f"  Available tool: {tool.name}")

                return True

        except ImportError:
            logger.error("FastMCP is not installed. Install with: pip install fastmcp")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return False

    async def disconnect_mcp(self) -> None:
        """
        Disconnect from the MCP server if connected.
        """
        if self._mcp_client and self._mcp_connected:
            try:
                await self._mcp_client.__aexit__(None, None, None)
                logger.info(f"Agent '{self.name}' disconnected from MCP")
            except Exception as e:
                logger.warning(f"Error disconnecting from MCP: {e}")
            finally:
                self._mcp_connected = False
                self._mcp_tools = []

    async def list_tools(self, filter_tags: list[str] | None = None) -> list[dict[str, Any]]:
        """
        List available MCP tools, optionally filtered by tags.

        Args:
            filter_tags: Optional list of tags to filter by (e.g., ['analysis', 'weather'])

        Returns:
            List of tool descriptions with name, description, parameters, and tags
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return []

        tools_list = []
        for tool in self._mcp_tools:
            # Extract tags
            tool_tags = []
            if hasattr(tool, 'meta') and tool.meta:
                fastmcp_meta = tool.meta.get('_fastmcp', {})
                tool_tags = fastmcp_meta.get('tags', [])

            # Apply tag filter if specified
            if filter_tags:
                if not any(tag in tool_tags for tag in filter_tags):
                    continue

            tool_info = {
                "name": tool.name,
                "description": getattr(tool, 'description', 'No description available')
            }

            # Add input schema if available
            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                tool_info["parameters"] = tool.inputSchema

            # Add tags if available (FastMCP metadata)
            if tool_tags:
                tool_info["tags"] = tool_tags

            tools_list.append(tool_info)

        return tools_list

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float | None = None,
        raise_on_error: bool = True,
        progress_handler: Callable | None = None
    ) -> dict[str, Any]:
        """
        Call an MCP tool using FastMCP client.

        FastMCP provides automatic type hydration in result.data, converting JSON
        to complete Python objects (datetime, UUID, custom classes). Primitive
        results (int, str, bool) are automatically unwrapped from {"result": value}.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments (optional)
            timeout: Override timeout for this call (optional)
            raise_on_error: Whether to raise exception on tool errors
            progress_handler: Optional callback for progress updates on long-running tasks

        Returns:
            Tool execution result with 'success', 'data', and optional 'error' keys.
            The 'data' field contains hydrated Python objects from FastMCP.
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return {
                    "success": False,
                    "error": "MCP server not connected",
                    "data": None
                }

        try:
            from fastmcp.exceptions import ToolError

            # Track metrics
            self.mcp_tool_calls += 1
            start_time = datetime.utcnow()

            logger.debug(f"Agent '{self.name}' calling tool '{tool_name}' with args: {arguments}")

            # Call the tool
            result = await self._mcp_client.call_tool(
                tool_name,
                arguments or {},
                timeout=timeout or self.mcp_config.timeout if self.mcp_config else 30.0,
                raise_on_error=raise_on_error,
                progress_handler=progress_handler
            )

            # Track timing
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.debug(f"Tool '{tool_name}' completed in {duration:.2f}s")

            # Track tool call in history
            tool_call_record = {
                "timestamp": start_time.isoformat(),
                "tool_name": tool_name,
                "arguments": arguments or {},
                "duration": duration,
                "success": True,
                "result": result
            }
            self.tool_call_history.append(tool_call_record)

            # Process result
            if result.is_error:
                error_msg = "Tool execution failed"
                if result.content and len(result.content) > 0:
                    if hasattr(result.content[0], 'text'):
                        error_msg = result.content[0].text

                return {
                    "success": False,
                    "error": error_msg,
                    "data": None
                }

            # Extract data from result
            # FastMCP provides fully hydrated Python objects in .data
            response_data = None
            if result.data is not None:
                # FastMCP provides hydrated Python objects - trust it!
                response_data = result.data

                # Convert Pydantic models to dicts for API compatibility
                if hasattr(response_data, 'model_dump'):
                    # Pydantic v2
                    response_data = response_data.model_dump()
                elif hasattr(response_data, 'dict'):
                    # Pydantic v1
                    response_data = response_data.dict()
                # Handle Root objects from MCP protocol (these need dict conversion for compatibility)
                elif hasattr(response_data, '__dict__') and not isinstance(response_data, (str, int, float, bool, list, dict)):
                    # Convert object to dict if it has __dict__ but isn't a basic type
                    try:
                        response_data = {k: v for k, v in response_data.__dict__.items() if not k.startswith('_')}
                    except Exception:
                        # If conversion fails, keep as-is
                        pass
                # For all other types (int, str, datetime, UUID, etc.) keep as-is

            elif result.structured_content:
                # Fallback to structured JSON
                response_data = result.structured_content
            else:
                # Fallback to text content
                text_content = []
                for content in result.content:
                    if hasattr(content, 'text'):
                        text_content.append(content.text)
                if text_content:
                    response_data = {"text": " ".join(text_content)}

            return {
                "success": True,
                "data": response_data,
                "error": None
            }

        except ToolError as e:
            logger.error(f"Tool '{tool_name}' failed with ToolError: {e}")

            # Track failed tool call in history
            duration = (datetime.utcnow() - start_time).total_seconds()
            tool_call_record = {
                "timestamp": start_time.isoformat(),
                "tool_name": tool_name,
                "arguments": arguments or {},
                "duration": duration,
                "success": False,
                "error": str(e),
                "result": None
            }
            self.tool_call_history.append(tool_call_record)

            return {
                "success": False,
                "error": str(e),
                "data": None
            }
        except Exception as e:
            logger.error(f"Unexpected error calling tool '{tool_name}': {e}")

            # Track failed tool call in history
            duration = (datetime.utcnow() - start_time).total_seconds()
            tool_call_record = {
                "timestamp": start_time.isoformat(),
                "tool_name": tool_name,
                "arguments": arguments or {},
                "duration": duration,
                "success": False,
                "error": str(e),
                "result": None
            }
            self.tool_call_history.append(tool_call_record)

            return {
                "success": False,
                "error": str(e),
                "data": None
            }

    def clear_tool_call_history(self) -> None:
        """Clear the tool call history."""
        self.tool_call_history = []

    def get_tool_call_history(self) -> list[dict[str, Any]]:
        """
        Get the current tool call history.

        Returns:
            List of tool call records
        """
        return self.tool_call_history.copy()

    def clear_prompt_call_history(self) -> None:
        """Clear the prompt call history."""
        self.prompt_call_history = []

    def get_prompt_call_history(self) -> list[dict[str, Any]]:
        """
        Get the current prompt call history.

        Returns:
            List of prompt call records
        """
        return self.prompt_call_history.copy()

    def get_mcp_history(self) -> dict[str, list[dict[str, Any]]]:
        """
        Get the complete MCP operation history including both tools and prompts.

        Returns:
            Dictionary with 'tools' and 'prompts' keys containing respective histories
        """
        return {
            "tools": self.tool_call_history.copy(),
            "prompts": self.prompt_call_history.copy()
        }

    def clear_mcp_history(self) -> None:
        """Clear both tool and prompt call histories."""
        self.tool_call_history = []
        self.prompt_call_history = []

    async def get_tool_by_name(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get detailed information about a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool information or None if not found
        """
        tools = await self.list_tools()
        for tool in tools:
            if tool["name"] == tool_name:
                return tool
        return None

    async def call_tool_with_retry(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> dict[str, Any]:
        """
        Call an MCP tool with automatic retry on failure.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments (optional)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            Tool execution result
        """
        last_error = None
        for attempt in range(max_retries):
            if attempt > 0:
                await asyncio.sleep(retry_delay * attempt)  # Exponential backoff
                logger.info(f"Retrying tool '{tool_name}' (attempt {attempt + 1}/{max_retries})")

            result = await self.call_tool(tool_name, arguments, raise_on_error=False)

            if result["success"]:
                return result

            last_error = result["error"]
            logger.warning(f"Tool '{tool_name}' failed on attempt {attempt + 1}: {last_error}")

        return {
            "success": False,
            "error": f"Failed after {max_retries} attempts. Last error: {last_error}",
            "data": None
        }

    async def call_tool_mcp(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None
    ) -> Any:
        """
        Call an MCP tool and return the raw MCP protocol result.

        This bypasses FastMCP's automatic deserialization and returns the raw
        mcp.types.CallToolResult. Useful for debugging or special cases where
        you need complete control over result processing.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments (optional)

        Returns:
            Raw mcp.types.CallToolResult object or None if not connected
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return None

        try:
            return await self._mcp_client.call_tool_mcp(tool_name, arguments or {})
        except Exception as e:
            logger.error(f"Raw MCP tool call failed for '{tool_name}': {e}")
            return None

    def has_mcp_capability(self) -> bool:
        """
        Check if this agent has MCP capabilities configured.

        Returns:
            True if MCP is configured, False otherwise
        """
        return self.mcp_config is not None

    def is_mcp_connected(self) -> bool:
        """
        Check if currently connected to MCP server.

        Returns:
            True if connected, False otherwise
        """
        return self._mcp_connected

    # Resource Operations

    async def list_resources(self) -> list[dict[str, Any]]:
        """
        List all static resources available on the MCP server.

        Returns:
            List of resource descriptions
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return []

        if self._resource_handler:
            return await self._resource_handler.list_resources()
        return []

    async def list_resource_templates(self) -> list[dict[str, Any]]:
        """
        List all resource templates available on the MCP server.

        Returns:
            List of template descriptions
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return []

        if self._resource_handler:
            return await self._resource_handler.list_resource_templates()
        return []

    async def read_resource(self, uri: str) -> ResourceContent | None:
        """
        Read content from a resource URI.

        Args:
            uri: Resource URI to read

        Returns:
            ResourceContent object or None if failed
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return None

        if self._resource_handler:
            return await self._resource_handler.read_resource(uri)
        return None

    async def read_json_resource(self, uri: str) -> dict[str, Any] | None:
        """
        Read a JSON resource and parse it.

        Args:
            uri: Resource URI to read

        Returns:
            Parsed JSON as dictionary or None if failed
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return None

        if self._resource_handler:
            return await self._resource_handler.read_json_resource(uri)
        return None

    async def save_resource_to_file(self, uri: str, file_path: str) -> bool:
        """
        Read a resource and save it to a file.

        Args:
            uri: Resource URI to read
            file_path: Path to save the resource content

        Returns:
            True if successful, False otherwise
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return False

        if self._resource_handler:
            return await self._resource_handler.save_resource_to_file(uri, file_path)
        return False

    # Prompt Operations

    async def list_prompts(self) -> list[dict[str, Any]]:
        """
        List all available prompt templates on the MCP server.

        Returns:
            List of prompt descriptions
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return []

        if self._prompt_handler:
            return await self._prompt_handler.list_prompts()
        return []

    async def get_prompt(
        self,
        prompt_name: str,
        arguments: dict[str, Any] | None = None
    ) -> PromptResult:
        """
        Get a rendered prompt with arguments.

        Args:
            prompt_name: Name of the prompt template
            arguments: Arguments to pass to the prompt

        Returns:
            PromptResult with generated messages
        """
        # Track metrics
        self.mcp_prompt_calls += 1
        start_time = datetime.utcnow()

        if not self._mcp_connected:
            if not await self.connect_mcp():
                error_result = PromptResult(
                    prompt_name=prompt_name,
                    messages=[],
                    arguments_used={},
                    success=False,
                    error="MCP server not connected"
                )

                # Track failed prompt call
                duration = (datetime.utcnow() - start_time).total_seconds()
                prompt_call_record = {
                    "timestamp": start_time.isoformat(),
                    "prompt_name": prompt_name,
                    "arguments": arguments or {},
                    "duration": duration,
                    "success": False,
                    "error": "MCP server not connected",
                    "messages": []
                }
                self.prompt_call_history.append(prompt_call_record)

                return error_result

        result = None
        if self._prompt_handler:
            result = await self._prompt_handler.get_prompt(prompt_name, arguments)
        else:
            result = PromptResult(
                prompt_name=prompt_name,
                messages=[],
                arguments_used={},
                success=False,
                error="Prompt handler not initialized"
            )

        # Track timing and result
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.debug(f"Prompt '{prompt_name}' completed in {duration:.2f}s")

        # Track prompt call in history
        prompt_call_record = {
            "timestamp": start_time.isoformat(),
            "prompt_name": prompt_name,
            "arguments": arguments or {},
            "duration": duration,
            "success": result.success,
            "error": result.error if not result.success else None,
            "messages": [{"role": m.role, "content": m.content[:200] + "..." if len(m.content) > 200 else m.content} for m in result.messages] if result.messages else []
        }
        self.prompt_call_history.append(prompt_call_record)

        return result

    async def get_system_prompt_from_mcp(
        self,
        prompt_name: str,
        arguments: dict[str, Any] | None = None
    ) -> str | None:
        """
        Get a system prompt message from an MCP prompt template.

        Args:
            prompt_name: Name of the prompt template
            arguments: Arguments to pass to the prompt

        Returns:
            System message content or None if not found
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return None

        if self._prompt_handler:
            return await self._prompt_handler.get_system_prompt(prompt_name, arguments)
        return None

    async def get_conversation_from_mcp(
        self,
        prompt_name: str,
        arguments: dict[str, Any] | None = None
    ) -> list[dict[str, str]]:
        """
        Get a conversation template from MCP as a list of messages.

        Args:
            prompt_name: Name of the prompt template
            arguments: Arguments to pass to the prompt

        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        if not self._mcp_connected:
            if not await self.connect_mcp():
                return []

        if self._prompt_handler:
            return await self._prompt_handler.get_conversation_template(prompt_name, arguments)
        return []

    async def call_llm(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs
    ) -> dict | str | tuple[dict | None, list[dict], bool]:
        """
        Call the LLM with automatic error handling and metrics tracking.

        Args:
            prompt: The user prompt
            schema: Optional JSON schema for structured output
            system_prompt: Override default system prompt
            temperature: Override default temperature
            **kwargs: Additional arguments for the LLM

        Returns:
            LLM response (format depends on schema parameter)
        """
        # Use agent defaults if not specified
        system_prompt = system_prompt or self.system_prompt
        temperature = temperature if temperature is not None else self.temperature

        # Track metrics
        self.call_count += 1
        start_time = datetime.utcnow()

        try:
            logger.debug(f"Agent '{self.name}' calling LLM (call #{self.call_count})")

            # Make the call through our unified interface
            result = await self.model_caller.call(
                prompt=prompt,
                schema=schema,
                system_prompt=system_prompt,
                temperature=temperature,
                **kwargs
            )

            # Track success metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(success=True, duration=duration)

            return result

        except Exception as e:
            # Track error metrics
            self.error_count += 1
            duration = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(success=False, duration=duration, error=str(e))

            logger.error(f"Agent '{self.name}' LLM call failed: {e}")
            raise

    async def think(
        self,
        context: str,
        temperature: float | None = None
    ) -> str:
        """
        Have the agent "think" about a context and return unstructured thoughts.

        This is useful for reasoning, analysis, or generating ideas.

        Args:
            context: The context to think about
            temperature: Override temperature for creative thinking

        Returns:
            Agent's thoughts as a string
        """
        prompt = f"Consider the following context and provide your analysis:\n\n{context}"

        result = await self.call_llm(
            prompt=prompt,
            temperature=temperature or 0.7,  # Higher temp for creative thinking
            return_raw=True
        )

        return result if isinstance(result, str) else str(result)

    async def decide(
        self,
        question: str,
        options: list[str],
        context: str | None = None
    ) -> dict[str, Any]:
        """
        Have the agent make a decision between options.

        Args:
            question: The decision question
            options: List of available options
            context: Optional context for decision-making

        Returns:
            Structured decision response
        """
        schema = {
            "type": "object",
            "properties": {
                "selected_option": {
                    "type": "string",
                    "enum": options
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation for the decision"
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confidence level (0-1)"
                }
            },
            "required": ["selected_option", "reasoning", "confidence"]
        }

        prompt = f"Question: {question}\n\nOptions:\n"
        for i, option in enumerate(options, 1):
            prompt += f"{i}. {option}\n"

        if context:
            prompt += f"\nContext:\n{context}\n"

        prompt += "\nPlease select the best option and explain your reasoning."

        result, history, success = await self.call_llm(
            prompt=prompt,
            schema=schema,
            temperature=0.3  # Low temp for consistent decisions
        )

        if not success:
            raise ValueError("Failed to get valid decision from LLM")

        return result

    async def extract(
        self,
        text: str,
        extraction_schema: dict[str, Any],
        instructions: str | None = None
    ) -> dict[str, Any]:
        """
        Extract structured information from unstructured text.

        Args:
            text: The text to extract from
            extraction_schema: JSON schema defining the extraction structure
            instructions: Optional specific extraction instructions

        Returns:
            Extracted information matching the schema
        """
        prompt = f"Extract information from the following text:\n\n{text}"

        if instructions:
            prompt += f"\n\nExtraction Instructions:\n{instructions}"

        result, history, success = await self.call_llm(
            prompt=prompt,
            schema=extraction_schema,
            temperature=0.1  # Very low temp for accurate extraction
        )

        if not success:
            raise ValueError("Failed to extract information from text")

        return result

    async def summarize(
        self,
        text: str,
        max_length: int | None = None,
        style: str = "concise"
    ) -> str:
        """
        Summarize text with specified constraints.

        Args:
            text: Text to summarize
            max_length: Optional maximum length in words
            style: Summary style (concise, detailed, bullet_points)

        Returns:
            Summarized text
        """
        prompt = f"Summarize the following text in a {style} manner:\n\n{text}"

        if max_length:
            prompt += f"\n\nLimit the summary to approximately {max_length} words."

        if style == "bullet_points":
            prompt += "\n\nFormat as bullet points."

        result = await self.call_llm(
            prompt=prompt,
            temperature=0.3,
            return_raw=True
        )

        return result if isinstance(result, str) else str(result)

    async def chain_thought(
        self,
        problem: str,
        steps: int | None = None
    ) -> dict[str, Any]:
        """
        Use chain-of-thought reasoning to solve a problem.

        Args:
            problem: The problem to solve
            steps: Optional number of reasoning steps

        Returns:
            Structured reasoning response
        """
        schema = {
            "type": "object",
            "properties": {
                "reasoning_steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_number": {"type": "integer"},
                            "thought": {"type": "string"},
                            "conclusion": {"type": "string"}
                        },
                        "required": ["step_number", "thought", "conclusion"]
                    }
                },
                "final_answer": {
                    "type": "string",
                    "description": "The final answer or solution"
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["reasoning_steps", "final_answer", "confidence"]
        }

        prompt = f"Solve the following problem using step-by-step reasoning:\n\n{problem}"

        if steps:
            prompt += f"\n\nUse approximately {steps} reasoning steps."

        prompt += "\n\nThink through this step-by-step, showing your reasoning at each stage."

        result, history, success = await self.call_llm(
            prompt=prompt,
            schema=schema,
            temperature=0.4
        )

        if not success:
            raise ValueError("Failed to complete chain-of-thought reasoning")

        return result

    def _update_metrics(
        self,
        success: bool,
        duration: float,
        error: str | None = None
    ):
        """
        Update internal metrics tracking.

        Args:
            success: Whether the call was successful
            duration: Call duration in seconds
            error: Optional error message
        """
        self.last_call_metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "duration": duration,
            "error": error,
            "agent": self.name
        }

        if success:
            logger.debug(f"Agent '{self.name}' call completed in {duration:.2f}s")
        else:
            logger.warning(f"Agent '{self.name}' call failed after {duration:.2f}s: {error}")

    def get_metrics(self) -> dict[str, Any]:
        """
        Get agent performance metrics.

        Returns:
            Dictionary of performance metrics
        """
        success_rate = (
            (self.call_count - self.error_count) / self.call_count
            if self.call_count > 0 else 0
        )

        metrics = {
            "agent_name": self.name,
            "total_calls": self.call_count,
            "error_count": self.error_count,
            "success_rate": success_rate,
            "last_call": self.last_call_metadata
        }

        # Add MCP metrics if available
        if self.has_mcp_capability():
            metrics["mcp"] = {
                "connected": self._mcp_connected,
                "tool_calls": self.mcp_tool_calls,
                "prompt_calls": self.mcp_prompt_calls,
                "available_tools": len(self._mcp_tools)
            }

        return metrics

    async def validate_response(
        self,
        response: Any,
        validation_rules: dict[str, Any] | None = None
    ) -> bool:
        """
        Validate an LLM response against custom rules.

        Args:
            response: The response to validate
            validation_rules: Optional custom validation rules

        Returns:
            True if valid, False otherwise
        """
        if validation_rules:
            # Apply custom validation logic
            for rule_name, rule_func in validation_rules.items():
                if callable(rule_func):
                    if not rule_func(response):
                        logger.warning(f"Validation failed for rule: {rule_name}")
                        return False

        return True

    @abstractmethod
    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the main agent logic.

        This method must be implemented by all concrete agent classes.

        Args:
            input_data: Input data for the agent

        Returns:
            Agent execution results
        """
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        # Disconnect MCP if connected
        await self.disconnect_mcp()

        if self.call_count > 0 or self.mcp_tool_calls > 0 or self.mcp_prompt_calls > 0:
            metrics = self.get_metrics()
            log_msg = f"Agent '{self.name}' session complete: "

            if self.call_count > 0:
                log_msg += f"{metrics['total_calls']} LLM calls, {metrics['success_rate']:.1%} success rate"

            if self.mcp_tool_calls > 0 or self.mcp_prompt_calls > 0:
                if self.call_count > 0:
                    log_msg += ", "

                mcp_parts = []
                if self.mcp_tool_calls > 0:
                    mcp_parts.append(f"{self.mcp_tool_calls} tool calls")
                if self.mcp_prompt_calls > 0:
                    mcp_parts.append(f"{self.mcp_prompt_calls} prompt calls")

                log_msg += f"MCP: {', '.join(mcp_parts)}"

            logger.info(log_msg)


class SimpleAgent(BaseAgent):
    """
    A simple concrete implementation of BaseAgent for basic tasks.
    """

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute simple agent logic.

        Args:
            input_data: Should contain 'task' and 'context' keys

        Returns:
            Execution results
        """
        task = input_data.get("task", "process input")
        context = input_data.get("context", "")

        # Use the agent's thinking capability
        response = await self.think(f"Task: {task}\nContext: {context}")

        return {
            "success": True,
            "response": response,
            "agent": self.name,
            "metrics": self.get_metrics()
        }
