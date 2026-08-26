"""
Node 3: Planner.

Nhiệm vụ: biến UserRequest + SupervisorDecision thành 1 bản Plan chi
tiết (3-7 task, có thể có dependency giữa các task).

Khác với Supervisor, Planner KHÔNG có fallback hợp lý khi thất bại
(không thể "đoán đại" ra 1 Plan giả) - nếu LLM liên tục trả sai
format/sai logic (depends_on cycle, task_id không tồn tại...) sau khi
đã retry ở BaseAgent, node này sẽ raise lỗi để tầng gọi nó (graph.py
sau này, hoặc code test hiện tại) tự quyết định: thử gọi lại node,
hay dừng workflow và báo lỗi cho user.

Node này còn được dùng lại khi user REJECT plan ở bước HITL (truyền
thêm feedback để Planner tạo lại plan tốt hơn).
"""

from agents.base_agent import BaseAgent, LLMOutputError
from agents.schemas.plan import Plan
from agents.schemas.supervisor import SupervisorDecision
from agents.schemas.user_request import UserRequest


class PlannerAgent(BaseAgent):
    """Agent tạo bản kế hoạch (Plan) chi tiết cho bài viết."""

    def __init__(self):
        super().__init__(
            prompt_name="planner",
            model_role="planner",
            output_schema=Plan,
            # Planner dễ bị sai logic (depends_on cycle, task_id sai) hơn
            # các node khác vì output phức tạp -> cho retry nhiều hơn 1 lần.
            max_json_retries=2,
        )


_agent = PlannerAgent()


async def run_planner(
    user_request: UserRequest,
    supervisor: SupervisorDecision,
    feedback: str | None = None,
) -> Plan:
    """
    Entry point chính của node Planner.

    Args:
        user_request: Yêu cầu gốc của user.
        supervisor: Quyết định của Supervisor (mode, reasoning).
        feedback: Feedback của user khi reject plan ở bước HITL trước đó
            (None nếu đây là lần tạo plan đầu tiên).

    Raises:
        LLMOutputError: nếu LLM không tạo ra được Plan hợp lệ sau khi
            đã retry (bao gồm cả lỗi validate: cycle, task_id không tồn tại,
            sai số lượng task...).
    """
    return await _agent.run(
        topic=user_request.topic,
        article_type=user_request.article_type,
        target_audience=user_request.target_audience or "độc giả phổ thông",
        tone=user_request.tone or "professional",
        language=user_request.language,
        research_mode=supervisor.mode,
        research_reasoning=supervisor.reasoning,
        feedback=feedback,
    )


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Planner
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.planner
# ============================================================

# if __name__ == "__main__":
#     import asyncio

#     def _print_plan(plan: Plan) -> None:
#         print(f"\nTitle       : {plan.title}")
#         print(f"Objective   : {plan.objective}")
#         print(f"Audience    : {plan.target_audience}")
#         print(f"Tone        : {plan.tone}")
#         print(f"Est.sections: {plan.estimated_sections}")
#         print(f"Số tasks    : {len(plan.tasks)}")
#         print("-" * 60)

#         for task in plan.tasks:
#             deps = task.depends_on if task.depends_on else "(không phụ thuộc)"
#             print(f"[{task.id}] (order={task.order}) {task.title}")
#             print(f"    Depends on       : {deps}")
#             print(f"    Requires research: {task.requires_research}")
#             if task.research_queries:
#                 print(f"    Research queries : {task.research_queries}")
#             print(f"    Expected output  : {task.expected_output}")
#             print()

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test Planner")
#         print("=" * 60)

#         user_request = UserRequest(
#             topic="MCP (Model Context Protocol) cho AI Engineer",
#             article_type="blog",
#             target_audience="AI Engineer",
#             tone="technical",
#             language="vi",
#             raw_input="Viết một bài blog bằng tiếng Việt về MCP cho AI Engineer, có so sánh với cách tích hợp tool truyền thống.",
#         )

#         supervisor_decision = SupervisorDecision(
#             mode="hybrid",
#             reasoning="Cần kiến thức nền tảng về MCP + thông tin cập nhật để so sánh.",
#             research_queries=["Model Context Protocol architecture", "MCP vs traditional tool calling"],
#             language="vi",
#         )

#         # --- Test 1: Tạo plan lần đầu ---
#         print("\n### TEST 1: Tạo Plan lần đầu (chưa có feedback) ###")
#         try:
#             plan = await run_planner(user_request, supervisor_decision)
#             _print_plan(plan)
#         except LLMOutputError as e:
#             print(f"❌ Planner thất bại: {e}")
#             plan = None

#         # --- Test 2: Giả lập user reject ở HITL, yêu cầu tạo lại plan ---
#         print("\n### TEST 2: Tạo lại Plan sau khi user reject (có feedback) ###")
#         try:
#             revised_plan = await run_planner(
#                 user_request,
#                 supervisor_decision,
#                 feedback="Thêm một task riêng về bảo mật (security) khi dùng MCP, và bỏ bớt phần lịch sử phát triển.",
#             )
#             _print_plan(revised_plan)
#         except LLMOutputError as e:
#             print(f"❌ Planner thất bại: {e}")

#     asyncio.run(_debug())