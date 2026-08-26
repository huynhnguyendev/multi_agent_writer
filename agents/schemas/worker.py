"""
Schema cho output của một Worker và state riêng của Worker.

Worker nhận một Task:
    Task → Worker → WorkerOutput

Worker có thể:
    - sử dụng knowledge của LLM
    - sử dụng Tavily (research)
    - sử dụng MCP
    - tìm image query

Nhưng cuối cùng phải trả về một WorkerOutput có format thống nhất.

WorkerState là state riêng cho MỖI Worker khi LangGraph fan-out
(mỗi task tương ứng với 1 WorkerState độc lập, chạy song song
hoặc theo batch tùy dependency).
"""

from typing import TypedDict

from pydantic import BaseModel, Field

from agents.schemas.plan import Task
from agents.schemas.research import ResearchSource
from agents.schemas.supervisor import SupervisorDecision
from agents.schemas.user_request import UserRequest


class WorkerOutput(BaseModel):
    """Kết quả một Worker trả về sau khi xử lý xong 1 task."""

    # Worker đang xử lý task nào?
    # Dùng để Synthesizer biết section này thuộc task nào.
    task_id: str = Field(
        ...,
        description="ID của task mà worker này đã xử lý",
    )

    # Title của section
    title: str = Field(
        ...,
        description="Tiêu đề của section",
    )

    # Nội dung section
    content: str = Field(
        ...,
        description="Nội dung markdown của section",
    )

    # Các nguồn mà Worker thực sự sử dụng.
    # Có thể rỗng nếu Worker không research.
    sources: list[ResearchSource] = Field(
        default_factory=list,
        description="Các nguồn research thực sự đã dùng",
    )

    # Worker có thực sự sử dụng research không.
    # Lưu lại để debug, LangSmith tracing, kiểm tra factuality.
    used_research: bool = Field(
        default=False,
        description="True nếu worker đã thực sự gọi research tool",
    )

    # Worker đề xuất các query tìm ảnh.
    # Ví dụ: ["MCP architecture", "AI agent tools"]
    image_queries: list[str] = Field(
        default_factory=list,
        description="Danh sách query gợi ý để tìm ảnh minh họa cho section này",
    )

    # ==========================================================
    # ERROR HANDLING
    # ==========================================================
    # Theo yêu cầu: "Bỏ qua và log lỗi" khi có lỗi xảy ra.
    # Field này giúp Synthesizer biết section nào bị lỗi (nếu có)
    # để có thể xử lý phù hợp (bỏ qua section đó, dùng placeholder, v.v.)
    # thay vì làm sập toàn bộ workflow.
    # ==========================================================
    success: bool = Field(
        default=True,
        description="False nếu worker gặp lỗi trong quá trình xử lý task",
    )

    error: str | None = Field(
        default=None,
        description="Thông báo lỗi nếu success=False",
    )

    # Số lần task này đã được retry (nếu Executor có retry logic riêng
    # cho từng worker khi gặp lỗi tạm thời, ví dụ lỗi API timeout).
    retry_count: int = Field(
        default=0,
        description="Số lần worker này đã được retry",
    )


class WorkerState(TypedDict):
    """State riêng cho MỘT Worker khi LangGraph fan-out."""

    # Task mà Worker hiện tại phải thực hiện
    task: Task

    # User request ban đầu.
    # Worker cần context này để biết chủ đề, ngôn ngữ, audience, tone.
    user_request: UserRequest

    # Quyết định của Supervisor.
    # Worker có thể dùng nó làm global context (mode, research_queries chung).
    supervisor: SupervisorDecision | None

    # Kết quả của Worker.
    # Ban đầu: None
    # Sau khi chạy: WorkerOutput(...)
    result: WorkerOutput | None