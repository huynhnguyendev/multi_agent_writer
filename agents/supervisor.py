"""
Node 2: Supervisor.

Nhiệm vụ: phân tích UserRequest, quyết định chiến lược research
(closed_book / open_book / hybrid) và chuẩn hóa lại ngôn ngữ nếu cần.

Dùng BaseAgent pattern (render prompt YAML -> gọi LLM -> parse JSON
-> validate bằng SupervisorDecision schema) vì output của node này
đã đúng chuẩn JSON khớp với schema.
"""

from agents.base_agent import BaseAgent, LLMOutputError
from agents.schemas.supervisor import SupervisorDecision
from agents.schemas.user_request import UserRequest


class SupervisorAgent(BaseAgent):
    """Agent quyết định chiến lược research cho toàn bộ workflow."""

    def __init__(self):
        super().__init__(
            prompt_name="supervisor",
            model_role="supervisor",
            output_schema=SupervisorDecision,
        )


_agent = SupervisorAgent()


async def run_supervisor(user_request: UserRequest) -> SupervisorDecision:
    """
    Entry point chính của node Supervisor.

    Theo chiến lược "bỏ qua và log lỗi": nếu LLM trả output không
    parse/validate được sau khi retry, KHÔNG làm sập graph mà fallback
    về mode "hybrid" (an toàn nhất - vừa dùng kiến thức LLM vừa có thể
    research nếu Worker thấy cần), đồng thời log lỗi rõ ràng.
    """
    try:
        return await _agent.run(
            topic=user_request.topic,
            article_type=user_request.article_type,
            target_audience=user_request.target_audience or "độc giả phổ thông",
            tone=user_request.tone or "professional",
            language=user_request.language,
            raw_input=user_request.raw_input or user_request.topic,
        )
    except LLMOutputError as e:
        print(f"⚠️  [supervisor] Lỗi khi tạo SupervisorDecision: {e}")
        return SupervisorDecision(
            mode="hybrid",
            reasoning=(
                "Fallback do lỗi hệ thống khi gọi LLM. "
                "Mặc định chọn hybrid để đảm bảo an toàn (vừa dùng kiến "
                "thức sẵn có, vừa cho phép Worker research nếu cần)."
            ),
            research_queries=[],
            language=user_request.language,
        )


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Supervisor
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.supervisor
# ============================================================

if __name__ == "__main__":
    import asyncio

    TEST_CASES = [
        (
            UserRequest(
                topic="Transformer là gì",
                article_type="tutorial",
                target_audience="sinh viên CNTT",
                tone="beginner-friendly",
                language="vi",
                raw_input="Giải thích Transformer là gì cho người mới bắt đầu.",
            ),
            "kỳ vọng closed_book (kiến thức nền tảng)",
        ),
        (
            UserRequest(
                topic="Tình hình MCP mới nhất năm 2026",
                article_type="news",
                target_audience="AI Engineer",
                tone="technical",
                language="vi",
                raw_input="Viết bài về tình hình MCP mới nhất năm 2026.",
            ),
            "kỳ vọng open_book (cần thông tin cập nhật)",
        ),
        (
            UserRequest(
                topic="MCP và các thay đổi mới nhất so với kiến trúc cũ",
                article_type="blog",
                target_audience="AI Engineer",
                tone="technical",
                language="vi",
                raw_input="Giải thích MCP là gì và phân tích những thay đổi mới nhất.",
            ),
            "kỳ vọng hybrid (nền tảng + cập nhật)",
        ),
    ]

    async def _debug():
        print("=" * 60)
        print("DEBUG: Test Supervisor")
        print("=" * 60)

        for user_request, label in TEST_CASES:
            print(f"\n--- Test case: {label} ---")
            print(f"Topic: {user_request.topic}")

            decision = await run_supervisor(user_request)

            print(f"Mode       : {decision.mode}")
            print(f"Reasoning  : {decision.reasoning}")
            print(f"Language   : {decision.language}")
            print(f"Queries    : {decision.research_queries}")

    asyncio.run(_debug())