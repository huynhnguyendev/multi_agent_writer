"""
Pydantic models cho REQUEST BODY của các API endpoint.

Khác với agents/schemas/user_request.py (UserRequest - dùng nội bộ
cho LangGraph state), các model ở đây định nghĩa CHÍNH XÁC những gì
client (frontend) được phép gửi lên qua HTTP - có validation riêng
phù hợp với ngữ cảnh API (ví dụ giới hạn max 7 task khi edit Plan,
điều mà agents/schemas/plan.py đã có sẵn nhưng validate ở đây sớm hơn
để trả lỗi 400 rõ ràng, thay vì để lỗi rơi xuống tận Pydantic của
agents/schemas/plan.py).
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StartWorkflowRequest(BaseModel):
    """Body cho POST /workflow - khởi tạo 1 lần chạy workflow mới."""

    topic: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Chủ đề chính của bài viết",
    )
    language: str = Field(default="vi", description="Mã ngôn ngữ, ví dụ 'vi', 'en'")
    article_type: str = Field(default="blog", description="Loại bài viết: blog, tutorial, news...")
    target_audience: str | None = Field(default=None, description="Đối tượng độc giả")
    tone: str | None = Field(default=None, description="Văn phong mong muốn")
    raw_input: str | None = Field(
        default=None,
        max_length=2000,
        description="Câu input gốc của user (nếu khác topic), dùng cho Input Guardrails",
    )


class TaskEditRequest(BaseModel):
    """1 task trong Plan khi user chỉnh sửa qua form Edit."""

    id: str = Field(..., min_length=1, max_length=20)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    expected_output: str = Field(..., min_length=1)
    requires_research: bool = False
    research_queries: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    order: int = 0


class PlanEditRequest(BaseModel):
    """
    Toàn bộ Plan mà user gửi lên khi chọn 'Edit' ở bước HITL.

    Giới hạn tối đa 7 task được validate NGAY TẠI ĐÂY (tầng API) để
    trả lỗi 400 sớm và rõ ràng cho FE, thay vì để lỗi rơi xuống tận
    agents/schemas/plan.py (Plan schema) - dù cả 2 nơi đều chặn, chặn
    sớm ở API giúp FE hiển thị lỗi ngay khi user thao tác thay vì phải
    đợi round-trip qua graph.
    """

    title: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    target_audience: str = Field(..., min_length=1)
    tone: str = Field(..., min_length=1)
    estimated_sections: int = Field(default=0, ge=0)
    tasks: list[TaskEditRequest] = Field(..., min_length=3, max_length=7)

    @field_validator("tasks")
    @classmethod
    def validate_task_ids_unique(cls, tasks: list[TaskEditRequest]) -> list[TaskEditRequest]:
        """Chặn trùng task id ngay tại tầng API (tránh lỗi khó hiểu hơn ở agents/schemas/plan.py)."""
        ids = [t.id for t in tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("Các task phải có id duy nhất, không được trùng nhau.")
        return tasks


class HITLDecisionRequest(BaseModel):
    """Body cho POST /workflow/{id}/hitl - quyết định của user với Plan."""

    action: Literal["approved", "edited", "rejected"] = Field(
        ...,
        description="approved: chấp nhận plan | edited: đã sửa plan | rejected: yêu cầu tạo lại plan mới",
    )
    edited_plan: PlanEditRequest | None = Field(
        default=None,
        description="Bắt buộc phải có nếu action='edited'",
    )
    feedback: str | None = Field(
        default=None,
        max_length=1000,
        description="Lý do/yêu cầu chỉnh sửa, dùng khi action='rejected'",
    )

    @field_validator("edited_plan")
    @classmethod
    def edited_plan_required_when_edited(cls, v: PlanEditRequest | None, info) -> PlanEditRequest | None:
        action = info.data.get("action")
        if action == "edited" and v is None:
            raise ValueError("edited_plan là bắt buộc khi action='edited'.")
        return v