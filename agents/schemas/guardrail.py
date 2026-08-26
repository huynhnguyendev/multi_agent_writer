"""
Schema cho kết quả kiểm tra của node Input Guardrail.

Node: Input Guardrail
Model: Groq Llama Guard 2 (86m)

Nhiệm vụ:
    - Kiểm tra input có hợp lệ không.
    - Phát hiện prompt injection / malicious input.
    - Kiểm tra yêu cầu có phù hợp với hệ thống hay không.

Guardrail KHÔNG cần trả về nội dung bài viết.
Nó chỉ cần trả lời: valid / invalid + lý do nếu invalid.

Ví dụ:
    {
        "is_valid": false,
        "reason": "Prompt contains malicious instructions."
    }
"""

from typing import Literal

from pydantic import BaseModel, Field

# Các category vi phạm mà Guardrail có thể phát hiện.
# Dùng Literal để giới hạn giá trị hợp lệ, tránh model trả về
# một string tùy ý không kiểm soát được.
GuardrailCategory = Literal[
    "prompt_injection",
    "unsafe_content",
    "off_topic",
    "invalid_format",
    "other",
]


class GuardrailResult(BaseModel):
    """Kết quả kiểm tra input từ node Input Guardrail."""

    # True  → cho phép workflow tiếp tục
    # False → block request
    is_valid: bool = Field(
        ...,
        description="True nếu input hợp lệ, False nếu bị chặn",
    )

    # Category vi phạm (nếu có).
    # None nếu input hợp lệ.
    category: GuardrailCategory | None = Field(
        default=None,
        description="Loại vi phạm nếu input không hợp lệ",
    )

    # Lý do block.
    # Nếu input hợp lệ thì có thể để None.
    reason: str | None = Field(
        default=None,
        description="Lý do cụ thể tại sao input bị chặn",
    )

    # Điểm tin cậy của model khi đưa ra quyết định (0-1).
    # Hữu ích để debug / theo dõi threshold trên LangSmith.
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Độ tin cậy của quyết định (0-1)",
    )