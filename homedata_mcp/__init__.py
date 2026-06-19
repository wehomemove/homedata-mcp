"""Homedata MCP server - exposes UK property data to LLM coding assistants."""

__version__ = "0.5.0"

from .client import HomedataClient, HomedataError

__all__ = ["HomedataClient", "HomedataError", "__version__"]
