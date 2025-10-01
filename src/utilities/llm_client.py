#!/usr/bin/env python3
"""
LLM Client utility for the application.

This module provides a real LLM client that integrates with Llama 4
or other configured LLM providers.
"""

import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

# Try to load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Production LLM client for making real API calls.

    This client is designed to work with various LLM providers
    and currently supports Llama 4 via API.
    """

    def __init__(self):
        """
        Initialize LLM client with environment configuration.
        """
        self.api_url = os.getenv('LLM_URL', '')
        self.api_key = os.getenv('LLM_API_KEY', '')
        self.model_name = os.getenv('LLM_MODEL_NAME', 'llama-4-scout-17b-16e-w4a16')

        # Check if we have valid configuration
        self.is_configured = bool(self.api_url and self.api_key)

        if not self.is_configured:
            logger.warning(
                "LLM client not configured. Please set LLM_URL and LLM_API_KEY "
                "environment variables."
            )
        else:
            logger.info(
                f"LLM client initialized with model: {self.model_name} at {self.api_url}"
            )

    def invoke_with_metadata(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call the LLM API and return response with metadata.

        Args:
            prompt: The prompt to send to the LLM
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters to pass to the API

        Returns:
            Dictionary containing:
                - content: The LLM response text
                - model: Model name used
                - temperature: Temperature used
                - metadata: Additional response metadata

        Raises:
            RuntimeError: If LLM is not configured or API call fails
        """
        if not self.is_configured:
            raise RuntimeError(
                "LLM client not configured. Please set LLM_URL and LLM_API_KEY "
                "environment variables."
            )

        import requests

        try:
            # Prepare API request
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            # Build payload
            payload = {
                'model': self.model_name,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': temperature,
                'max_tokens': max_tokens
            }

            # Add any additional kwargs to payload
            for key, value in kwargs.items():
                if key not in payload:
                    payload[key] = value

            logger.debug(f"Calling LLM API with model: {self.model_name}, temperature: {temperature}")

            # Make API call
            response = requests.post(
                f'{self.api_url}/chat/completions',
                headers=headers,
                json=payload,
                timeout=60  # Increased timeout for longer responses
            )

            if response.status_code == 200:
                result = response.json()

                # Extract content from response
                choices = result.get('choices', [])
                if not choices:
                    raise RuntimeError("No choices in LLM response")

                content = choices[0].get('message', {}).get('content', '')

                # Track token usage if available
                usage = result.get('usage', {})
                if usage:
                    logger.debug(
                        f"Token usage - Prompt: {usage.get('prompt_tokens', 0)}, "
                        f"Completion: {usage.get('completion_tokens', 0)}, "
                        f"Total: {usage.get('total_tokens', 0)}"
                    )

                return {
                    'content': content,
                    'model': result.get('model', self.model_name),
                    'temperature': temperature,
                    'usage': usage,
                    'finish_reason': choices[0].get('finish_reason', 'unknown')
                }
            else:
                error_msg = f"LLM API call failed with status {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

        except requests.exceptions.Timeout:
            error_msg = "LLM API call timed out"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Failed to connect to LLM API: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error calling LLM API: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def is_available(self) -> bool:
        """
        Check if the LLM client is configured and available.

        Returns:
            True if configured, False otherwise
        """
        return self.is_configured


# Create a singleton instance for the application
_llm_client_instance = None


def get_llm_client() -> LLMClient:
    """
    Get the singleton LLM client instance.

    Returns:
        The configured LLM client
    """
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance