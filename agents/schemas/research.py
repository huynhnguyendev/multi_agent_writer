"""
Schema dùng để chuẩn hóa dữ liệu trả về từ Tavily / MCP research tool.

KHÔNG nên đưa raw response của Tavily thẳng vào State.
Thay vào đó normalize thành schema riêng của project.

Điều này giúp sau này đổi:
    Tavily → MCP Search → Google Search
mà Worker không cần biết implementation bên dưới.
"""

from pydantic import BaseModel, Field


class ResearchSource(BaseModel):
    """Một nguồn thông tin tìm được từ research tool."""

    # Tiêu đề của nguồn
    title: str = Field(
        ...,
        description="Tiêu đề của trang/nguồn",
    )

    # URL nguồn
    url: str = Field(
        ...,
        description="URL của nguồn",
    )

    # Nội dung đã lấy được từ nguồn
    content: str = Field(
        ...,
        description="Nội dung / snippet lấy được từ nguồn",
    )

    # Điểm relevance nếu tool có trả về.
    # Không phải search engine nào cũng có (nên optional).
    score: float | None = Field(
        default=None,
        description="Điểm relevance do search engine trả về (nếu có)",
    )


class ResearchResult(BaseModel):
    """Kết quả research cho một query cụ thể."""

    # Query đã dùng để research
    query: str = Field(
        ...,
        description="Câu query đã dùng để tìm kiếm",
    )

    # Danh sách nguồn tìm được
    sources: list[ResearchSource] = Field(
        default_factory=list,
        description="Danh sách các nguồn tìm được cho query này",
    )

    # Provider đã dùng để research (tavily, mcp, google...).
    # Hữu ích khi cache/debug/đổi provider sau này.
    provider: str = Field(
        default="tavily",
        description="Provider đã dùng để lấy kết quả research",
    )

    # Đánh dấu kết quả này lấy từ cache hay gọi API mới.
    from_cache: bool = Field(
        default=False,
        description="True nếu kết quả này được lấy từ cache",
    )