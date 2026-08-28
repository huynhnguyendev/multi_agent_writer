"""
Image Resolver - chạy SAU Executor, TRƯỚC Synthesizer.

Nhiệm vụ: với mỗi WorkerOutput thành công có đề xuất image_queries,
gọi Wikimedia MCP để tìm ảnh thật, chọn ra 1 candidate tốt nhất, và
trả về danh sách ImageSpec (mỗi ImageSpec gắn với 1 task_id cụ thể).

Ảnh là phần "có thì tốt, không có cũng không sao" (optional
enhancement) - nếu 1 task không tìm được ảnh phù hợp, đơn giản là bỏ
qua (không gắn ảnh cho section đó), KHÔNG coi đây là lỗi nghiêm trọng
làm fail cả task (khác với lỗi LLM/research ở Worker).
"""

import asyncio

from agents.schemas import ImageCandidate, ImageSpec, WorkerOutput
from agents.tools import search_wikimedia_images

# Chỉ lấy query ĐẦU TIÊN mà Worker đề xuất cho mỗi task (Worker có thể
# đề xuất tối đa 2 query theo worker.yaml, nhưng 1 ảnh/section là đủ).
IMAGES_PER_TASK = 1
CANDIDATES_TO_FETCH = 3


def _pick_best_candidate(candidates: list[ImageCandidate]) -> ImageCandidate | None:
    """
    Chọn candidate tốt nhất trong danh sách tìm được.

    Ưu tiên ảnh có kích thước lớn hơn (thường là ảnh chất lượng/chi
    tiết hơn, ít khả năng là icon/thumbnail nhỏ không phù hợp minh
    họa bài viết). Nếu không có candidate nào, trả về None.
    """
    if not candidates:
        return None

    def _area(c: ImageCandidate) -> int:
        return (c.width or 0) * (c.height or 0)

    return max(candidates, key=_area)


async def _resolve_one(output: WorkerOutput) -> ImageSpec | None:
    """
    Resolve ảnh cho 1 WorkerOutput cụ thể. Trả về None nếu task không
    đề xuất image_queries nào, hoặc tìm không ra candidate nào phù hợp.
    """
    if not output.image_queries:
        return None

    query = output.image_queries[0]

    try:
        candidates = await search_wikimedia_images(query, limit=CANDIDATES_TO_FETCH)
    except Exception as e:
        print(f"⚠️  [image_resolver] Lỗi khi tìm ảnh cho '{output.task_id}': {e}")
        return None

    if not candidates:
        print(f"ℹ️  [image_resolver] Không tìm được ảnh nào cho task '{output.task_id}' (query: '{query}')")
        return None

    selected = _pick_best_candidate(candidates)

    return ImageSpec(
        task_id=output.task_id,
        query=query,
        alt_text=output.title,
        candidates=candidates,
        selected=selected,
    )


async def resolve_images(worker_outputs: list[WorkerOutput]) -> list[ImageSpec]:
    """
    Entry point chính - resolve ảnh cho TẤT CẢ WorkerOutput thành công
    trong danh sách, chạy song song (mỗi task 1 lần gọi Wikimedia).

    Chỉ xử lý output.success=True (bỏ qua các task đã lỗi từ Executor,
    vì section đó cũng sẽ không xuất hiện trong bài viết cuối cùng).
    """
    successful_outputs = [o for o in worker_outputs if o.success]

    results = await asyncio.gather(
        *[_resolve_one(output) for output in successful_outputs]
    )

    specs = [spec for spec in results if spec is not None]

    print(f"🖼️  [image_resolver] Resolve được {len(specs)}/{len(successful_outputs)} ảnh.")
    return specs


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Image Resolver
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.executor.image_resolver
# ============================================================

# if __name__ == "__main__":

#     def _print_spec(spec: ImageSpec) -> None:
#         print(f"\nTask ID    : {spec.task_id}")
#         print(f"Query      : {spec.query}")
#         print(f"Alt text   : {spec.alt_text}")
#         print(f"Số candidates: {len(spec.candidates)}")
#         if spec.selected:
#             print(f"Selected   : {spec.selected.url}")
#             print(f"  Size     : {spec.selected.width}x{spec.selected.height}")
#             print(f"  License  : {spec.selected.license}")
#             print(f"  Author   : {spec.selected.author}")

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test Image Resolver")
#         print("=" * 60)

#         fake_outputs = [
#             WorkerOutput(
#                 task_id="task_01",
#                 title="Giới thiệu MCP",
#                 content="...",
#                 success=True,
#                 image_queries=["artificial intelligence network diagram"],
#             ),
#             WorkerOutput(
#                 task_id="task_02",
#                 title="Không có image query",
#                 content="...",
#                 success=True,
#                 image_queries=[],  # kỳ vọng: bị bỏ qua, không lỗi
#             ),
#             WorkerOutput(
#                 task_id="task_03",
#                 title="Task bị lỗi từ Executor",
#                 content="",
#                 success=False,
#                 image_queries=["robot"],  # kỳ vọng: bị bỏ qua vì success=False
#             ),
#             WorkerOutput(
#                 task_id="task_04",
#                 title="Query hiếm gặp",
#                 content="...",
#                 success=True,
#                 image_queries=["xyzabc123nonexistentqueryterm"],  # kỳ vọng: không tìm ra, bị bỏ qua
#             ),
#         ]

#         specs = await resolve_images(fake_outputs)

#         print(f"\nTổng số ImageSpec trả về: {len(specs)}")
#         for spec in specs:
#             _print_spec(spec)

#         resolved_task_ids = {s.task_id for s in specs}
#         assert "task_02" not in resolved_task_ids, "❌ task_02 (không có query) không nên có ảnh!"
#         assert "task_03" not in resolved_task_ids, "❌ task_03 (lỗi) không nên có ảnh!"
#         print("\n✅ Đúng: task_02 và task_03 bị bỏ qua như kỳ vọng.")

#     asyncio.run(_debug())