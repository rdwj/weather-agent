#!/usr/bin/env python3
"""
MCP Resource operations module.

Provides functionality for listing and reading static and templated resources
from MCP servers. This module is used by BaseAgent to provide resource
capabilities to all agents.
"""

import logging
from typing import List, Dict, Any, Optional, Union, TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path
import base64

if TYPE_CHECKING:
    from fastmcp import Client

logger = logging.getLogger(__name__)


@dataclass
class ResourceContent:
    """
    Represents content from an MCP resource.
    """
    uri: str
    mime_type: Optional[str] = None
    text: Optional[str] = None
    blob: Optional[bytes] = None
    is_binary: bool = False


class MCPResourceHandler:
    """
    Handles MCP resource operations for agents.
    """

    def __init__(self, mcp_client: Optional[Any] = None):
        """
        Initialize resource handler.

        Args:
            mcp_client: FastMCP client instance
        """
        self._client = mcp_client
        self._resources_cache: List[Any] = []
        self._templates_cache: List[Any] = []

    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all static resources available on the server.

        Returns:
            List of resource descriptions
        """
        if not self._client:
            logger.warning("MCP client not initialized")
            return []

        try:
            # Get resources from server
            resources = await self._client.list_resources()
            self._resources_cache = resources

            # Format for return
            resource_list = []
            for resource in resources:
                resource_info = {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": getattr(resource, 'description', ''),
                    "mime_type": getattr(resource, 'mimeType', None)
                }

                # Add metadata if available
                if hasattr(resource, '_meta') and resource._meta:
                    fastmcp_meta = resource._meta.get('_fastmcp', {})
                    if fastmcp_meta.get('tags'):
                        resource_info["tags"] = fastmcp_meta['tags']

                resource_list.append(resource_info)

            logger.info(f"Found {len(resource_list)} static resources")
            return resource_list

        except Exception as e:
            logger.error(f"Failed to list resources: {e}")
            return []

    async def list_resource_templates(self) -> List[Dict[str, Any]]:
        """
        List all resource templates available on the server.

        Returns:
            List of template descriptions
        """
        if not self._client:
            logger.warning("MCP client not initialized")
            return []

        try:
            # Get templates from server
            templates = await self._client.list_resource_templates()
            self._templates_cache = templates

            # Format for return
            template_list = []
            for template in templates:
                template_info = {
                    "uri_template": template.uriTemplate,
                    "name": template.name,
                    "description": getattr(template, 'description', ''),
                    "mime_type": getattr(template, 'mimeType', None)
                }

                # Add metadata if available
                if hasattr(template, '_meta') and template._meta:
                    fastmcp_meta = template._meta.get('_fastmcp', {})
                    if fastmcp_meta.get('tags'):
                        template_info["tags"] = fastmcp_meta['tags']

                template_list.append(template_info)

            logger.info(f"Found {len(template_list)} resource templates")
            return template_list

        except Exception as e:
            logger.error(f"Failed to list resource templates: {e}")
            return []

    async def read_resource(self, uri: str) -> Optional[ResourceContent]:
        """
        Read content from a resource URI.

        Args:
            uri: Resource URI to read

        Returns:
            ResourceContent object or None if failed
        """
        if not self._client:
            logger.warning("MCP client not initialized")
            return None

        try:
            logger.debug(f"Reading resource: {uri}")

            # Read from server
            content_list = await self._client.read_resource(uri)

            if not content_list:
                logger.warning(f"No content returned for resource: {uri}")
                return None

            # Process first content item (MCP can return multiple)
            content = content_list[0]

            # Create ResourceContent object
            resource_content = ResourceContent(uri=uri)

            # Check content type
            if hasattr(content, 'text'):
                resource_content.text = content.text
                resource_content.is_binary = False
            elif hasattr(content, 'blob'):
                resource_content.blob = content.blob
                resource_content.is_binary = True

            # Add MIME type if available
            if hasattr(content, 'mimeType'):
                resource_content.mime_type = content.mimeType

            logger.debug(f"Successfully read resource: {uri} (binary: {resource_content.is_binary})")
            return resource_content

        except Exception as e:
            logger.error(f"Failed to read resource '{uri}': {e}")
            return None

    async def read_multiple_resources(self, uris: List[str]) -> Dict[str, Optional[ResourceContent]]:
        """
        Read multiple resources in parallel.

        Args:
            uris: List of resource URIs to read

        Returns:
            Dictionary mapping URI to ResourceContent or None if failed
        """
        import asyncio

        tasks = [self.read_resource(uri) for uri in uris]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        resource_map = {}
        for uri, result in zip(uris, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to read resource '{uri}': {result}")
                resource_map[uri] = None
            else:
                resource_map[uri] = result

        return resource_map

    async def save_resource_to_file(self, uri: str, file_path: Union[str, Path]) -> bool:
        """
        Read a resource and save it to a file.

        Args:
            uri: Resource URI to read
            file_path: Path to save the resource content

        Returns:
            True if successful, False otherwise
        """
        content = await self.read_resource(uri)

        if not content:
            return False

        try:
            file_path = Path(file_path)

            if content.is_binary and content.blob:
                # Save binary content
                file_path.write_bytes(content.blob)
                logger.info(f"Saved binary resource to: {file_path}")
            elif content.text:
                # Save text content
                file_path.write_text(content.text)
                logger.info(f"Saved text resource to: {file_path}")
            else:
                logger.warning(f"No content to save for resource: {uri}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to save resource to file: {e}")
            return False

    async def get_resource_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """
        Get all resources with a specific tag.

        Args:
            tag: Tag to filter by

        Returns:
            List of resources with the specified tag
        """
        all_resources = await self.list_resources()

        filtered = [
            resource for resource in all_resources
            if tag in resource.get('tags', [])
        ]

        logger.debug(f"Found {len(filtered)} resources with tag '{tag}'")
        return filtered

    async def get_template_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """
        Get all resource templates with a specific tag.

        Args:
            tag: Tag to filter by

        Returns:
            List of templates with the specified tag
        """
        all_templates = await self.list_resource_templates()

        filtered = [
            template for template in all_templates
            if tag in template.get('tags', [])
        ]

        logger.debug(f"Found {len(filtered)} templates with tag '{tag}'")
        return filtered

    async def read_json_resource(self, uri: str) -> Optional[Dict[str, Any]]:
        """
        Read a JSON resource and parse it.

        Args:
            uri: Resource URI to read

        Returns:
            Parsed JSON as dictionary or None if failed
        """
        import json

        content = await self.read_resource(uri)

        if not content or not content.text:
            return None

        try:
            return json.loads(content.text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from resource '{uri}': {e}")
            return None

    async def read_yaml_resource(self, uri: str) -> Optional[Dict[str, Any]]:
        """
        Read a YAML resource and parse it.

        Args:
            uri: Resource URI to read

        Returns:
            Parsed YAML as dictionary or None if failed
        """
        try:
            import yaml
        except ImportError:
            logger.error("PyYAML not installed. Install with: pip install pyyaml")
            return None

        content = await self.read_resource(uri)

        if not content or not content.text:
            return None

        try:
            return yaml.safe_load(content.text)
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML from resource '{uri}': {e}")
            return None

    async def read_template_resource(
        self,
        template_uri: str,
        parameters: Dict[str, Any]
    ) -> Optional[ResourceContent]:
        """
        Read from a resource template with parameters.

        Args:
            template_uri: Template URI pattern
            parameters: Parameters to fill in the template

        Returns:
            ResourceContent object or None if failed
        """
        # Simple template substitution (servers may handle this differently)
        uri = template_uri
        for key, value in parameters.items():
            uri = uri.replace(f"{{{{{key}}}}}", str(value))
            uri = uri.replace(f"{{{key}}}", str(value))

        logger.debug(f"Expanded template URI: {template_uri} -> {uri}")
        return await self.read_resource(uri)

    def get_cached_resources(self) -> List[Any]:
        """
        Get cached list of resources from last list operation.

        Returns:
            Cached resource list
        """
        return self._resources_cache

    def get_cached_templates(self) -> List[Any]:
        """
        Get cached list of templates from last list operation.

        Returns:
            Cached template list
        """
        return self._templates_cache

    async def prefetch_resources(self, uris: List[str]) -> Dict[str, bool]:
        """
        Prefetch multiple resources for later use.

        Args:
            uris: List of resource URIs to prefetch

        Returns:
            Dictionary mapping URI to success status
        """
        results = await self.read_multiple_resources(uris)

        status = {}
        for uri, content in results.items():
            status[uri] = content is not None

        successful = sum(1 for success in status.values() if success)
        logger.info(f"Prefetched {successful}/{len(uris)} resources successfully")

        return status

    async def get_resource_as_base64(self, uri: str) -> Optional[str]:
        """
        Read a resource and return its content as base64.

        Useful for embedding binary resources in JSON or HTML.

        Args:
            uri: Resource URI to read

        Returns:
            Base64 encoded string or None if failed
        """
        content = await self.read_resource(uri)

        if not content:
            return None

        try:
            if content.is_binary and content.blob:
                return base64.b64encode(content.blob).decode('utf-8')
            elif content.text:
                return base64.b64encode(content.text.encode('utf-8')).decode('utf-8')
            else:
                return None
        except Exception as e:
            logger.error(f"Failed to encode resource as base64: {e}")
            return None