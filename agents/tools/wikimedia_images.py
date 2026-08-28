"""
Wrapper gọi tool `wikimedia_search_images` từ Wikimedia MCP server (stdio).

Cách dùng:

    from agents.tools.wikimedia_images import search_wikimedia_images

    candidates: list[ImageCandidate] = await search_wikimedia_images("MCP architecture")

Lưu ý:
    - Tool trả về multi-content response gồm:
        + 1 block "text"  → YAML metadata (dùng để parse ra ImageCandidate)
        + 1 block "image" → composite thumbnail (bỏ qua, không cần dùng)
    - Kết quả được cache vào PostgreSQL (TTL 7 ngày) theo (query, limit,
      license) để tránh gọi lại Wikimedia cho cùng 1 query.
"""

from agents.cache import WIKIMEDIA_TTL_SECONDS, get_cached, set_cached
from agents.schemas.image import ImageCandidate
from agents.tools.mcp_client import get_mcp_client
from agents.tools.research_normalizer import normalize_wikimedia_result

WIKIMEDIA_TOOL_NAME = "wikimedia_search_images"
CACHE_PROVIDER = "wikimedia"


async def _get_wikimedia_tool():
    """Lấy tool 'wikimedia_search_images' từ MCP client."""
    client = get_mcp_client()
    tools = await client.get_tools(server_name="wikimedia")

    for tool in tools:
        if tool.name == WIKIMEDIA_TOOL_NAME:
            return tool

    raise RuntimeError(
        f"Không tìm thấy tool '{WIKIMEDIA_TOOL_NAME}' trên Wikimedia MCP server. "
        f"Các tool hiện có: {[t.name for t in tools]}"
    )


def _extract_text_block(raw_output) -> str:
    """
    Trích phần "text" content ra khỏi response (có thể là str hoặc
    list content blocks). Bỏ qua các block khác (ví dụ "image").
    """
    if isinstance(raw_output, str):
        return raw_output

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
        return text_block["text"]

    raise TypeError(f"Kiểu response không được hỗ trợ: {type(raw_output)}")


async def _call_wikimedia_search(
    query: str,
    limit: int,
    license: str,
    include_thumbnails: bool,
) -> list[ImageCandidate]:
    """Gọi thật sự tới Wikimedia MCP (KHÔNG qua cache), trả về list ImageCandidate."""
    tool = await _get_wikimedia_tool()

    raw_output = await tool.ainvoke(
        {
            "query": query,
            "limit": limit,
            "license": license,
            "include_thumbnails": include_thumbnails,
        }
    )

    raw_text = _extract_text_block(raw_output)
    return normalize_wikimedia_result(raw_text, query=query)


async def search_wikimedia_images(
    query: str,
    limit: int = 5,
    license: str = "all",
    include_thumbnails: bool = False,
) -> list[ImageCandidate]:
    """
    Gọi Wikimedia image search qua MCP, trả về list ImageCandidate đã normalize.

    Kiểm tra cache (PostgreSQL, TTL 7 ngày) trước khi gọi API thật.

    Args:
        query: Câu query tìm ảnh (ví dụ: "MCP architecture").
        limit: Số lượng kết quả tối đa (mặc định 5, tối đa 50 theo tool).
        license: "all" hoặc "no_restrictions" (CC0/Public Domain only).
        include_thumbnails: False mặc định để tiết kiệm token/băng thông.

    Nếu có lỗi, trả về list rỗng thay vì raise exception (theo chiến lược
    "bỏ qua và log lỗi").
    """
    cache_params = {
        "query": query,
        "limit": limit,
        "license": license,
    }

    try:
        cached = await get_cached(CACHE_PROVIDER, cache_params)
        if cached is not None:
            return [ImageCandidate(**item) for item in cached["candidates"]]
    except Exception as e:
        print(f"⚠️  [search_wikimedia_images] Lỗi khi đọc cache: {e}")

    try:
        candidates = await _call_wikimedia_search(query, limit, license, include_thumbnails)
    except Exception as e:
        print(f"⚠️  [search_wikimedia_images] Lỗi khi search '{query}': {e}")
        return []

    try:
        cache_value = {"candidates": [c.model_dump() for c in candidates]}
        await set_cached(CACHE_PROVIDER, cache_params, cache_value, WIKIMEDIA_TTL_SECONDS)
    except Exception as e:
        print(f"⚠️  [search_wikimedia_images] Lỗi khi ghi cache: {e}")

    return candidates


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Wikimedia search (có cache)
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.tools.wikimedia_images
# ============================================================

# if __name__ == "__main__":
#     import asyncio
#     import time

#     async def _debug():
#         test_query = "artificial intelligence robot"

#         print("=" * 60)
#         print(f"DEBUG: Wikimedia search cho query: '{test_query}'")
#         print("=" * 60)

#         # --- Lần 1: cache miss ---
#         print("\n### Lần 1: gọi API thật (cache miss) ###")
#         start = time.monotonic()
#         candidates_1 = await search_wikimedia_images(test_query, limit=5)
#         elapsed_1 = time.monotonic() - start

#         print(f"Số candidates : {len(candidates_1)}")
#         print(f"Thời gian     : {elapsed_1:.2f}s")

#         if not candidates_1:
#             print("❌ Không có candidate nào. Kiểm tra Wikimedia MCP connection.")
#             return

#         # --- Lần 2: cùng query -> cache hit, nhanh hơn ---
#         print("\n### Lần 2: cùng query (kỳ vọng cache hit) ###")
#         start = time.monotonic()
#         candidates_2 = await search_wikimedia_images(test_query, limit=5)
#         elapsed_2 = time.monotonic() - start

#         print(f"Số candidates : {len(candidates_2)}")
#         print(f"Thời gian     : {elapsed_2:.2f}s")

#         assert len(candidates_1) == len(candidates_2), "❌ Số candidates không khớp giữa 2 lần!"
#         assert elapsed_2 < elapsed_1, "❌ Cache hit phải nhanh hơn cache miss!"
#         print(f"\n✅ Cache hoạt động đúng: lần 2 nhanh hơn lần 1 ({elapsed_2:.2f}s < {elapsed_1:.2f}s)")

#     asyncio.run(_debug())