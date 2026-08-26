"""
Schema cho quyết định của node Supervisor.

Supervisor chịu trách nhiệm trả lời câu hỏi:
    "Yêu cầu này nên xử lý như thế nào?"

Một trong ba mode:

    closed_book
        → Chỉ dùng kiến thức của LLM

    open_book
        → Cần research thông tin bên ngoài

    hybrid
        → Kết hợp kiến thức LLM + thông tin mới từ Tavily

Ví dụ:
    User: "Giải thích Transformer là gì?"
    → closed_book

    User: "Tình hình MCP mới nhất năm 2026?"
    → open_book

    User: "Giải thích MCP và phân tích những thay đổi mới nhất."
    → hybrid
"""

from typing import Literal

from pydantic import BaseModel, Field

ResearchMode = Literal[
    "closed_book",
    "open_book",
    "hybrid",
]


class SupervisorDecision(BaseModel):
    """Quyết định điều phối của Supervisor cho toàn bộ workflow."""

    # Supervisor chọn chiến lược research
    mode: ResearchMode = Field(
        ...,
        description="Chiến lược research: closed_book / open_book / hybrid",
    )

    # Giải thích ngắn gọn tại sao chọn mode này.
    # Field này rất hữu ích khi debug trên LangSmith.
    reasoning: str = Field(
        ...,
        description="Lý do ngắn gọn Supervisor chọn mode này",
    )

    # Các query mà Supervisor đề xuất cho research.
    # Có thể rỗng nếu mode == "closed_book"
    research_queries: list[str] = Field(
        default_factory=list,
        description="Danh sách query gợi ý cho research (nếu cần)",
    )

    # Ngôn ngữ đã được Supervisor xác nhận/chuẩn hóa từ input gốc.
    # Hữu ích vì user có thể không nói rõ, Supervisor sẽ suy luận.
    language: str = Field(
        default="vi",
        description="Ngôn ngữ đã được xác nhận cho toàn bộ workflow",
    )