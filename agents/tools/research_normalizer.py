"""
Normalize dữ liệu thô (raw) trả về từ các MCP tools (Tavily, Wikimedia)
thành các Pydantic schema chuẩn của project (ResearchResult, ImageCandidate).

Mục đích: tách biệt "raw response format" của từng provider ra khỏi
phần logic chính (worker, executor). Sau này nếu đổi provider
(Tavily → Google Search, Wikimedia → Unsplash...) thì chỉ cần sửa
file này, không cần đụng vào Worker.
"""

import re

import yaml

from agents.schemas import ImageCandidate, ResearchResult, ResearchSource


# ============================================================
# TAVILY NORMALIZER
# ============================================================
#
# Tavily search API trả về JSON dạng:
# {
#     "query": "...",
#     "results": [
#         {
#             "title": "...",
#             "url": "...",
#             "content": "...",
#             "score": 0.87
#         },
#         ...
#     ]
# }
# ============================================================

def normalize_tavily_result(raw: dict, query: str) -> ResearchResult:
    """Chuyển raw JSON response từ Tavily thành ResearchResult chuẩn."""
    sources: list[ResearchSource] = []

    for item in raw.get("results", []):
        sources.append(
            ResearchSource(
                title=item.get("title", "Untitled"),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=item.get("score"),
            )
        )

    return ResearchResult(
        query=query,
        sources=sources,
        provider="tavily",
        from_cache=False,
    )


# ============================================================
# WIKIMEDIA NORMALIZER
# ============================================================
#
# Wikimedia MCP (wikimedia_search_images) trả về text dạng YAML,
# mỗi item có cấu trúc:
#
#   - index: 1
#     url: https://upload.wikimedia.org/.../330px-xxx.jpg
#     width: 3000
#     height: 2000
#     descriptionurl: https://commons.wikimedia.org/w/index.php?curid=...
#     caption: Felis catus-cat on snow
#     artist: Von.grzanka
#     license:
#       name: CC BY-SA 3.0
#       usageTerms: ...
#       url: https://creativecommons.org/licenses/by-sa/3.0
#
# Text trả về có thêm phần mô tả (prose) ở đầu/cuối, không phải
# YAML thuần túy, nên cần cắt phần list ra trước khi parse.
# ============================================================

def _extract_yaml_list_block(text: str) -> str:
    """
    Cắt phần YAML list (bắt đầu từ dòng '- index:') ra khỏi text,
    bỏ qua phần mô tả (prose) ở đầu và cuối.
    """
    lines = text.splitlines()

    start_idx = None
    end_idx = len(lines)

    # Các dòng "note" cuối thường thấy trong output của tool này,
    # dùng để xác định điểm kết thúc phần YAML list.
    stop_markers = (
        "If nothing found",
        "To download images",
        "Compare the images",
        "Showing",
    )

    for i, line in enumerate(lines):
        stripped = line.strip()
        if start_idx is None and re.match(r"^-\s*index:\s*\d+", stripped):
            start_idx = i
        elif start_idx is not None and any(
            stripped.startswith(marker) for marker in stop_markers
        ):
            end_idx = i
            break

    if start_idx is None:
        # Không tìm thấy block YAML nào -> không có kết quả
        return ""

    return "\n".join(lines[start_idx:end_idx])


def normalize_wikimedia_result(raw_text: str, query: str) -> list[ImageCandidate]:
    """
    Parse raw YAML text từ Wikimedia MCP thành danh sách ImageCandidate.

    Nếu parse lỗi (format thay đổi khác so với dự kiến), trả về list
    rỗng thay vì raise exception (theo chiến lược "bỏ qua và log lỗi").
    """
    yaml_block = _extract_yaml_list_block(raw_text)
    if not yaml_block:
        return []

    try:
        items = yaml.safe_load(yaml_block)
    except yaml.YAMLError as e:
        print(f"⚠️  [wikimedia normalizer] Lỗi parse YAML: {e}")
        return []

    if not isinstance(items, list):
        return []

    candidates: list[ImageCandidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        license_info = item.get("license") or {}
        license_name = (
            license_info.get("name") if isinstance(license_info, dict) else None
        )

        candidates.append(
            ImageCandidate(
                title=item.get("caption") or item.get("description") or query,
                url=item.get("url", ""),
                source_url=item.get("descriptionurl", ""),
                license=license_name,
                author=item.get("artist"),
                width=item.get("width"),
                height=item.get("height"),
            )
        )

    return candidates