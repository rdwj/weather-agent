#!/usr/bin/env python3
"""
MCP Prompts operations module.

Provides functionality for listing and using prompt templates from MCP servers.
This module handles automatic argument serialization and message generation.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Union, TYPE_CHECKING
from dataclasses import dataclass, asdict, is_dataclass
from datetime import datetime
from decimal import Decimal

if TYPE_CHECKING:
    from fastmcp import Client

logger = logging.getLogger(__name__)


@dataclass
class PromptMessage:
    """
    Represents a message generated from a prompt template.
    """
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PromptResult:
    """
    Result from executing a prompt template.
    """
    prompt_name: str
    messages: List[PromptMessage]
    arguments_used: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None


class MCPPromptHandler:
    """
    Handles MCP prompt operations for agents.
    """

    def __init__(self, mcp_client: Optional[Any] = None):
        """
        Initialize prompt handler.

        Args:
            mcp_client: FastMCP client instance
        """
        self._client = mcp_client
        self._prompts_cache: List[Any] = []

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """
        List all available prompt templates on the server.

        Returns:
            List of prompt descriptions
        """
        if not self._client:
            logger.warning("MCP client not initialized")
            return []

        try:
            # Get prompts from server
            prompts = await self._client.list_prompts()
            self._prompts_cache = prompts

            # Format for return
            prompt_list = []
            for prompt in prompts:
                prompt_info = {
                    "name": prompt.name,
                    "description": getattr(prompt, 'description', '')
                }

                # Add arguments if available
                if hasattr(prompt, 'arguments') and prompt.arguments:
                    prompt_info["arguments"] = [
                        {
                            "name": arg.name,
                            "description": getattr(arg, 'description', ''),
                            "required": getattr(arg, 'required', False)
                        }
                        for arg in prompt.arguments
                    ]

                # Add metadata if available
                if hasattr(prompt, '_meta') and prompt._meta:
                    fastmcp_meta = prompt._meta.get('_fastmcp', {})
                    if fastmcp_meta.get('tags'):
                        prompt_info["tags"] = fastmcp_meta['tags']

                prompt_list.append(prompt_info)

            logger.info(f"Found {len(prompt_list)} prompt templates")
            return prompt_list

        except Exception as e:
            logger.error(f"Failed to list prompts: {e}")
            return []

    def _serialize_argument(self, value: Any) -> Union[str, Any]:
        """
        Prepare arguments for FastMCP client.

        FastMCP v2.9+ automatically serializes complex types (dicts, lists, dataclasses)
        to JSON strings as required by the MCP specification. We just need to convert
        any special Python types to standard JSON-compatible types.

        Args:
            value: Value to prepare

        Returns:
            Value ready for FastMCP client (unchanged for most types)
        """
        # Simple types pass through unchanged - FastMCP handles them
        if isinstance(value, (str, bool, type(None), int, float)):
            return value

        # Dicts and lists pass through - FastMCP will serialize them
        if isinstance(value, (dict, list, tuple)):
            return value

        # Convert special types to JSON-compatible forms
        try:
            # Handle dataclasses - convert to dict
            if is_dataclass(value):
                return asdict(value)

            # Handle datetime objects - convert to ISO string
            if isinstance(value, datetime):
                return value.isoformat()

            # Handle Decimal - convert to float
            if isinstance(value, Decimal):
                return float(value)

            # For other objects with __dict__, convert to dict
            if hasattr(value, '__dict__'):
                return {k: v for k, v in value.__dict__.items() if not k.startswith('_')}

            # Last resort: convert to string
            logger.warning(f"Unknown type {type(value)}, converting to string")
            return str(value)

        except Exception as e:
            logger.warning(f"Failed to prepare argument: {e}, using string representation")
            return str(value)

    async def get_prompt(
        self,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> PromptResult:
        """
        Get a rendered prompt with arguments.

        Args:
            prompt_name: Name of the prompt template
            arguments: Arguments to pass to the prompt

        Returns:
            PromptResult with generated messages
        """
        if not self._client:
            return PromptResult(
                prompt_name=prompt_name,
                messages=[],
                arguments_used={},
                success=False,
                error="MCP client not initialized"
            )

        try:
            # Serialize complex arguments
            serialized_args = {}
            if arguments:
                for key, value in arguments.items():
                    serialized_args[key] = self._serialize_argument(value)

            logger.debug(f"Getting prompt '{prompt_name}' with args: {serialized_args}")

            # Get rendered prompt from server
            try:
                result = await self._client.get_prompt(prompt_name, serialized_args)
            except Exception as get_error:
                logger.error(f"MCP server error for prompt '{prompt_name}': {get_error}")
                logger.error(f"Arguments passed: {serialized_args}")
                raise

            # Convert to PromptMessage objects
            messages = []
            for msg in result.messages:
                # Extract content based on type
                content = msg.content
                if hasattr(msg.content, 'text'):
                    content = msg.content.text

                messages.append(PromptMessage(
                    role=msg.role,
                    content=content,
                    metadata=getattr(msg, 'metadata', None)
                ))

            return PromptResult(
                prompt_name=prompt_name,
                messages=messages,
                arguments_used=arguments or {},
                success=True
            )

        except Exception as e:
            logger.error(f"Failed to get prompt '{prompt_name}': {e}")
            return PromptResult(
                prompt_name=prompt_name,
                messages=[],
                arguments_used=arguments or {},
                success=False,
                error=str(e)
            )

    async def get_prompt_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """
        Get all prompts with a specific tag.

        Args:
            tag: Tag to filter by

        Returns:
            List of prompts with the specified tag
        """
        all_prompts = await self.list_prompts()

        filtered = [
            prompt for prompt in all_prompts
            if tag in prompt.get('tags', [])
        ]

        logger.debug(f"Found {len(filtered)} prompts with tag '{tag}'")
        return filtered

    async def get_prompt_with_fallback(
        self,
        prompt_names: List[str],
        arguments: Optional[Dict[str, Any]] = None
    ) -> PromptResult:
        """
        Try multiple prompts in order, using the first successful one.

        Args:
            prompt_names: List of prompt names to try in order
            arguments: Arguments to pass to the prompt

        Returns:
            PromptResult from the first successful prompt
        """
        last_error = None

        for prompt_name in prompt_names:
            result = await self.get_prompt(prompt_name, arguments)

            if result.success:
                logger.debug(f"Successfully used prompt: {prompt_name}")
                return result

            last_error = result.error
            logger.debug(f"Prompt '{prompt_name}' failed: {last_error}, trying next...")

        # All prompts failed
        return PromptResult(
            prompt_name=" -> ".join(prompt_names),
            messages=[],
            arguments_used=arguments or {},
            success=False,
            error=f"All prompts failed. Last error: {last_error}"
        )

    async def get_system_prompt(
        self,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Get a system prompt message from a prompt template.

        Convenience method for prompts that generate system messages.

        Args:
            prompt_name: Name of the prompt template
            arguments: Arguments to pass to the prompt

        Returns:
            System message content or None if not found
        """
        result = await self.get_prompt(prompt_name, arguments)

        if not result.success or not result.messages:
            return None

        # Find first system message
        for msg in result.messages:
            if msg.role == "system":
                return msg.content

        # If no system message, return first message
        return result.messages[0].content

    async def get_conversation_template(
        self,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """
        Get a conversation template as a list of role/content dictionaries.

        Useful for initializing LLM conversations.

        Args:
            prompt_name: Name of the prompt template
            arguments: Arguments to pass to the prompt

        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        result = await self.get_prompt(prompt_name, arguments)

        if not result.success:
            return []

        return [
            {"role": msg.role, "content": msg.content}
            for msg in result.messages
        ]

    async def batch_get_prompts(
        self,
        prompt_requests: List[Dict[str, Any]]
    ) -> Dict[str, PromptResult]:
        """
        Get multiple prompts in parallel.

        Args:
            prompt_requests: List of dicts with 'name' and 'arguments' keys

        Returns:
            Dictionary mapping prompt names to results
        """
        import asyncio

        tasks = []
        names = []

        for request in prompt_requests:
            name = request.get('name')
            args = request.get('arguments')

            if name:
                tasks.append(self.get_prompt(name, args))
                names.append(name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        prompt_results = {}
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                prompt_results[name] = PromptResult(
                    prompt_name=name,
                    messages=[],
                    arguments_used={},
                    success=False,
                    error=str(result)
                )
            else:
                prompt_results[name] = result

        return prompt_results

    def get_cached_prompts(self) -> List[Any]:
        """
        Get cached list of prompts from last list operation.

        Returns:
            Cached prompt list
        """
        return self._prompts_cache

    async def validate_prompt_arguments(
        self,
        prompt_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate arguments against prompt requirements.

        Args:
            prompt_name: Name of the prompt
            arguments: Arguments to validate

        Returns:
            Validation result with 'valid' and 'errors' keys
        """
        prompts = await self.list_prompts()

        # Find the prompt
        prompt_info = None
        for prompt in prompts:
            if prompt['name'] == prompt_name:
                prompt_info = prompt
                break

        if not prompt_info:
            return {
                "valid": False,
                "errors": [f"Prompt '{prompt_name}' not found"]
            }

        errors = []

        # Check required arguments
        if 'arguments' in prompt_info:
            for arg_info in prompt_info['arguments']:
                arg_name = arg_info['name']
                is_required = arg_info.get('required', False)

                if is_required and arg_name not in arguments:
                    errors.append(f"Required argument '{arg_name}' is missing")

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

    async def format_prompt_for_llm(
        self,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Get a prompt and format it as a single string for LLM input.

        Args:
            prompt_name: Name of the prompt template
            arguments: Arguments to pass to the prompt
            additional_context: Extra context to append

        Returns:
            Formatted prompt string
        """
        result = await self.get_prompt(prompt_name, arguments)

        if not result.success:
            return f"Error getting prompt: {result.error}"

        # Format messages
        formatted_parts = []
        for msg in result.messages:
            formatted_parts.append(f"{msg.role.upper()}: {msg.content}")

        if additional_context:
            formatted_parts.append(f"\nCONTEXT: {additional_context}")

        return "\n\n".join(formatted_parts)