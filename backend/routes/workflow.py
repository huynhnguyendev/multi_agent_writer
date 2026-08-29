"""
API routes cho toàn bộ vòng đời 1 workflow: khởi tạo, poll trạng
thái, gửi quyết định HITL, lấy bài viết cuối cùng, download, xem lỗi.

Toàn bộ logic nghiệp vụ (chạy graph, resume, sync DB) nằm ở
backend/services/workflow_manager.py - router này CHỈ làm nhiệm vụ:
    1. Validate request (đã có Pydantic lo phần lớn).
    2. Gọi đúng hàm ở workflow_manager.
    3. Map kết quả sang response schema.
    4. Trả lỗi HTTP phù hợp (404, 400, 409...).
"""

from fastapi import APIRouter, HTTPException, Response

from agents.db.progress_tracker import get_workflow_with_tasks
from agents.schemas.user_request import UserRequest
from backend.schemas import (
    ArticleResponse,
    ErrorLogResponse,
    HITLDecisionRequest,
    HITLDecisionResponse,
    PlanPreview,
    StartWorkflowRequest,
    StartWorkflowResponse,
    TaskStatusItem,
    WorkflowStatusResponse,
)
from backend.services.workflow_manager import (
    get_final_article,
    get_pending_plan,
    pause_hitl_timeout,
    resume_hitl_timeout,
    start_workflow,
    submit_hitl_decision,
)

router = APIRouter(prefix="/workflow", tags=["workflow"])


# ============================================================
# POST /workflow - Khởi tạo workflow mới
# ============================================================

@router.post("", response_model=StartWorkflowResponse, status_code=201)
async def create_workflow(body: StartWorkflowRequest) -> StartWorkflowResponse:
    user_request = UserRequest(
        topic=body.topic,
        language=body.language,
        article_type=body.article_type,
        target_audience=body.target_audience,
        tone=body.tone,
        raw_input=body.raw_input or body.topic,
    )

    workflow_id = await start_workflow(user_request)
    return StartWorkflowResponse(workflow_id=workflow_id)


# ============================================================
# GET /workflow/{id}/status - Trạng thái tổng hợp (FE poll định kỳ)
# ============================================================

@router.get("/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_status(workflow_id: str) -> WorkflowStatusResponse:
    run = await get_workflow_with_tasks(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy workflow.")

    tasks = [
        TaskStatusItem(
            task_id=t.task_id,
            title=t.title,
            status=t.status,
            progress=t.progress,
            error_message=t.error_message,
        )
        for t in run.tasks
    ]

    plan_preview: PlanPreview | None = None
    if run.status == "waiting_hitl":
        pending_plan = get_pending_plan(workflow_id)
        if pending_plan is not None:
            plan_preview = PlanPreview(
                title=pending_plan["title"],
                objective=pending_plan["objective"],
                target_audience=pending_plan["target_audience"],
                tone=pending_plan["tone"],
                tasks=[
                    TaskStatusItem(
                        task_id=t["id"],
                        title=t["title"],
                        status="pending",
                        progress=0,
                    )
                    for t in pending_plan["tasks"]
                ],
            )

    return WorkflowStatusResponse(
        workflow_id=run.workflow_id,
        topic=run.topic,
        status=run.status,
        current_node=run.current_node,
        overall_progress=run.overall_progress,
        plan_title=run.plan_title,
        plan_progress=run.plan_progress,
        plan=plan_preview,
        tasks=tasks,
        article_score=run.article_score,
        error_message=run.error_message or None,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


# ============================================================
# POST /workflow/{id}/hitl - Gửi quyết định approve/edit/reject
# ============================================================

@router.post("/{workflow_id}/hitl", response_model=HITLDecisionResponse)
async def submit_hitl(workflow_id: str, body: HITLDecisionRequest) -> HITLDecisionResponse:
    run = await get_workflow_with_tasks(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy workflow.")

    if run.status != "waiting_hitl":
        raise HTTPException(
            status_code=409,
            detail=f"Workflow không ở trạng thái chờ HITL (status hiện tại: '{run.status}').",
        )

    edited_plan_dict = body.edited_plan.model_dump() if body.edited_plan else None

    ok = await submit_hitl_decision(
        workflow_id,
        action=body.action,
        edited_plan=edited_plan_dict,
        feedback=body.feedback,
    )

    if not ok:
        raise HTTPException(
            status_code=409,
            detail="Không thể gửi quyết định - workflow có thể đã được xử lý bởi request khác.",
        )

    return HITLDecisionResponse(
        workflow_id=workflow_id,
        accepted=True,
        message=f"Đã ghi nhận quyết định '{body.action}', workflow đang tiếp tục chạy.",
    )


# ============================================================
# POST /workflow/{id}/hitl/pause - Tạm dừng đếm giờ auto-approve
# ============================================================

@router.post("/{workflow_id}/hitl/pause", response_model=HITLDecisionResponse)
async def pause_hitl_countdown(workflow_id: str) -> HITLDecisionResponse:
    """
    Gọi khi user bắt đầu mở form Edit/Reject - dừng vô hạn bộ đếm
    auto-approve, tránh bị tự động chấp nhận Plan trong lúc họ chưa
    kịp điền xong.
    """
    run = await get_workflow_with_tasks(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy workflow.")
    if run.status != "waiting_hitl":
        raise HTTPException(status_code=409, detail="Workflow không ở trạng thái chờ HITL.")

    pause_hitl_timeout(workflow_id)
    return HITLDecisionResponse(
        workflow_id=workflow_id, accepted=True,
        message="Đã tạm dừng đếm giờ tự động chấp nhận.",
    )


# ============================================================
# POST /workflow/{id}/hitl/resume - Đếm lại giờ (khi user hủy form)
# ============================================================

@router.post("/{workflow_id}/hitl/resume", response_model=HITLDecisionResponse)
async def resume_hitl_countdown(workflow_id: str) -> HITLDecisionResponse:
    """
    Gọi khi user bấm Hủy ở form Edit/Reject để quay lại xem Plan mà
    không gửi quyết định gì - đếm lại từ đầu (fresh) bộ đếm auto-approve.
    """
    run = await get_workflow_with_tasks(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy workflow.")
    if run.status != "waiting_hitl":
        raise HTTPException(status_code=409, detail="Workflow không ở trạng thái chờ HITL.")

    resume_hitl_timeout(workflow_id)
    return HITLDecisionResponse(
        workflow_id=workflow_id, accepted=True,
        message="Đã tiếp tục đếm giờ tự động chấp nhận.",
    )


# ============================================================
# GET /workflow/{id}/article - Lấy bài viết cuối cùng
# ============================================================

@router.get("/{workflow_id}/article", response_model=ArticleResponse)
async def get_article(workflow_id: str) -> ArticleResponse:
    run = await get_workflow_with_tasks(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy workflow.")

    if run.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Bài viết chưa sẵn sàng (status hiện tại: '{run.status}').",
        )

    article = await get_final_article(workflow_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nội dung bài viết.")

    return ArticleResponse(
        workflow_id=workflow_id,
        title=article["title"],
        markdown=article["markdown"],
        word_count=article["word_count"],
        article_score=run.article_score,
    )


# ============================================================
# GET /workflow/{id}/download - Download file .md trực tiếp
# ============================================================

@router.get("/{workflow_id}/download")
async def download_article(workflow_id: str) -> Response:
    run = await get_workflow_with_tasks(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy workflow.")

    if run.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Bài viết chưa sẵn sàng (status hiện tại: '{run.status}').",
        )

    article = await get_final_article(workflow_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nội dung bài viết.")

    safe_filename = f"{workflow_id}.md"

    return Response(
        content=article["markdown"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


# ============================================================
# GET /workflow/{id}/errors - Danh sách lỗi đã ghi nhận
# ============================================================

@router.get("/{workflow_id}/errors", response_model=ErrorLogResponse)
async def get_errors(workflow_id: str) -> ErrorLogResponse:
    run = await get_workflow_with_tasks(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy workflow.")

    errors = [run.error_message] if run.error_message else []

    return ErrorLogResponse(workflow_id=workflow_id, errors=errors)