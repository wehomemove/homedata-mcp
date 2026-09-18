"""Homedata MCP server: UK property data as tools for AI assistants."""

__version__ = "1.0.0"

from .client import HomedataClient, HomedataError

__all__ = ["HomedataClient", "HomedataError", "__version__"]
