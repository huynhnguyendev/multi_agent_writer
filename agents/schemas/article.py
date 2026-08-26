"""
Schema cho bài viết cuối cùng.

Synthesizer nhận:
    WorkerOutput 1
    WorkerOutput 2
    WorkerOutput 3
    ...

rồi tổng hợp thành:
    FinalArticle

FinalArticle là output gần cuối của workflow, trước khi
đưa qua Evaluator để chấm điểm.
"""

from pydantic import BaseModel, Field

from agents.schemas.image import ImageSpec


class FinalArticle(BaseModel):
    """Bài viết hoàn chỉnh do Synthesizer tạo ra."""

    # Title cuối cùng
    title: str = Field(
        ...,
        description="Tiêu đề cuối cùng của bài viết",
    )

    # Toàn bộ bài viết ở Markdown
    markdown: str = Field(
        ...,
        description="Nội dung đầy đủ của bài viết dưới dạng Markdown",
    )

    # Số từ.
    # Có thể được tính bằng code sau khi generate (không cần LLM tính).
    word_count: int = Field(
        default=0,
        description="Số từ của bài viết",
    )

    # Danh sách section.
    # Ví dụ: ["Introduction", "What is MCP?", "Architecture", "Conclusion"]
    sections: list[str] = Field(
        default_factory=list,
        description="Danh sách tên các section trong bài viết",
    )

    # Danh sách ảnh đã được nhúng vào bài viết.
    # Giúp truy vết ảnh nào đã dùng, alt text, attribution (license/author).
    images: list[ImageSpec] = Field(
        default_factory=list,
        description="Danh sách ảnh đã nhúng vào bài viết",
    )

    # Danh sách task_id bị lỗi và đã bị bỏ qua khi tổng hợp
    # (theo chiến lược error handling: "bỏ qua và log lỗi").
    skipped_task_ids: list[str] = Field(
        default_factory=list,
        description="Các task_id bị lỗi, đã bị bỏ qua khi tổng hợp bài viết",
    )

    # Phiên bản hiện tại của bài viết (tăng dần mỗi lần revision).
    # Đồng bộ với revision_count trong WriterState, hữu ích để
    # so sánh các phiên bản khi debug trên LangSmith.
    version: int = Field(
        default=1,
        description="Phiên bản của bài viết (tăng sau mỗi lần revision)",
    )