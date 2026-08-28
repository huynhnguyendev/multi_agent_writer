"""
Schema cho kết quả đánh giá của node Evaluator.

Evaluator không chỉ chấm một điểm duy nhất, mà chia thành
nhiều tiêu chí:

    Factuality              (Tính xác thực)
    Completeness            (Mức độ đầy đủ)
    Coherence               (Tính logic/mạch lạc)
    Writing Quality         (Chất lượng văn phong)
    Visual Support          (Chất lượng ảnh)
    Instruction Following   (Tuân thủ yêu cầu ban đầu)

Sau đó mới tính ra overall_score.

Ví dụ:
    factuality              = 9.2
    completeness            = 8.7
    coherence               = 9.4
    writing_quality         = 9.1
    Visual Support          = 8.1
    instruction_following   = 9.5

    overall_score           = 9.2
    accepted                = True

Quy tắc chấp nhận:

    overall_score >= 8.0
        → accepted = True
        → kết thúc workflow

    overall_score < 8.0
        → accepted = False
        → quay lại Synthesizer
        → tối đa 5 lần revision
"""

from pydantic import BaseModel, Field, model_validator

# Ngưỡng điểm để bài viết được chấp nhận (theo yêu cầu của bạn).
ACCEPTANCE_THRESHOLD = 8.0

# Số lần revision tối đa trước khi buộc chấp nhận bài viết
# dù điểm thấp hơn ngưỡng (theo yêu cầu của bạn).
MAX_REVISIONS = 5


class Evaluation(BaseModel):
    """Kết quả đánh giá chất lượng của FinalArticle."""

    # Điểm tổng thể
    overall_score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Điểm tổng thể (trung bình các tiêu chí)",
    )

    # Độ chính xác thông tin
    factuality: float = Field(
        ...,
        ge=0,
        le=10,
        description="Điểm tính xác thực của thông tin trong bài viết",
    )

    # Mức độ đầy đủ
    completeness: float = Field(
        ...,
        ge=0,
        le=10,
        description="Điểm mức độ đầy đủ so với plan ban đầu",
    )

    # Tính logic / mạch lạc
    coherence: float = Field(
        ...,
        ge=0,
        le=10,
        description="Điểm tính logic và mạch lạc của bài viết",
    )

    # Chất lượng văn phong
    writing_quality: float = Field(
        ...,
        ge=0,
        le=10,
        description="Điểm chất lượng văn phong",
    )

    # Mức độ hỗ trợ trực quan bằng hình ảnh: bài viết có ảnh minh họa
    # phù hợp, đúng chỗ cần thiết không? Nếu bài hoàn toàn không có
    # ảnh nào dù nội dung có các khái niệm cần minh họa trực quan
    # (kiến trúc, sơ đồ, quy trình...), điểm này phải thấp.
    visual_support: float = Field(
        ...,
        ge=0,
        le=10,
        description="Điểm mức độ hỗ trợ trực quan bằng hình ảnh minh họa",
    )

    # Có làm đúng yêu cầu ban đầu không?
    instruction_following: float = Field(
        ...,
        ge=0,
        le=10,
        description="Điểm mức độ tuân thủ yêu cầu ban đầu của user",
    )

    # Feedback để Synthesizer biết cần sửa gì.
    # Ví dụ:
    #   ["Section 2 quá dài dòng.", "Bổ sung dẫn chứng cho claim về MCP security."]
    feedback: list[str] = Field(
        default_factory=list,
        description="Danh sách feedback cụ thể để cải thiện bài viết",
    )

    # Model evaluator đưa ra kết luận sơ bộ.
    # Tuy nhiên graph vẫn nên kiểm tra lại overall_score bằng code
    # (không tin tưởng hoàn toàn vào field này do LLM có thể tính sai).
    accepted: bool = Field(
        ...,
        description="Kết luận của Evaluator: bài viết có được chấp nhận không",
    )

    @model_validator(mode="after")
    def enforce_threshold_by_code(self) -> "Evaluation":
        """
        Không tin tưởng hoàn toàn LLM khi tự set `accepted`.
        Luôn tính lại bằng code dựa trên ACCEPTANCE_THRESHOLD,
        để đảm bảo logic routing trong graph luôn nhất quán.
        """
        self.accepted = self.overall_score >= ACCEPTANCE_THRESHOLD
        return self