"""
Schema cho việc tìm kiếm và gắn ảnh vào bài viết.

Worker không trực tiếp nhúng image vào article.
Worker chỉ đề xuất: image_queries

Sau đó Image layer / Image subgraph sẽ:
    query → Wikimedia (MCP) → ImageCandidate → ImageSpec

Cách này giúp tách:
    Content generation  và  Image retrieval
khỏi nhau.
"""

from pydantic import BaseModel, Field


class ImageCandidate(BaseModel):
    """Một ảnh candidate tìm được từ Wikimedia."""

    # Tên / title của ảnh
    title: str = Field(
        ...,
        description="Tên/title của ảnh trên Wikimedia",
    )

    # URL trực tiếp tới ảnh
    url: str = Field(
        ...,
        description="URL trực tiếp tới file ảnh",
    )

    # URL trang nguồn của ảnh (quan trọng cho attribution)
    source_url: str = Field(
        ...,
        description="URL trang gốc chứa ảnh trên Wikimedia Commons",
    )

    # License của ảnh nếu lấy được
    license: str | None = Field(
        default=None,
        description="Loại license của ảnh (CC-BY, Public Domain...)",
    )

    # Tác giả nếu Wikimedia cung cấp
    author: str | None = Field(
        default=None,
        description="Tác giả/nguồn gốc ảnh nếu có",
    )

    # Kích thước ảnh (width x height), hữu ích để chọn ảnh phù hợp
    width: int | None = Field(default=None, description="Chiều rộng ảnh (px)")
    height: int | None = Field(default=None, description="Chiều cao ảnh (px)")


class ImageSpec(BaseModel):
    """Yêu cầu tìm ảnh cho một task cụ thể + kết quả candidates."""

    # Task nào yêu cầu ảnh này
    task_id: str = Field(
        ...,
        description="ID của task yêu cầu ảnh này",
    )

    # Query tìm ảnh
    # Ví dụ: "Model Context Protocol architecture"
    query: str = Field(
        ...,
        description="Câu query dùng để tìm ảnh trên Wikimedia",
    )

    # Alt text cho Markdown (SEO + accessibility)
    alt_text: str = Field(
        ...,
        description="Alt text mô tả ảnh, dùng trong markdown",
    )

    # Các candidate tìm được từ Wikimedia
    candidates: list[ImageCandidate] = Field(
        default_factory=list,
        description="Danh sách ảnh candidate tìm được",
    )

    # Candidate được chọn cuối cùng (do Synthesizer hoặc logic tự động chọn)
    selected: ImageCandidate | None = Field(
        default=None,
        description="Ảnh candidate được chọn để nhúng vào bài viết",
    )

    # Đánh dấu kết quả này lấy từ cache hay gọi API mới
    from_cache: bool = Field(
        default=False,
        description="True nếu kết quả này được lấy từ cache",
    )