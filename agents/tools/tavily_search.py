"""
Wrapper gọi tool `tavily_search` từ Tavily MCP server (remote).

Cách dùng:

    from agents.tools.tavily_search import tavily_search

    result: ResearchResult = await tavily_search("MCP cho AI Engineer")

Lưu ý:
    - Tool name chính xác trên Tavily MCP là "tavily_search".
    - Kết quả trả về từ MCP tool là danh sách content blocks.
      Content block kiểu "text" chứa JSON string.
"""

import json

from agents.schemas.research import ResearchResult
from agents.tools.mcp_client import get_mcp_client
from agents.tools.research_normalizer import normalize_tavily_result

TAVILY_TOOL_NAME = "tavily_search"


async def _get_tavily_tool():
    """Lấy tool 'tavily_search' từ MCP client."""
    client = get_mcp_client()
    tools = await client.get_tools(server_name="tavily")

    for tool in tools:
        if tool.name == TAVILY_TOOL_NAME:
            return tool

    raise RuntimeError(
        f"Không tìm thấy tool '{TAVILY_TOOL_NAME}' trên Tavily MCP server. "
        f"Các tool hiện có: {[t.name for t in tools]}"
    )


async def tavily_search(
    query: str,
    max_results: int = 5,
) -> ResearchResult:
    """
    Gọi Tavily search qua MCP, trả về ResearchResult đã normalize.

    Nếu có lỗi (API fail, parse fail...), trả về ResearchResult rỗng
    (sources=[]) thay vì raise exception, theo chiến lược
    "bỏ qua và log lỗi" của project.
    """
    try:
        tool = await _get_tavily_tool()

        raw_output = await tool.ainvoke(
            {
                "query": query,
                "max_results": max_results,
            }
        )

        if isinstance(raw_output, list):
            text_block = next(
                (
                    item
                    for item in raw_output
                    if isinstance(item, dict) and item.get("type") == "text"
                ),
                None,
            )

            if text_block is None:
                raise ValueError("Không tìm thấy text content trong MCP response.")

            raw_json = json.loads(text_block["text"])

        elif isinstance(raw_output, str):
            raw_json = json.loads(raw_output)

        else:
            raise TypeError(
                f"Kiểu response không được hỗ trợ: {type(raw_output)}"
            )

        return normalize_tavily_result(raw_json, query=query)

    except Exception as e:
        print(f"⚠️  [tavily_search] Lỗi khi search '{query}': {e}")
        return ResearchResult(query=query, sources=[], provider="tavily")


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Tavily search thật
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.tools.tavily_search
#
# Kết quả mong đợi: in ra danh sách sources tìm được cho query test.
# ============================================================

# if __name__ == "__main__":
#     import asyncio

#     async def _debug():
#         test_query = "Model Context Protocol MCP AI agent"

#         print("=" * 60)
#         print(f"DEBUG: Tavily search cho query: '{test_query}'")
#         print("=" * 60)

#         result = await tavily_search(test_query, max_results=5)

#         print(f"\nQuery       : {result.query}")
#         print(f"Provider    : {result.provider}")
#         print(f"Số sources  : {len(result.sources)}")
#         print("-" * 60)

#         if not result.sources:
#             print("❌ Không có source nào được trả về. Kiểm tra lại:")
#             print("   - TAVILY_API_KEY trong .env có hợp lệ không?")
#             print("   - Raw response format có đúng như dự đoán không?")
#         else:
#             for i, source in enumerate(result.sources, start=1):
#                 print(f"\n[{i}] {source.title}")
#                 print(f"    URL   : {source.url}")
#                 print(f"    Score : {source.score}")
#                 print(f"    Content (200 ký tự đầu): {source.content[:200]}...")

#     asyncio.run(_debug())