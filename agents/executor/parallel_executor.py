"""
Node 5: Executor (Fan-out Workers).

Orchestrate việc chạy các Worker theo batch (dựa trên DAG đã tính ở
task_manager.py):
    - Trong CÙNG 1 batch: các task chạy SONG SONG (asyncio.gather).
    - GIỮA các batch: chạy TUẦN TỰ (batch sau chỉ chạy khi batch
      trước đã xong hết), vì batch sau có thể cần dependency_context
      từ batch trước.

Đây là entry point chính mà graph.py (sau này) sẽ gọi cho Node 5.
"""

import asyncio

from agents.executor.task_manager import build_execution_batches
from agents.executor.worker import run_worker
from agents.schemas import Plan, SupervisorDecision, UserRequest, WorkerOutput


async def execute_plan(
    plan: Plan,
    user_request: UserRequest,
    supervisor: SupervisorDecision | None = None,
) -> list[WorkerOutput]:
    """
    Entry point chính của node Executor.

    Args:
        plan: Plan đã được HITL approve (approved_plan trong WriterState).
        user_request: Yêu cầu gốc của user.
        supervisor: Quyết định của Supervisor (truyền cho Worker làm context).

    Returns:
        list[WorkerOutput] - kết quả của TẤT CẢ task trong plan, theo
        đúng thứ tự plan.tasks ban đầu (KHÔNG theo thứ tự batch chạy
        xong), để Synthesizer dễ dàng sắp xếp lại theo `task.order`.

    Lưu ý: Worker tự xử lý lỗi nội bộ (retry + trả về success=False),
    nên hàm này không cần try/except riêng cho từng worker - chỉ cần
    asyncio.gather bình thường (không dùng return_exceptions=True vì
    run_worker() đã đảm bảo không bao giờ raise exception ra ngoài).
    """
    batches = build_execution_batches(plan.tasks)

    all_outputs: list[WorkerOutput] = []

    for batch_index, batch in enumerate(batches, start=1):
        task_ids = [t.id for t in batch]
        print(f"\n🚀 [executor] Chạy Batch {batch_index}/{len(batches)}: {task_ids}")

        batch_outputs = await asyncio.gather(
            *[
                run_worker(
                    task=task,
                    user_request=user_request,
                    supervisor=supervisor,
                    completed_outputs=all_outputs,
                )
                for task in batch
            ]
        )

        for output in batch_outputs:
            status = "✅" if output.success else "❌"
            print(f"   {status} {output.task_id} hoàn thành")

        all_outputs.extend(batch_outputs)

    # Sắp xếp lại theo đúng thứ tự "order" trong Plan (thứ tự hiển thị
    # trong bài viết cuối cùng), KHÔNG theo thứ tự batch/id.
    order_by_task_id = {task.id: task.order for task in plan.tasks}
    all_outputs.sort(key=lambda output: order_by_task_id.get(output.task_id, 0))

    success_count = sum(1 for o in all_outputs if o.success)
    print(
        f"\n📊 [executor] Hoàn thành: {success_count}/{len(all_outputs)} "
        f"task thành công."
    )

    return all_outputs


# ============================================================
# DEBUG - Chạy trực tiếp file này để test toàn bộ Executor
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.executor.parallel_executor
#
# Test này chạy full pipeline: Planner thật -> Executor thật (gọi LLM
# + Tavily thật cho các task requires_research=True).
# ============================================================

# if __name__ == "__main__":
#     from agents.planner import run_planner

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test Parallel Executor (full pipeline)")
#         print("=" * 60)

#         user_request = UserRequest(
#             topic="MCP (Model Context Protocol) cho AI Engineer",
#             article_type="blog",
#             target_audience="AI Engineer",
#             tone="technical",
#             language="vi",
#             raw_input="Viết một bài blog bằng tiếng Việt về MCP cho AI Engineer, có so sánh với cách tích hợp tool truyền thống.",
#         )

#         supervisor_decision = SupervisorDecision(
#             mode="hybrid",
#             reasoning="Cần kiến thức nền tảng về MCP + thông tin cập nhật để so sánh.",
#             research_queries=["Model Context Protocol architecture"],
#             language="vi",
#         )

#         print("\n📋 Đang tạo Plan...")
#         plan = await run_planner(user_request, supervisor_decision)
#         print(f"✅ Plan có {len(plan.tasks)} tasks.")
#         for task in plan.tasks:
#             deps = task.depends_on or "—"
#             print(f"   [{task.id}] {task.title} (depends_on: {deps})")

#         print("\n⚙️  Đang chạy Executor...")
#         outputs = await execute_plan(plan, user_request, supervisor_decision)

#         print("\n" + "=" * 60)
#         print("KẾT QUẢ CUỐI CÙNG (đã sắp xếp theo order)")
#         print("=" * 60)

#         for output in outputs:
#             status = "✅" if output.success else "❌ LỖI"
#             print(f"\n[{output.task_id}] {status} - {output.title}")
#             if output.success:
#                 print(f"   Used research: {output.used_research}")
#                 print(f"   Content preview: {output.content[:150]}...")
#             else:
#                 print(f"   Error: {output.error}")

#     asyncio.run(_debug())