"""
Wrapper gọi tool `tavily_search` từ Tavily MCP server (remote).

Cách dùng:

    from agents.tools.tavily_search import tavily_search

    result: ResearchResult = await tavily_search("MCP cho AI Engineer")

Lưu ý:
    - Tool name chính xác trên Tavily MCP là "tavily_search".
    - Kết quả trả về từ MCP tool là list content blocks
      ({"type": "text", "text": "..."}), cần extract đúng block.
    - Kết quả được cache vào PostgreSQL (TTL 24h) theo (query, max_results)
      để tránh gọi lại Tavily API cho cùng 1 query trong thời gian ngắn.
"""

import json

from agents.cache import TAVILY_TTL_SECONDS, get_cached, set_cached
from agents.schemas.research import ResearchResult
from agents.tools.mcp_client import get_mcp_client
from agents.tools.research_normalizer import normalize_tavily_result

TAVILY_TOOL_NAME = "tavily_search"
CACHE_PROVIDER = "tavily"


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


async def _call_tavily_search(query: str, max_results: int) -> ResearchResult:
    """Gọi thật sự tới Tavily MCP (KHÔNG qua cache), trả về ResearchResult."""
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
        raise TypeError(f"Kiểu response không được hỗ trợ: {type(raw_output)}")

    return normalize_tavily_result(raw_json, query=query)


async def tavily_search(
    query: str,
    max_results: int = 5,
) -> ResearchResult:
    """
    Gọi Tavily search qua MCP, trả về ResearchResult đã normalize.

    Kiểm tra cache (PostgreSQL, TTL 24h) trước khi gọi API thật. Nếu
    cache hit, trả về ngay với from_cache=True (không tốn API call).

    Nếu có lỗi (API fail, parse fail, lỗi mạng...), trả về ResearchResult
    rỗng (sources=[]) thay vì raise exception, theo chiến lược
    "bỏ qua và log lỗi" của project.
    """
    cache_params = {"query": query, "max_results": max_results}

    try:
        cached = await get_cached(CACHE_PROVIDER, cache_params)
        if cached is not None:
            result = ResearchResult(**cached)
            result.from_cache = True
            return result
    except Exception as e:
        # Lỗi đọc cache KHÔNG được làm fail cả pipeline research - chỉ
        # log rồi tiếp tục gọi API thật như bình thường.
        print(f"⚠️  [tavily_search] Lỗi khi đọc cache: {e}")

    try:
        result = await _call_tavily_search(query, max_results)
    except Exception as e:
        print(f"⚠️  [tavily_search] Lỗi khi search '{query}': {e}")
        return ResearchResult(query=query, sources=[], provider="tavily")

    try:
        await set_cached(CACHE_PROVIDER, cache_params, result.model_dump(), TAVILY_TTL_SECONDS)
    except Exception as e:
        # Lỗi ghi cache cũng không được làm fail kết quả đã research
        # thành công - chỉ log, vẫn trả về result bình thường.
        print(f"⚠️  [tavily_search] Lỗi khi ghi cache: {e}")

    return result


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Tavily search (có cache)
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.tools.tavily_search
# ============================================================

# if __name__ == "__main__":
#     import asyncio
#     import time

#     async def _debug():
#         test_query = "Model Context Protocol MCP AI agent"

#         print("=" * 60)
#         print(f"DEBUG: Tavily search cho query: '{test_query}'")
#         print("=" * 60)

#         # --- Lần 1: chắc chắn cache miss (gọi API thật) ---
#         print("\n### Lần 1: gọi API thật (cache miss) ###")
#         start = time.monotonic()
#         result_1 = await tavily_search(test_query, max_results=5)
#         elapsed_1 = time.monotonic() - start

#         print(f"from_cache : {result_1.from_cache}")
#         print(f"Số sources : {len(result_1.sources)}")
#         print(f"Thời gian  : {elapsed_1:.2f}s")

#         if not result_1.sources:
#             print("❌ Không có source nào. Kiểm tra TAVILY_API_KEY / MCP connection.")
#             return

#         # --- Lần 2: cùng query -> phải cache hit, nhanh hơn hẳn ---
#         print("\n### Lần 2: cùng query (kỳ vọng cache hit) ###")
#         start = time.monotonic()
#         result_2 = await tavily_search(test_query, max_results=5)
#         elapsed_2 = time.monotonic() - start

#         print(f"from_cache : {result_2.from_cache}")
#         print(f"Số sources : {len(result_2.sources)}")
#         print(f"Thời gian  : {elapsed_2:.2f}s")

#         assert result_2.from_cache is True, "❌ Lần 2 phải là cache hit!"
#         assert elapsed_2 < elapsed_1, "❌ Cache hit phải nhanh hơn cache miss!"
#         print(f"\n✅ Cache hoạt động đúng: lần 2 nhanh hơn lần 1 ({elapsed_2:.2f}s < {elapsed_1:.2f}s)")

#     asyncio.run(_debug())