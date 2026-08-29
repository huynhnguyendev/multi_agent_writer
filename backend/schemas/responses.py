"""
Pydantic models cho RESPONSE BODY của các API endpoint.

Đây là "hợp đồng" (contract) giữa backend và frontend - FE dựa vào
đúng các field ở đây để render UI (progress bar, danh sách task, plan
preview, bài viết cuối cùng...). Field nào FE cần mà chưa có ở đây
thì cần bổ sung thêm, KHÔNG để FE tự suy luận từ field khác.
"""

from datetime import datetime

from pydantic import BaseModel


class StartWorkflowResponse(BaseModel):
    """Response cho POST /workflow."""

    workflow_id: str


class TaskStatusItem(BaseModel):
    """1 dòng task trong danh sách tasks của WorkflowStatusResponse."""

    task_id: str
    title: str
    status: str  # pending | running | success | failed
    progress: int
    error_message: str | None = None


class PlanPreview(BaseModel):
    """
    Bản tóm tắt Plan để hiển thị ở màn hình xác nhận HITL - CHỈ những
    field "quan trọng" theo đúng yêu cầu UI của bạn (không cần dump
    toàn bộ Plan đầy đủ, ví dụ research_queries nội bộ không cần hiện
    cho user thấy).
    """

    title: str
    objective: str
    target_audience: str
    tone: str
    tasks: list[TaskStatusItem]  # dùng lại shape tương tự, nhưng status mặc định "pending"


class WorkflowStatusResponse(BaseModel):
    """
    Response cho GET /workflow/{id}/status - "nguồn sự thật" chính mà
    FE poll định kỳ để cập nhật toàn bộ UI (progress bar tổng, Plan,
    danh sách Task, lỗi).
    """

    workflow_id: str
    topic: str
    status: str  # pending | running | waiting_hitl | blocked | completed | failed
    current_node: str | None
    overall_progress: int

    plan_title: str | None
    plan_progress: int
    plan: PlanPreview | None = None  # chỉ có giá trị khi status == "waiting_hitl"

    tasks: list[TaskStatusItem]

    article_score: float | None
    error_message: str | None

    created_at: datetime
    updated_at: datetime


class ArticleResponse(BaseModel):
    """Response cho GET /workflow/{id}/article."""

    workflow_id: str
    title: str
    markdown: str
    word_count: int
    article_score: float | None


class HITLDecisionResponse(BaseModel):
    """Response cho POST /workflow/{id}/hitl."""

    workflow_id: str
    accepted: bool
    message: str


class ErrorLogResponse(BaseModel):
    """Response cho GET /workflow/{id}/errors."""

    workflow_id: str
    errors: list[str]