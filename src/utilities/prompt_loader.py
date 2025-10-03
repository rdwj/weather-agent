#!/usr/bin/env python3
"""
Prompt loader utility for managing YAML-based prompt templates.

This module provides functionality to load and manage prompt templates
from YAML files, supporting variable substitution and caching.
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class PromptLoader:
    """
    Utility class for loading and managing YAML-based prompt templates.
    """

    def __init__(self, prompts_dir: Optional[str] = None):
        """
        Initialize the prompt loader.

        Args:
            prompts_dir: Directory containing prompt YAML files.
                        Defaults to 'prompts' in project root.
        """
        if prompts_dir:
            self.prompts_dir = Path(prompts_dir)
        else:
            # Default to prompts directory in project root
            project_root = Path(__file__).parent.parent.parent
            self.prompts_dir = project_root / "prompts"

        self._cache: Dict[str, Dict[str, Any]] = {}
        logger.info(f"PromptLoader initialized with directory: {self.prompts_dir}")

    def load_prompt(
        self,
        prompt_name: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Load a prompt template and substitute variables.

        Args:
            prompt_name: Name of the prompt file (without .yaml extension)
            variables: Dictionary of variables to substitute in the template

        Returns:
            Formatted prompt string with variables substituted

        Raises:
            FileNotFoundError: If prompt file doesn't exist
            KeyError: If required variables are missing
        """
        # Load from cache or file
        if prompt_name not in self._cache:
            prompt_data = self._load_from_file(prompt_name)
            self._cache[prompt_name] = prompt_data
        else:
            prompt_data = self._cache[prompt_name]

        # Get the template
        template = prompt_data.get("template", "")

        # Substitute variables if provided
        if variables:
            try:
                formatted_prompt = str(template.format(**variables))
            except KeyError as e:
                missing_var = str(e).strip("'")
                logger.error(f"Missing required variable '{missing_var}' for prompt '{prompt_name}'")
                raise KeyError(
                    f"Missing required variable '{missing_var}' for prompt '{prompt_name}'"
                ) from e
        else:
            formatted_prompt = str(template)

        return formatted_prompt

    def _load_from_file(self, prompt_name: str) -> Dict[str, Any]:
        """
        Load prompt data from YAML file.

        Args:
            prompt_name: Name of the prompt file (without .yaml extension)

        Returns:
            Dictionary containing prompt data

        Raises:
            FileNotFoundError: If prompt file doesn't exist
        """
        prompt_file = self.prompts_dir / f"{prompt_name}.yaml"

        if not prompt_file.exists():
            logger.error(f"Prompt file not found: {prompt_file}")
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_data: Dict[str, Any] = yaml.safe_load(f)

            logger.debug(f"Loaded prompt '{prompt_name}' from {prompt_file}")
            return prompt_data

        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {prompt_file}: {e}")
            raise

    def get_prompt_info(self, prompt_name: str) -> Dict[str, Any]:
        """
        Get metadata about a prompt without loading the template.

        Args:
            prompt_name: Name of the prompt file (without .yaml extension)

        Returns:
            Dictionary containing prompt metadata (name, description, variables, etc.)
        """
        if prompt_name not in self._cache:
            prompt_data = self._load_from_file(prompt_name)
            self._cache[prompt_name] = prompt_data
        else:
            prompt_data = self._cache[prompt_name]

        return {
            "name": prompt_data.get("name", ""),
            "description": prompt_data.get("description", ""),
            "variables": prompt_data.get("variables", []),
            "parameters": prompt_data.get("parameters", {})
        }

    def list_prompts(self) -> list[str]:
        """
        List all available prompt files.

        Returns:
            List of prompt names (without .yaml extension)
        """
        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory does not exist: {self.prompts_dir}")
            return []

        prompt_files = list(self.prompts_dir.glob("*.yaml"))
        return [p.stem for p in prompt_files if p.stem != "weather_agent"]

    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._cache.clear()
        logger.debug("Prompt cache cleared")

    def reload_prompt(self, prompt_name: str) -> None:
        """
        Reload a specific prompt from disk, bypassing cache.

        Args:
            prompt_name: Name of the prompt to reload
        """
        if prompt_name in self._cache:
            del self._cache[prompt_name]
        self._load_from_file(prompt_name)
        self._cache[prompt_name] = self._load_from_file(prompt_name)
        logger.info(f"Reloaded prompt: {prompt_name}")


# Global prompt loader instance
_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader(prompts_dir: Optional[str] = None) -> PromptLoader:
    """
    Get or create the global prompt loader instance.

    Args:
        prompts_dir: Optional prompts directory path

    Returns:
        PromptLoader instance
    """
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader(prompts_dir)
    return _prompt_loader
