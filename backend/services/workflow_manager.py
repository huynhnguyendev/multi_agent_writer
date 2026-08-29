"""
Lớp trung gian giữa API (FastAPI routes) và agents/graph.py.

Trách nhiệm:
    1. Chạy graph ở BACKGROUND (asyncio.create_task) - API trả response
       ngay lập tức, không block chờ cả workflow chạy xong.
    2. Theo dõi graph chạy qua astream(stream_mode="updates") - mỗi khi
       1 node hoàn thành, tự động đồng bộ tiến trình vào
       agents/db/progress_tracker.py (KHÔNG cần sửa gì trong
       agents/graph.py - toàn bộ "phiên dịch" tiến trình nằm ở đây,
       giữ agents/ không phụ thuộc ngược vào backend/).
    3. Khi graph dừng tại interrupt() (node hitl) - lưu trạng thái
       "waiting_hitl", lên lịch 1 task đếm 60s tự động approve nếu
       user không phản hồi kịp.
    4. Khi nhận quyết định HITL từ API - hủy timer đang đếm, resume
       graph bằng Command(resume=payload), tiếp tục chạy nền.

Cách dùng (trong backend/routes/workflow.py):

    from backend.services.workflow_manager import (
        start_workflow, submit_hitl_decision, get_status,
    )

    workflow_id = await start_workflow(user_request)
    status = await get_status(workflow_id)
    await submit_hitl_decision(workflow_id, action="approved")
"""

import asyncio
import sys
from typing import Any

from langgraph.types import Command

# Fix cho Windows: lặp lại phòng thủ giống các file khác, dù import
# agents.graph phía dưới cũng đã set policy này như side-effect.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from agents.db.progress_tracker import (
    NODE_PROGRESS,
    create_workflow_run,
    update_workflow_run,
    upsert_task,
)
from agents.graph import build_initial_state, get_compiled_graph
from agents.hitl_handler import HITL_INTERRUPT_TYPE
from agents.schemas.user_request import UserRequest
from agents.hooks import register_task_hook, unregister_task_hook

HITL_TIMEOUT_SECONDS = 300

# ============================================================
# STATE NỘI BỘ CỦA MODULE (in-memory, mất khi restart server)
# ============================================================
#
# _timeout_tasks: theo dõi background task đang đếm 60s cho mỗi
# workflow đang waiting_hitl, để có thể HỦY nếu user phản hồi kịp.
#
# _pending_plans: cache payload interrupt (Plan dict) mới nhất để
# GET /status trả về ngay mà không cần query lại graph state. Nếu
# server restart giữa chừng, thông tin này mất - nhưng workflow vẫn
# AN TOÀN (checkpoint Postgres vẫn giữ đủ state để resume), chỉ là
# FE tạm thời không có full Plan để hiển thị lại cho tới khi mình bổ
# sung fallback đọc từ graph.aget_state() (có thể làm sau nếu cần).
# ============================================================

_timeout_tasks: dict[str, asyncio.Task] = {}
_pending_plans: dict[str, dict] = {}


# ============================================================
# ENTRY POINTS CHO ROUTES
# ============================================================


async def start_workflow(user_request: UserRequest) -> str:
    """
    Tạo workflow_id mới, ghi record ban đầu vào DB, chạy graph ở
    background, trả về workflow_id NGAY LẬP TỨC (không đợi chạy xong).
    """
    import uuid

    workflow_id = str(uuid.uuid4())
    await create_workflow_run(workflow_id, topic=user_request.topic)

    initial_state = build_initial_state(user_request, workflow_id)
    asyncio.create_task(_run_graph(workflow_id, resume_input=initial_state))

    return workflow_id


async def submit_hitl_decision(
    workflow_id: str,
    action: str,
    edited_plan: dict | None = None,
    feedback: str | None = None,
) -> bool:
    """
    Nhận quyết định HITL từ user (qua API), hủy timer 60s đang đếm
    (nếu có), resume graph ở background.

    Returns:
        True nếu resume thành công (workflow đang ở trạng thái chờ),
        False nếu workflow_id không tồn tại hoặc không ở trạng thái
        waiting_hitl (tránh resume nhầm workflow đã chạy xong).
    """
    if workflow_id not in _pending_plans:
        return False

    _cancel_timeout(workflow_id)
    _pending_plans.pop(workflow_id, None)

    payload = {"action": action, "edited_plan": edited_plan, "feedback": feedback}
    asyncio.create_task(
        _run_graph(workflow_id, resume_input=Command(resume=payload))
    )

    return True


def pause_hitl_timeout(workflow_id: str) -> bool:
    """
    Tạm dừng vĩnh viễn bộ đếm auto-approve (cho tới khi resume) - gọi
    khi user bắt đầu mở form Edit/Reject, để họ có bao nhiêu thời gian
    cũng được, không lo bị "cướp" giữa chừng bởi timeout cũ.

    Trả về True nếu có gì đó để hủy, False nếu workflow không waiting_hitl.
    """
    if workflow_id not in _pending_plans:
        return False
    _cancel_timeout(workflow_id)
    return True


def resume_hitl_timeout(workflow_id: str) -> bool:
    """
    Lên lịch lại bộ đếm auto-approve (fresh, đủ HITL_TIMEOUT_SECONDS)
    khi user bấm Hủy ở form Edit/Reject để quay lại xem Plan mà KHÔNG
    gửi quyết định gì cả.

    Trả về False nếu workflow không còn waiting_hitl nữa (ví dụ đã bị
    resume bởi request khác trong lúc user đang mở form).
    """
    if workflow_id not in _pending_plans:
        return False
    _schedule_timeout(workflow_id)
    return True


def get_pending_plan(workflow_id: str) -> dict | None:
    """Lấy Plan (dạng dict) đang chờ user xác nhận, None nếu không có."""
    return _pending_plans.get(workflow_id)


async def get_final_article(workflow_id: str) -> dict | None:
    """
    Lấy nội dung FinalArticle đầy đủ (title, markdown, word_count) từ
    checkpoint của graph - đây là nguồn sự thật duy nhất cho nội dung
    bài viết, KHÔNG lưu trùng lặp vào bảng workflow_runs (giữ DB nhẹ,
    chỉ lưu metadata: score, status, output_path...).

    Trả về None nếu workflow chưa có final_article (chưa chạy tới
    Synthesizer, hoặc bị lỗi trước đó).
    """
    async with get_compiled_graph() as graph:
        config = {"configurable": {"thread_id": workflow_id}}
        state = await graph.aget_state(config)
        article = state.values.get("final_article")

        if article is None:
            return None

        return {
            "title": article.title,
            "markdown": article.markdown,
            "word_count": article.word_count,
        }


# ============================================================
# LOGIC CHẠY GRAPH Ở BACKGROUND
# ============================================================


async def _run_graph(workflow_id: str, resume_input: Any) -> None:
    """
    Chạy graph tới khi gặp interrupt (dừng chờ HITL) hoặc chạy xong
    hẳn (END). Đồng bộ tiến trình vào DB sau mỗi node hoàn thành.

    `resume_input` là 1 trong 2 dạng:
        - dict (WriterState đầy đủ)  -> chạy TỪ ĐẦU workflow mới.
        - Command(resume=...)         -> RESUME workflow đang chờ HITL.
    """
    await update_workflow_run(workflow_id, status="running")

    async def _task_hook(task_id: str, title: str, status: str, progress: int, error: str | None) -> None:
        await upsert_task(workflow_id, task_id, title, status=status, progress=progress, error_message=error)

    register_task_hook(workflow_id, _task_hook)

    try:
        async with get_compiled_graph() as graph:
            config = {"configurable": {"thread_id": workflow_id}}

            async for chunk in graph.astream(resume_input, config=config, stream_mode="updates"):
                await _handle_stream_chunk(workflow_id, chunk)

            final_state = await graph.aget_state(config)

            if final_state.next:
                return

            await _finalize_workflow(workflow_id, final_state.values)

    except Exception as e:
        await update_workflow_run(workflow_id, status="failed", error_message=str(e))
    finally:
        unregister_task_hook(workflow_id)


async def _handle_stream_chunk(workflow_id: str, chunk: dict) -> None:
    """
    Xử lý 1 chunk từ astream(stream_mode="updates") - mỗi chunk ứng
    với output của 1 node vừa chạy xong, dạng {node_name: output_dict}.

    Chunk đặc biệt {"__interrupt__": (Interrupt(...),)} báo hiệu graph
    vừa dừng lại (node hitl gọi interrupt()).
    """
    if "__interrupt__" in chunk:
        interrupt_obj = chunk["__interrupt__"][0]
        payload = interrupt_obj.value

        if payload.get("type") == HITL_INTERRUPT_TYPE:
            _pending_plans[workflow_id] = payload["plan"]
            await update_workflow_run(
                workflow_id, status="waiting_hitl", current_node="hitl",
                overall_progress=NODE_PROGRESS["hitl"],
                plan_title=payload["plan"].get("title"),
                plan_progress=100,
            )
            _schedule_timeout(workflow_id)
        return

    for node_name, output in chunk.items():
        await _sync_node_progress(workflow_id, node_name, output)


async def _sync_node_progress(workflow_id: str, node_name: str, output: dict) -> None:
    """Ánh xạ output của 1 node sang cập nhật DB tương ứng (progress %, task status...)."""
    progress = NODE_PROGRESS.get(node_name)

    if node_name == "guardrail":
        guardrail = output.get("guardrail")
        if guardrail is not None and not guardrail.is_valid:
            await update_workflow_run(
                workflow_id, status="blocked", current_node=node_name,
                overall_progress=progress or 0,
                error_message=guardrail.reason,
            )
            return
        await update_workflow_run(workflow_id, current_node=node_name, overall_progress=progress or 0)

    elif node_name == "planner":
        plan = output.get("plan")
        await update_workflow_run(
            workflow_id, current_node=node_name, overall_progress=progress or 0,
            plan_title=plan.title if plan else None,
        )

    elif node_name == "hitl":
        # Trường hợp approve/edit/reject xử lý XONG (không dừng lại nữa,
        # ví dụ do đã hết MAX_PLAN_REVISIONS nên tự ép approve) - cập
        # nhật lại status về "running" (thoát khỏi waiting_hitl).
        _pending_plans.pop(workflow_id, None)
        await update_workflow_run(workflow_id, status="running", current_node=node_name)

        approved_plan = output.get("approved_plan")
        if approved_plan is not None:
            for task in approved_plan.tasks:
                await upsert_task(workflow_id, task.id, task.title, status="pending", progress=0)

    elif node_name == "executor":
        await update_workflow_run(workflow_id, current_node=node_name, overall_progress=progress or 0)

    elif node_name == "synthesizer":
        final_article = output.get("final_article")
        await update_workflow_run(
            workflow_id, current_node=node_name, overall_progress=progress or 0,
            error_message="" if final_article is not None else "Synthesizer thất bại",
        )

    elif node_name == "evaluator":
        evaluation = output.get("evaluation")
        await update_workflow_run(
            workflow_id, current_node=node_name, overall_progress=progress or 0,
            article_score=evaluation.overall_score if evaluation else None,
        )

    elif node_name == "save_output":
        await update_workflow_run(workflow_id, current_node=node_name, overall_progress=progress or 100)

    else:
        if progress is not None:
            await update_workflow_run(workflow_id, current_node=node_name, overall_progress=progress)


async def _finalize_workflow(workflow_id: str, final_values: dict) -> None:
    """Cập nhật trạng thái cuối cùng khi graph đã chạy tới END."""
    output_markdown = final_values.get("output_markdown")
    guardrail = final_values.get("guardrail")

    if output_markdown:
        final_article = final_values.get("final_article")
        evaluation = final_values.get("evaluation")
        await update_workflow_run(
            workflow_id, status="completed", current_node="save_output",
            overall_progress=100,
            article_score=evaluation.overall_score if evaluation else None,
            output_path=None,  # đã lưu qua save_article_to_markdown trong node save_output
        )
    elif guardrail is not None and not guardrail.is_valid:
        pass  # đã set status="blocked" ngay tại _sync_node_progress
    else:
        errors = final_values.get("errors") or []
        await update_workflow_run(
            workflow_id, status="failed",
            error_message="; ".join(errors) if errors else "Workflow kết thúc bất thường",
        )


# ============================================================
# QUẢN LÝ TIMEOUT 60s CHO HITL
# ============================================================


def _schedule_timeout(workflow_id: str) -> None:
    """Lên lịch tự động resume với action='timeout' sau HITL_TIMEOUT_SECONDS."""
    _cancel_timeout(workflow_id)  # phòng trường hợp gọi trùng
    task = asyncio.create_task(_auto_timeout(workflow_id))
    _timeout_tasks[workflow_id] = task


def _cancel_timeout(workflow_id: str) -> None:
    """Hủy timer đang đếm cho workflow_id (nếu có), dùng khi user phản hồi kịp."""
    task = _timeout_tasks.pop(workflow_id, None)
    if task is not None and not task.done():
        task.cancel()


async def _auto_timeout(workflow_id: str) -> None:
    """Đợi HITL_TIMEOUT_SECONDS, nếu không bị hủy thì tự động resume với action='timeout'."""
    try:
        await asyncio.sleep(HITL_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        return  # user đã phản hồi kịp, không cần làm gì thêm

    if workflow_id not in _pending_plans:
        return  # đã được resume bằng cách khác trước khi task này kịp chạy

    _pending_plans.pop(workflow_id, None)
    payload = {"action": "timeout", "edited_plan": None, "feedback": None}
    await _run_graph(workflow_id, resume_input=Command(resume=payload))


# ============================================================
# DEBUG - Chạy trực tiếp file này để test toàn bộ workflow_manager
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m backend.services.workflow_manager
#
# CẢNH BÁO: đây là test tốn thời gian + API call thật (chạy full
# pipeline thật, tự động approve Plan sau khi phát hiện waiting_hitl).
# ============================================================

if __name__ == "__main__":
    from agents.db.connection import init_db
    from agents.db.progress_tracker import get_workflow_with_tasks

    async def _debug():
        print("=" * 60)
        print("DEBUG: Test Workflow Manager (full pipeline qua background task)")
        print("=" * 60)

        await init_db()

        user_request = UserRequest(
            topic="MCP (Model Context Protocol) cho AI Engineer",
            article_type="blog",
            target_audience="AI Engineer",
            tone="technical",
            language="vi",
            raw_input="Viết một bài blog ngắn bằng tiếng Việt về MCP cho AI Engineer.",
        )

        print("\n### Bước 1: start_workflow() ###")
        workflow_id = await start_workflow(user_request)
        print(f"✅ workflow_id = {workflow_id}")

        print("\n### Bước 2: Poll status tới khi waiting_hitl hoặc completed/failed ###")
        while True:
            await asyncio.sleep(2)
            run = await get_workflow_with_tasks(workflow_id)
            print(f"   status={run.status} | node={run.current_node} | progress={run.overall_progress}%")

            if run.status == "waiting_hitl":
                plan = get_pending_plan(workflow_id)
                print(f"\n✅ Đang chờ HITL. Plan title: '{plan['title']}' ({len(plan['tasks'])} tasks)")
                break
            if run.status in ("completed", "failed", "blocked"):
                print(f"\n⚠️  Workflow kết thúc sớm (status={run.status}) trước khi tới HITL.")
                return

        print("\n### Bước 3: Tự động submit_hitl_decision(action='approved') ###")
        ok = await submit_hitl_decision(workflow_id, action="approved")
        assert ok, "❌ submit_hitl_decision thất bại!"
        print("✅ Đã gửi quyết định approve, graph tiếp tục chạy...")

        print("\n### Bước 4: Poll tiếp tới khi completed/failed ###")
        while True:
            await asyncio.sleep(3)
            run = await get_workflow_with_tasks(workflow_id)
            tasks_summary = ", ".join(f"{t.task_id}:{t.status}" for t in run.tasks)
            print(f"   status={run.status} | node={run.current_node} | progress={run.overall_progress}% | tasks=[{tasks_summary}]")

            if run.status in ("completed", "failed"):
                break

        print("\n" + "=" * 60)
        print("KẾT QUẢ CUỐI CÙNG")
        print("=" * 60)
        print(f"status        : {run.status}")
        print(f"article_score : {run.article_score}")
        print(f"error_message : {run.error_message}")

        assert run.status == "completed", f"❌ Kỳ vọng completed, nhận được: {run.status}"
        print("\n✅ Test pass: workflow_manager chạy full pipeline qua background task thành công!")

    asyncio.run(_debug())