"""
MCP Client tập trung - quản lý kết nối tới các MCP servers.

Hiện tại có 2 servers:
    1. Tavily      → Remote MCP (streamable_http), dùng để research/search web.
    2. Wikimedia   → Local MCP (stdio, chạy qua npx), dùng để tìm ảnh minh họa.

Cách dùng ở các file khác (tavily_search.py, wikimedia_images.py):

    from agents.tools.mcp_client import get_mcp_client

    client = get_mcp_client()
    tools = await client.get_tools()

Lưu ý:
    - Wikimedia MCP chạy qua `npx -y wikimedia-image-search-mcp`, cần có
      Node.js >= 18 cài sẵn trên máy (kiểm tra bằng `node -v`).
    - Tavily MCP dùng remote server của Tavily, cần TAVILY_API_KEY hợp lệ
      trong file .env.
"""

import os

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

# Load biến môi trường từ .env (TODO: sau này thay bằng config/settings.py
# khi bạn build xong phần config chung của cả project).
load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

if not TAVILY_API_KEY:
    raise RuntimeError(
        "TAVILY_API_KEY chưa được set trong file .env. "
        "Vui lòng kiểm tra lại trước khi dùng Tavily MCP."
    )


# ============================================================
# CẤU HÌNH CÁC MCP SERVERS
# ============================================================
#
# Key trong dict này ("tavily", "wikimedia") chính là "server name"
# dùng để gọi tool sau này.
# ============================================================

MCP_SERVERS_CONFIG = {
    "tavily": {
        "transport": "streamable_http",
        "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}",
    },
    "wikimedia": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "wikimedia-image-search-mcp"],
    },
}


# Singleton instance - tránh tạo lại client (và spawn lại process npx) mỗi lần gọi.
_client: MultiServerMCPClient | None = None


def get_mcp_client() -> MultiServerMCPClient:
    """Trả về singleton instance của MultiServerMCPClient."""
    global _client
    if _client is None:
        _client = MultiServerMCPClient(MCP_SERVERS_CONFIG)
    return _client


async def list_all_tools() -> dict[str, list[str]]:
    """
    Liệt kê tất cả tools available từ tất cả MCP servers đã config.

    Trả về dict dạng:
        {
            "tavily": ["tavily-search", "tavily-extract", ...],
            "wikimedia": ["wikimedia_search_images"],
        }

    Hữu ích để debug xem server đã connect đúng chưa, tool name đúng chưa.
    """
    client = get_mcp_client()
    result: dict[str, list[str]] = {}

    for server_name in MCP_SERVERS_CONFIG:
        tools = await client.get_tools(server_name=server_name)
        result[server_name] = [tool.name for tool in tools]

    return result


# ============================================================
# DEBUG - Chạy trực tiếp file này để test kết nối MCP servers
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.tools.mcp_client
#
# Kết quả mong đợi: in ra danh sách tools của cả tavily và wikimedia.
# ============================================================

# if __name__ == "__main__":
#     import asyncio

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Kiểm tra kết nối MCP servers")
#         print("=" * 60)

#         try:
#             tools_by_server = await list_all_tools()
#             for server_name, tool_names in tools_by_server.items():
#                 print(f"\n✅ Server '{server_name}' connected thành công!")
#                 print(f"   Tools available: {tool_names}")
#         except Exception as e:
#             print(f"\n❌ Lỗi khi kết nối MCP servers: {e}")
#             print(
#                 "\nGợi ý kiểm tra:\n"
#                 "  - Wikimedia: đã cài Node.js >= 18 chưa? (chạy `node -v`)\n"
#                 "  - Tavily: TAVILY_API_KEY trong .env có hợp lệ không?\n"
#                 "  - Đã cài package `langchain-mcp-adapters` chưa? "
#                 "(pip install langchain-mcp-adapters)\n"
#             )

#     asyncio.run(_debug())