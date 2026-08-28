"""
Lớp "báo cáo tiến trình" cho UI/API - ghi nhận trạng thái workflow_runs
và workflow_tasks (agents/db/models.py) song song với việc graph.py
chạy các node. KHÔNG thay thế checkpoint của LangGraph (checkpoint vẫn
lo việc resume/replay graph), file này chỉ phục vụ mục đích hiển thị
tiến trình % và trạng thái real-time cho frontend sau này.

Cách dùng dự kiến ở graph.py (sẽ tích hợp ở bước sau):

    from agents.db.progress_tracker import (
        create_workflow_run, update_workflow_run, upsert_task,
        NODE_PROGRESS,
    )

    await create_workflow_run(state["workflow_id"], user_request.topic)
    ...
    await update_workflow_run(
        state["workflow_id"],
        status="running",
        current_node="planner",
        overall_progress=NODE_PROGRESS["planner"],
    )
"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from agents.db.connection import get_session
from agents.db.models import WorkflowRun, WorkflowTask

# ============================================================
# NODE PROGRESS MAP
# ============================================================
#
# Ánh xạ mỗi node trong graph.py sang % tiến trình tổng thể tương ứng
# (dùng cho overall_progress của WorkflowRun). Đây chỉ là ước lượng
# hợp lý theo thứ tự các node trong workflow, KHÔNG cần chính xác
# tuyệt đối - mục đích chính là cho UI 1 con số tăng dần hợp lý.
#
# executor chiếm khoảng cách lớn nhất (40->65) vì đây là giai đoạn
# tốn thời gian nhất (nhiều LLM call song song + research).
# ============================================================

NODE_PROGRESS: dict[str, int] = {
    "guardrail": 5,
    "supervisor": 15,
    "planner": 25,
    "hitl": 35,
    "executor": 65,
    "image_resolver": 75,
    "synthesizer": 85,
    "evaluator": 95,
    "save_output": 100,
}


async def create_workflow_run(workflow_id: str, topic: str) -> None:
    """
    Tạo 1 record WorkflowRun mới với status="pending".

    Nếu workflow_id đã tồn tại (ví dụ resume lại workflow cũ), KHÔNG
    tạo record trùng - giữ nguyên record cũ để không mất lịch sử.
    """
    async with get_session() as session:
        existing = await session.get(WorkflowRun, workflow_id)
        if existing is not None:
            return

        run = WorkflowRun(
            workflow_id=workflow_id,
            topic=topic,
            status="pending",
            overall_progress=0,
            plan_progress=0,
        )
        session.add(run)
        await session.commit()


async def update_workflow_run(
    workflow_id: str,
    status: str | None = None,
    current_node: str | None = None,
    overall_progress: int | None = None,
    plan_title: str | None = None,
    plan_progress: int | None = None,
    article_score: float | None = None,
    output_path: str | None = None,
    error_message: str | None = None,
) -> None:
    """
    Cập nhật 1 phần (partial update) của WorkflowRun đã tồn tại.

    CHỈ những tham số được truyền vào (khác None) mới được cập nhật -
    tham số nào để None (mặc định) thì giữ nguyên giá trị cũ trong DB.
    Do đó hàm này KHÔNG dùng để xóa/reset 1 field về NULL; nếu sau này
    cần reset (ví dụ xóa error_message khi retry thành công), gọi
    riêng với chuỗi rỗng "" thay vì None.

    Bỏ qua im lặng (không raise lỗi) nếu workflow_id chưa tồn tại
    trong DB - tránh làm crash graph.py chỉ vì lỗi ghi log tiến trình
    (đây là lớp phụ trợ, không phải logic nghiệp vụ cốt lõi).
    """
    async with get_session() as session:
        run = await session.get(WorkflowRun, workflow_id)
        if run is None:
            return

        if status is not None:
            run.status = status
        if current_node is not None:
            run.current_node = current_node
        if overall_progress is not None:
            run.overall_progress = overall_progress
        if plan_title is not None:
            run.plan_title = plan_title
        if plan_progress is not None:
            run.plan_progress = plan_progress
        if article_score is not None:
            run.article_score = article_score
        if output_path is not None:
            run.output_path = output_path
        if error_message is not None:
            run.error_message = error_message

        await session.commit()


async def upsert_task(
    workflow_id: str,
    task_id: str,
    title: str,
    status: str,
    progress: int = 0,
    error_message: str | None = None,
) -> None:
    """
    Tạo mới hoặc cập nhật 1 WorkflowTask theo (workflow_id, task_id).

    Dùng "upsert" vì Executor sẽ gọi hàm này nhiều lần cho CÙNG 1 task
    khi trạng thái thay đổi theo thời gian (pending -> running ->
    success/failed) - lần đầu tạo mới, các lần sau tìm record cũ để
    update thay vì tạo trùng.
    """
    async with get_session() as session:
        result = await session.execute(
            select(WorkflowTask).where(
                WorkflowTask.workflow_id == workflow_id,
                WorkflowTask.task_id == task_id,
            )
        )
        task = result.scalar_one_or_none()

        if task is None:
            task = WorkflowTask(
                workflow_id=workflow_id,
                task_id=task_id,
                title=title,
                status=status,
                progress=progress,
                error_message=error_message,
            )
            session.add(task)
        else:
            task.title = title
            task.status = status
            task.progress = progress
            if error_message is not None:
                task.error_message = error_message

        await session.commit()


async def get_workflow_with_tasks(workflow_id: str) -> WorkflowRun | None:
    """
    Lấy 1 WorkflowRun kèm TOÀN BỘ workflow_tasks liên quan (eager load
    bằng selectinload để tránh lỗi MissingGreenlet khi access
    `.tasks` sau khi session đã đóng - đây chính là hàm dùng cho API
    GET /workflow/{id}/status sau này).

    Trả về None nếu không tìm thấy workflow_id.
    """
    async with get_session() as session:
        result = await session.execute(
            select(WorkflowRun)
            .options(selectinload(WorkflowRun.tasks))
            .where(WorkflowRun.workflow_id == workflow_id)
        )
        return result.scalar_one_or_none()


# ============================================================
# DEBUG - Chạy trực tiếp file này để test toàn bộ Progress Tracker
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.db.progress_tracker
#
# Mô phỏng 1 lượt chạy workflow rút gọn qua các node, kiểm tra progress
# tổng thể + trạng thái từng task cập nhật đúng theo thời gian.
# ============================================================

# if __name__ == "__main__":
#     import asyncio

#     from agents.db.connection import close_engine, init_db

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test Progress Tracker")
#         print("=" * 60)

#         await init_db()
#         workflow_id = "debug-progress-test-001"

#         # Dọn record cũ nếu có, để test lại nhiều lần không bị vướng
#         async with get_session() as session:
#             existing = await session.get(WorkflowRun, workflow_id)
#             if existing:
#                 await session.delete(existing)
#                 await session.commit()

#         print("\n### Bước 1: Tạo WorkflowRun mới (pending) ###")
#         await create_workflow_run(workflow_id, topic="MCP cho AI Engineer")
#         run = await get_workflow_with_tasks(workflow_id)
#         assert run.status == "pending" and run.overall_progress == 0
#         print(f"✅ {run}")

#         print("\n### Bước 2: Mô phỏng lần lượt qua các node ###")
#         for node in ["guardrail", "supervisor", "planner"]:
#             await update_workflow_run(
#                 workflow_id,
#                 status="running",
#                 current_node=node,
#                 overall_progress=NODE_PROGRESS[node],
#             )
#             run = await get_workflow_with_tasks(workflow_id)
#             print(f"   [{node}] overall_progress={run.overall_progress}")

#         await update_workflow_run(workflow_id, plan_title="Giải mã MCP", plan_progress=100)

#         print("\n### Bước 3: HITL approve -> Executor với 3 task ###")
#         await update_workflow_run(
#             workflow_id, status="running", current_node="executor",
#             overall_progress=NODE_PROGRESS["executor"],
#         )

#         tasks_info = [
#             ("task_01", "Giới thiệu MCP"),
#             ("task_02", "Kiến trúc MCP"),
#             ("task_03", "Kết luận"),
#         ]

#         for task_id, title in tasks_info:
#             await upsert_task(workflow_id, task_id, title, status="pending", progress=0)

#         # Giả lập 3 task chạy song song: running -> success/failed
#         for task_id, title in tasks_info:
#             await upsert_task(workflow_id, task_id, title, status="running", progress=50)

#         await upsert_task(workflow_id, "task_01", "Giới thiệu MCP", status="success", progress=100)
#         await upsert_task(workflow_id, "task_02", "Kiến trúc MCP", status="success", progress=100)
#         await upsert_task(
#             workflow_id, "task_03", "Kết luận", status="failed", progress=100,
#             error_message="LLM timeout sau 3 lần retry",
#         )

#         run = await get_workflow_with_tasks(workflow_id)
#         print(f"   Số task: {len(run.tasks)}")
#         for t in run.tasks:
#             print(f"   - {t}")

#         assert len(run.tasks) == 3, "❌ Số task không đúng!"
#         success_count = sum(1 for t in run.tasks if t.status == "success")
#         assert success_count == 2, "❌ Số task success không đúng!"
#         print("✅ Upsert task hoạt động đúng (không tạo trùng record khi update trạng thái).")

#         print("\n### Bước 4: Hoàn thành workflow (save_output) ###")
#         await update_workflow_run(
#             workflow_id,
#             status="completed",
#             current_node="save_output",
#             overall_progress=100,
#             article_score=8.7,
#             output_path="outputs/fake-article.md",
#         )

#         run = await get_workflow_with_tasks(workflow_id)
#         assert run.status == "completed" and run.overall_progress == 100
#         assert run.article_score == 8.7
#         print(f"✅ {run}")
#         print(f"   article_score={run.article_score}, output_path={run.output_path}")

#         print("\n### Bước 5: get_workflow_with_tasks với workflow_id KHÔNG tồn tại ###")
#         none_run = await get_workflow_with_tasks("khong-ton-tai-123")
#         assert none_run is None, "❌ Phải trả về None khi không tìm thấy!"
#         print("✅ Trả về None đúng như kỳ vọng.")

#         await close_engine()
#         print("\n✅ Tất cả test pass!")

#     asyncio.run(_debug())