"""
Wrapper gọi tool `wikimedia_search_images` từ Wikimedia MCP server (stdio).

Cách dùng:

    from agents.tools.wikimedia_images import search_wikimedia_images

    candidates: list[ImageCandidate] = await search_wikimedia_images("MCP architecture")

Lưu ý:
    - Tool trả về multi-content response gồm:
        + 1 block "text"  → YAML metadata (dùng để parse ra ImageCandidate)
        + 1 block "image" → composite thumbnail (bỏ qua, không cần dùng)
    - License mặc định lọc theo "no_restrictions" (CC0/Public Domain) nếu
      cần an toàn tuyệt đối về bản quyền, nhưng mặc định để "all" theo
      đúng behavior gốc của tool, rồi để Synthesizer tự cân nhắc license
      khi attribution.
"""

from agents.schemas.image import ImageCandidate
from agents.tools.mcp_client import get_mcp_client
from agents.tools.research_normalizer import normalize_wikimedia_result

WIKIMEDIA_TOOL_NAME = "wikimedia_search_images"


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
    list content blocks, tương tự pattern đã gặp ở tavily_search.py).

    Bỏ qua các block khác (ví dụ "image" - composite thumbnail).
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


async def search_wikimedia_images(
    query: str,
    limit: int = 5,
    license: str = "all",
    include_thumbnails: bool = False,
) -> list[ImageCandidate]:
    """
    Gọi Wikimedia image search qua MCP, trả về list ImageCandidate đã normalize.

    Args:
        query: Câu query tìm ảnh (ví dụ: "MCP architecture").
        limit: Số lượng kết quả tối đa (mặc định 5, tối đa 50 theo tool).
        license: "all" hoặc "no_restrictions" (CC0/Public Domain only).
        include_thumbnails: False mặc định để tiết kiệm token/băng thông
            (composite thumbnail image không cần thiết cho pipeline này,
            vì Synthesizer chỉ cần URL + metadata để nhúng vào Markdown).

    Nếu có lỗi, trả về list rỗng thay vì raise exception (theo chiến lược
    "bỏ qua và log lỗi").
    """
    try:
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

    except Exception as e:
        print(f"⚠️  [search_wikimedia_images] Lỗi khi search '{query}': {e}")
        return []


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Wikimedia search thật
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.tools.wikimedia_images
#
# Kết quả mong đợi: in ra danh sách ImageCandidate tìm được cho query test.
# ============================================================

# if __name__ == "__main__":
#     import asyncio

#     async def _debug():
#         test_query = "artificial intelligence robot"

#         print("=" * 60)
#         print(f"DEBUG: Wikimedia search cho query: '{test_query}'")
#         print("=" * 60)

#         candidates = await search_wikimedia_images(test_query, limit=5)

#         print(f"\nSố candidates tìm được: {len(candidates)}")
#         print("-" * 60)

#         if not candidates:
#             print("❌ Không có candidate nào được trả về. Kiểm tra lại:")
#             print("   - Tool name có đúng 'wikimedia_search_images' không?")
#             print("   - Raw text format có đúng như dự đoán không?")
#             print("   - Thử print raw_output trực tiếp để xem cấu trúc thật.")
#         else:
#             for i, candidate in enumerate(candidates, start=1):
#                 print(f"\n[{i}] {candidate.title}")
#                 print(f"    URL        : {candidate.url}")
#                 print(f"    Source URL : {candidate.source_url}")
#                 print(f"    License    : {candidate.license}")
#                 print(f"    Author     : {candidate.author}")
#                 print(f"    Size       : {candidate.width}x{candidate.height}")

#     asyncio.run(_debug())