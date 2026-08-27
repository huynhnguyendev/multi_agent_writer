"""
State chính của toàn bộ LangGraph workflow.

Có thể xem nó như "bộ nhớ workflow" — mỗi node sẽ đọc một phần
State và update một phần State.

Luồng đi qua các node:

    Input Guardrail   → update guardrail
    Supervisor        → update supervisor
    Planner           → update plan
    HITL              → update hitl, approved_plan
    Executor (fan-out)→ update worker_outputs
    Image Resolver    → update image_specs
    Synthesizer       → update final_article
    Evaluator         → update evaluation, revision_count
"""

import operator
from typing import Annotated, TypedDict

from agents.schemas.evaluation import Evaluation
from agents.schemas.guardrail import GuardrailResult
from agents.schemas.hitl import HITLDecision
from agents.schemas.image import ImageSpec
from agents.schemas.article import FinalArticle
from agents.schemas.plan import Plan
from agents.schemas.supervisor import SupervisorDecision
from agents.schemas.user_request import UserRequest
from agents.schemas.worker import WorkerOutput


class WriterState(TypedDict):
    """State chính (main state) của toàn bộ LangGraph workflow."""

    # ========================================================
    # WORKFLOW METADATA
    # ========================================================
    #
    # ID định danh cho một lần chạy workflow.
    # Dùng để:
    #   - Lưu checkpoint vào PostgreSQL (khóa chính).
    #   - Resume lại workflow khi bị lỗi/gián đoạn.
    #   - Trace trên LangSmith.
    # ========================================================

    workflow_id: str

    # ========================================================
    # INPUT
    # ========================================================
    #
    # Dữ liệu user nhập vào. Đây là context gốc của toàn workflow.
    # ========================================================

    user_request: UserRequest

    # ========================================================
    # INPUT GUARDRAIL
    # ========================================================
    #
    # Kết quả kiểm tra input.
    # Nếu is_valid = False → Graph sẽ đi tới Blocked / END.
    # ========================================================

    guardrail: GuardrailResult | None

    # ========================================================
    # SUPERVISOR
    # ========================================================
    #
    # Supervisor quyết định: closed_book / open_book / hybrid
    # và có thể tạo research queries.
    # ========================================================

    supervisor: SupervisorDecision | None

    # ========================================================
    # PLANNER
    # ========================================================
    #
    # plan:
    #     Plan do LLM tạo ra ban đầu (có thể được tạo lại nhiều lần
    #     nếu user reject ở bước HITL).
    #
    # approved_plan:
    #     Plan cuối cùng sau khi HITL approve/edit.
    #
    # Hai field này được giữ riêng để biết:
    #     Model đề xuất gì?  vs  User đã chỉnh gì?
    # ========================================================

    plan: Plan | None

    approved_plan: Plan | None

    # ========================================================
    # HITL
    # ========================================================
    #
    # Lưu quyết định của user (approved/edited/rejected/timeout).
    # ========================================================

    hitl: HITLDecision | None

    # Số lần Plan đã được tạo lại do user reject.
    # Có thể dùng để giới hạn số lần lặp lại (tránh loop vô hạn
    # nếu user liên tục reject).
    plan_revision_count: int

    # ========================================================
    # WORKER OUTPUTS
    # ========================================================
    #
    # Đây là phần ĐẶC BIỆT QUAN TRỌNG.
    #
    # Vì Worker chạy song song (hoặc theo batch nếu có dependency)
    # nên nhiều node có thể cùng ghi vào worker_outputs.
    #
    # operator.add có nghĩa:
    #     [Output 1] + [Output 2] + [Output 3]
    #     = [Output 1, Output 2, Output 3]
    #
    # Đây là reducer dành cho fan-out của LangGraph.
    # ========================================================

    worker_outputs: Annotated[
        list[WorkerOutput],
        operator.add,
    ]

    # ========================================================
    # IMAGE RESOLVER
    # ========================================================
    #
    # Danh sách ImageSpec đã resolve từ image_queries của các
    # WorkerOutput (chạy sau Executor, trước Synthesizer).
    #
    # KHÔNG dùng operator.add vì image_resolver chạy 1 LẦN DUY NHẤT
    # cho toàn bộ danh sách worker_outputs (không phải fan-out theo
    # từng task như worker_outputs), nên chỉ cần ghi đè bình thường.
    #
    # Khi Synthesizer bị gọi lại (revision), image_specs giữ nguyên
    # không cần resolve lại (ảnh không phụ thuộc vào việc viết lại
    # văn bản, trừ khi sau này muốn tối ưu thêm).
    # ========================================================

    image_specs: list[ImageSpec]

    # ========================================================
    # FINAL ARTICLE
    # ========================================================
    #
    # Synthesizer tạo ra bài viết cuối cùng.
    # Ban đầu: None
    # Sau Synthesizer: FinalArticle(...)
    # Nếu bị revise nhiều lần, field này sẽ được OVERWRITE
    # (không cộng dồn như worker_outputs).
    # ========================================================

    final_article: FinalArticle | None

    # ========================================================
    # EVALUATION
    # ========================================================
    #
    # Evaluator đánh giá FinalArticle.
    #
    # Nếu overall_score >= 9   → END
    # Nếu overall_score <  9   → Revision → quay lại Synthesizer
    # ========================================================

    evaluation: Evaluation | None

    # ========================================================
    # REVISION CONTROL
    # ========================================================
    #
    # Đếm số lần bài viết đã được Synthesizer sửa lại
    # (khác với plan_revision_count ở trên - đây là revision
    # của FinalArticle sau khi bị Evaluator từ chối).
    #
    # Giới hạn: MAX_REVISIONS = 5 (xem agents/schemas/evaluation.py)
    # để tránh vòng lặp: Synthesizer → Evaluator → Synthesizer → ...
    # chạy vô hạn.
    #
    # Nếu revision_count >= 5 mà vẫn chưa đạt điểm:
    #     → Vẫn xuất bài viết với điểm thấp nhất (theo yêu cầu của bạn).
    # ========================================================

    revision_count: int

    # ========================================================
    # ERROR TRACKING (theo chiến lược "bỏ qua và log lỗi")
    # ========================================================
    #
    # Danh sách các lỗi không nghiêm trọng đã xảy ra trong suốt
    # workflow (ví dụ: 1 worker bị lỗi nhưng vẫn tiếp tục chạy).
    #
    # Không làm sập graph, chỉ dùng để log/debug/hiển thị cho user
    # biết có phần nào bị bỏ qua.
    # ========================================================

    errors: Annotated[list[str], operator.add]

    # ========================================================
    # OUTPUT
    # ========================================================
    #
    # Nội dung Markdown cuối cùng, sẵn sàng để render lên UI
    # sau khi workflow hoàn tất (accepted=True hoặc hết max revision).
    # ========================================================

    output_markdown: str | None