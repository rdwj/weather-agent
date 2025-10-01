#!/usr/bin/env python3
"""
Generic LLM call utility with optional JSON schema validation
Provides a unified interface for both structured and unstructured LLM responses
"""

import json
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime
from jsonschema import validate, ValidationError  # type: ignore

logger = logging.getLogger(__name__)


class CallModel:
    """
    Unified LLM caller that handles both schema-validated and regular responses
    """

    def __init__(self, llm_client, max_retries: int = 3):
        """
        Initialize with an existing LLM client
        
        Args:
            llm_client: Instance of RobustLLMClient or similar
            max_retries: Default maximum retry attempts for schema validation
        """
        self.llm = llm_client
        self.max_retries = max_retries

    async def call(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_retries: Optional[int] = None,
        return_raw: bool = False,
        **kwargs
    ) -> Union[Dict, str, Tuple[Optional[Dict], List[Dict], bool]]:
        """
        Unified entry point for LLM calls with optional schema validation
        
        Args:
            prompt: The user prompt
            schema: Optional JSON schema to validate against
            system_prompt: Optional system prompt
            temperature: Model temperature
            max_retries: Override default max retries (only used with schema)
            return_raw: For non-schema calls, return raw string instead of attempting JSON parse
            **kwargs: Additional arguments to pass to the LLM
        
        Returns:
            - With schema: Tuple of (validated_response, message_history, success)
            - Without schema: Response (dict if JSON parseable, string otherwise)
        """
        if schema:
            return await self._call_with_schema(
                prompt=prompt,
                schema=schema,
                system_prompt=system_prompt,
                temperature=temperature,
                max_retries=max_retries or self.max_retries
            )
        else:
            return await self._call_without_schema(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                return_raw=return_raw,
                **kwargs
            )

    async def _call_without_schema(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        return_raw: bool = False,
        **kwargs
    ) -> Union[Dict, str]:
        """
        Simple LLM call without schema validation
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Model temperature
            return_raw: Return raw string instead of attempting JSON parse
            **kwargs: Additional arguments to pass to the LLM
        
        Returns:
            Response as dict (if JSON) or string
        """
        if system_prompt is None:
            system_prompt = "You are a helpful assistant."
        
        # Build prompt
        full_prompt = f"System: {system_prompt}\n\nUser: {prompt}\n\nAssistant:"
        
        logger.info("  📞 Calling model without schema validation")
        
        # Call the LLM with temperature and additional kwargs
        invoke_kwargs = {'temperature': temperature}
        invoke_kwargs.update(kwargs)
        
        response_metadata = self.llm.invoke_with_metadata(
            full_prompt,
            **invoke_kwargs
        )
        raw_response = response_metadata.get('content', '')
        
        if return_raw:
            return raw_response
        
        # Try to parse as JSON
        try:
            # Clean up common JSON formatting
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            parsed = json.loads(cleaned.strip())
            logger.info("  ✅ Response successfully parsed as JSON")
            return parsed
        except json.JSONDecodeError:
            logger.info("  📝 Response is plain text (not JSON)")
            return raw_response

    async def _call_with_schema(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_retries: int = 3
    ) -> Tuple[Optional[Dict], List[Dict], bool]:
        """
        Call model with JSON schema validation and retry logic
        
        Args:
            prompt: The user prompt
            schema: JSON schema to validate against
            system_prompt: Optional system prompt
            temperature: Model temperature
            max_retries: Maximum retry attempts
        
        Returns:
            Tuple of (validated_response, message_history, success)
        """
        if system_prompt is None:
            system_prompt = "You are a helpful assistant that ALWAYS responds with valid JSON matching the provided schema. Output ONLY JSON, no additional text."
        
        # Build initial messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{prompt}\n\nRequired JSON Schema <schema>:\n{json.dumps(schema, indent=2)}</schema>"}
        ]
        
        message_history = []
        
        for attempt in range(max_retries):
            logger.info("  🔄 Attempt %d/%d for schema-compliant response", attempt + 1, max_retries)
            
            # Call the LLM with temperature
            response_metadata = self.llm.invoke_with_metadata(
                self._messages_to_prompt(messages),
                temperature=temperature
            )
            raw_response = response_metadata.get('content', '')
            
            # Try to parse as JSON
            response = None
            try:
                # Clean up response
                cleaned = raw_response.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                response = json.loads(cleaned.strip())
            except json.JSONDecodeError:
                response = None
            
            # Store in history
            message_history.append({
                "attempt": attempt + 1,
                "response": response,
                "raw": raw_response,
                "timestamp": datetime.now().isoformat()
            })
            
            # Check if response is valid JSON
            if response and isinstance(response, dict):
                # Validate against schema
                try:
                    validate(instance=response, schema=schema)
                    logger.info("  ✅ Valid JSON response on attempt %d", attempt + 1)
                    return response, message_history, True
                except ValidationError as e:
                    logger.warning("  ⚠️ Schema validation failed: %s", e.message)
                    error_detail = f"Field '{e.path}': {e.message}" if e.path else e.message
                    
                    # Add correction message
                    messages.append({
                        "role": "assistant",
                        "content": raw_response if raw_response else json.dumps(response)
                    })
                    messages.append({
                        "role": "user",
                        "content": f"That was not quite right. The JSON does not match the required schema.\nError: {error_detail}\n\nPlease try again and output ONLY valid JSON according to this exact schema: <schema>\n{json.dumps(schema, indent=2)}</schema>"
                    })
            else:
                # Not valid JSON at all
                logger.warning("  ⚠️ Response is not valid JSON")
                
                messages.append({
                    "role": "assistant",
                    "content": raw_response if raw_response else "Invalid response"
                })
                messages.append({
                    "role": "user",
                    "content": f"That was not valid JSON. Please output ONLY valid JSON matching this exact schema <schema>:\n{json.dumps(schema, indent=2)}</schema>"
                })
        
        logger.error("  ❌ Failed to get schema-compliant response after %d attempts", max_retries)
        return None, message_history, False

    def _messages_to_prompt(self, messages: List[Dict]) -> str:
        """
        Convert message array to single prompt for LLM
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
        
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        for msg in messages:
            role = msg['role']
            content = msg['content']
            if role == 'system':
                prompt_parts.append(f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
        
        return "\n\n".join(prompt_parts) + "\n\nAssistant:"
