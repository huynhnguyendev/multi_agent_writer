"""
Schema cho quyết định của node HITL (Human-in-the-Loop).

Sau Planner:
    Planner → Plan → HITL → User

User có thể:
    1. Approve            (chấp nhận plan, tiếp tục workflow)
    2. Edit                (tự sửa plan thủ công, rồi tiếp tục)
    3. Reject              (yêu cầu Planner lập lại plan mới)
    4. Timeout (60s)       (không phản hồi → tự động approve)

HITL không cần gọi LLM — đây là node xử lý logic thuần + chờ input
từ user qua WebSocket/API.
"""

from typing import Literal

from pydantic import BaseModel, Field

# Hành động cụ thể mà user đã thực hiện (hoặc hệ thống tự suy ra do timeout).
HITLAction = Literal[
    "approved",       # User bấm approve
    "edited",         # User tự sửa plan rồi accept
    "rejected",       # User yêu cầu tạo lại plan mới
    "timeout",        # Không phản hồi trong 60s → tự động approve
]


class HITLDecision(BaseModel):
    """Kết quả xử lý tại node HITL."""

    # Hành động cụ thể đã xảy ra.
    action: HITLAction = Field(
        ...,
        description="Hành động của user (hoặc timeout tự động)",
    )

    # User có approve plan hay không.
    # True cho cả "approved", "edited", và "timeout".
    # False chỉ khi "rejected".
    approved: bool = Field(
        ...,
        description="True nếu plan được chấp nhận để tiếp tục workflow",
    )

    # True nếu user đã sửa Plan thủ công.
    edited: bool = Field(
        default=False,
        description="True nếu user đã chỉnh sửa plan thủ công",
    )

    # Feedback của user.
    # Ví dụ: "Thêm một section về MCP security."
    # Dùng khi action == "rejected" để Planner biết cần sửa gì khi tạo lại plan.
    feedback: str | None = Field(
        default=None,
        description="Feedback của user, dùng khi reject để Planner cải thiện",
    )

    # Thời gian (giây) đã trôi qua trước khi user phản hồi.
    # Hữu ích để log/debug UX (ví dụ: theo dõi user có thường timeout không).
    response_time_seconds: float | None = Field(
        default=None,
        description="Thời gian user phản hồi tính bằng giây (None nếu timeout)",
    )