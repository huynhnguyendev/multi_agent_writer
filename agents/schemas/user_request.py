"""
Schema cho dữ liệu đầu vào ban đầu của người dùng.

Ví dụ user nhập:
    "Viết một bài blog bằng tiếng Việt về MCP cho AI Engineer."

Sau khi parse (do Supervisor/Planner xử lý), có thể trở thành:

    UserRequest(
        topic="MCP cho AI Engineer",
        language="vi",
        article_type="blog",
        target_audience="AI Engineer",
        tone="technical"
    )

Lưu ý: Không nhất thiết user phải cung cấp tất cả field.
Một số field có thể được Planner suy luận sau.
"""

from pydantic import BaseModel, Field


class UserRequest(BaseModel):
    """Dữ liệu request ban đầu từ người dùng."""

    # Chủ đề chính mà user muốn viết
    topic: str = Field(
        ...,
        description="Chủ đề chính của bài viết",
        min_length=1,
    )

    # Ngôn ngữ của bài viết
    language: str = Field(
        default="vi",
        description="Mã ngôn ngữ, ví dụ: 'vi', 'en'",
    )

    # Loại nội dung
    # Ví dụ: blog, tutorial, technical article...
    article_type: str = Field(
        default="blog",
        description="Loại bài viết: blog, tutorial, news, review...",
    )

    # Đối tượng độc giả. Có thể None nếu user không nói rõ.
    target_audience: str | None = Field(
        default=None,
        description="Đối tượng độc giả hướng tới",
    )

    # Văn phong.
    # Ví dụ: professional, technical, friendly, beginner-friendly
    tone: str | None = Field(
        default=None,
        description="Văn phong của bài viết",
    )

    # Raw input gốc của user (giữ lại để trace/debug)
    raw_input: str | None = Field(
        default=None,
        description="Câu input gốc mà user đã nhập",
    )