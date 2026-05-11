"""Homedata MCP server - exposes UK property data to LLM coding assistants."""

__version__ = "0.1.2"

from .client import HomedataClient, HomedataError

__all__ = ["HomedataClient", "HomedataError", "__version__"]
