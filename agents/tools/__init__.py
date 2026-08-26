"""
Export toàn bộ tools để tiện import từ 1 chỗ duy nhất.

Thay vì:
    from agents.tools.tavily_search import tavily_search
    from agents.tools.wikimedia_images import search_wikimedia_images

Có thể viết gọn:
    from agents.tools import tavily_search, search_wikimedia_images
"""

from agents.tools.mcp_client import get_mcp_client, list_all_tools
from agents.tools.research_normalizer import (
    normalize_tavily_result,
    normalize_wikimedia_result,
)
from agents.tools.tavily_search import tavily_search
from agents.tools.wikimedia_images import search_wikimedia_images

__all__ = [
    # mcp_client
    "get_mcp_client",
    "list_all_tools",
    # tavily_search
    "tavily_search",
    # wikimedia_images
    "search_wikimedia_images",
    # research_normalizer
    "normalize_tavily_result",
    "normalize_wikimedia_result",
]