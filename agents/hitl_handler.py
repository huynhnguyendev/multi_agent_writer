"""
Node 4: HITL (Human-in-the-Loop).

Node này KHÔNG gọi LLM và KHÔNG tự chờ input trực tiếp (khác bản cũ
dùng input() trên terminal - cách đó không hoạt động được khi chạy
qua web server, vì không có ai gõ vào terminal của backend cả).

Thay vào đó, dùng cơ chế `interrupt()` built-in của LangGraph:

    1. Node gọi interrupt({"plan": ...}) -> graph DỪNG HẲN LẠI tại đây,
       payload được trả ra ngoài cho code đang gọi graph.ainvoke().
    2. backend/services/workflow_manager.py (chạy graph ở background)
       nhận được payload này, lưu trạng thái "waiting_hitl" vào DB,
       trả về cho frontend qua GET /workflow/{id}/status.
    3. Frontend hiển thị Plan cho user xác nhận (approve/edit/reject),
       gọi POST /workflow/{id}/hitl.
    4. workflow_manager gọi lại:
           graph.ainvoke(Command(resume=payload), config=...)
       LangGraph tự resume đúng tại vị trí đã dừng, và giá trị
       `payload` đó chính là RETURN VALUE của lời gọi interrupt() ở
       bước 1 - node tiếp tục chạy tiếp với dữ liệu đó.

Nhờ cơ chế này, workflow có thể "tạm dừng" hàng giờ/hàng ngày (chờ
user) mà không tốn tài nguyên compute nào cả (checkpoint Postgres giữ
toàn bộ state), khác hẳn cách cũ (asyncio.wait_for chặn 1 process
sống suốt 60s).

3 lựa chọn của user (payload khi resume, dạng dict):

    {"action": "approved", "edited_plan": None, "feedback": None}
    {"action": "edited",   "edited_plan": {...Plan dict...}, "feedback": None}
    {"action": "rejected", "edited_plan": None, "feedback": "..."}
    {"action": "timeout",  "edited_plan": None, "feedback": None}
        -> do workflow_manager tự gửi khi hết 60s không ai phản hồi
"""

from langgraph.types import interrupt

from agents.schemas.hitl import HITLDecision
from agents.schemas.plan import Plan

# Type alias cho payload gửi vào interrupt() / nhận về khi resume,
# để nơi khác (workflow_manager.py) biết đúng format cần tuân theo.
HITL_INTERRUPT_TYPE = "hitl_plan_approval"


def request_plan_approval(plan: Plan) -> tuple[HITLDecision, Plan]:
    """
    Dừng graph tại đây, đợi resume với quyết định của user.

    Returns:
        (HITLDecision, Plan) - Plan trả về là bản CUỐI CÙNG sẽ dùng
        cho các bước tiếp theo:
            - approved/timeout: giữ nguyên plan gốc
            - edited: plan đã được user sửa (parse lại từ edited_plan dict)
            - rejected: vẫn trả về plan gốc (không dùng), vì graph sẽ
              quay lại Planner với feedback để tạo plan HOÀN TOÀN MỚI

    Raises:
        ValidationError (từ Pydantic): nếu edited_plan gửi lên không
        hợp lệ (ví dụ vượt quá 7 task, cycle dependency...) - lỗi này
        được validate NGAY tại code (không tin tưởng payload từ FE),
        nên caller (graph.py) cần chuẩn bị xử lý nếu cần.
    """
    payload: dict = interrupt(
        {
            "type": HITL_INTERRUPT_TYPE,
            "plan": plan.model_dump(),
        }
    )

    action = payload.get("action", "approved")
    edited_plan_data = payload.get("edited_plan")
    feedback = payload.get("feedback")

    approved = action in ("approved", "edited", "timeout")
    edited = action == "edited" and edited_plan_data is not None

    decision = HITLDecision(
        action=action,
        approved=approved,
        edited=edited,
        feedback=feedback,
    )

    final_plan = Plan(**edited_plan_data) if edited else plan

    return decision, final_plan


# ============================================================
# DEBUG - Test cơ chế interrupt/resume ĐỘC LẬP (không chạy full
# pipeline Guardrail->...->Executor, chỉ dựng 1 graph nhỏ 2 node để
# kiểm tra riêng cơ chế dừng/resume có hoạt động đúng không).
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.hitl_handler
# ============================================================

# if __name__ == "__main__":
#     import sys

#     if sys.platform == "win32":
#         import asyncio
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#     import asyncio
#     from typing import TypedDict

#     from langgraph.checkpoint.memory import InMemorySaver
#     from langgraph.graph import END, START, StateGraph
#     from langgraph.types import Command

#     from agents.schemas.plan import Task

#     class _DebugState(TypedDict):
#         plan: Plan
#         hitl_decision: HITLDecision | None
#         final_plan: Plan | None

#     def _hitl_test_node(state: _DebugState) -> dict:
#         decision, final_plan = request_plan_approval(state["plan"])
#         return {"hitl_decision": decision, "final_plan": final_plan}

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test cơ chế interrupt/resume của HITL")
#         print("=" * 60)

#         sample_plan = Plan(
#             title="MCP cho AI Engineer",
#             objective="Test interrupt/resume",
#             target_audience="AI Engineer",
#             tone="technical",
#             estimated_sections=1,
#             tasks=[
#                 Task(
#                     id="task_01",
#                     title="Giới thiệu",
#                     description="Giới thiệu tổng quan về MCP.",
#                     objective="Giải thích MCP là gì.",
#                     expected_output="Phần giới thiệu MCP.",
#                     depends_on=[],
#                     order=0,
#                 ),
#                 Task(
#                     id="task_02",
#                     title="Analyze MCP",
#                     description="Phân tích kiến trúc và cách MCP hoạt động.",
#                     objective="Giúp người đọc hiểu cơ chế hoạt động của MCP.",
#                     expected_output="Phần phân tích kiến trúc MCP.",
#                     depends_on=["task_01"],
#                     order=1,
#                 ),
#                 Task(
#                     id="task_03",
#                     title="Write article",
#                     description="Tổng hợp nội dung thành bài viết hoàn chỉnh.",
#                     objective="Tạo nội dung có cấu trúc về MCP cho AI Engineer.",
#                     expected_output="Phần kết luận và nội dung bài viết.",
#                     depends_on=["task_02"],
#                     order=2,
#                 ),
#             ],
#         )

#         builder = StateGraph(_DebugState)
#         builder.add_node("hitl", _hitl_test_node)
#         builder.add_edge(START, "hitl")
#         builder.add_edge("hitl", END)

#         checkpointer = InMemorySaver()
#         graph = builder.compile(checkpointer=checkpointer)

#         config = {"configurable": {"thread_id": "debug-hitl-thread-001"}}

#         # --- Bước 1: chạy graph lần đầu -> phải DỪNG LẠI ở interrupt ---
#         print("\n### Bước 1: Chạy graph lần đầu (kỳ vọng dừng tại interrupt) ###")
#         result = await graph.ainvoke({"plan": sample_plan, "hitl_decision": None, "final_plan": None}, config=config)

#         assert "__interrupt__" in result, "❌ Graph phải dừng tại interrupt, nhưng chạy thẳng tới cuối!"
#         interrupt_payload = result["__interrupt__"][0].value
#         print(f"✅ Graph đã dừng đúng tại interrupt.")
#         print(f"   Payload nhận được: type={interrupt_payload['type']}, plan_title={interrupt_payload['plan']['title']}")

#         # --- Bước 2: giả lập user APPROVE -> resume ---
#         print("\n### Bước 2: Resume với action='approved' ###")
#         result = await graph.ainvoke(
#             Command(resume={"action": "approved", "edited_plan": None, "feedback": None}),
#             config=config,
#         )
#         assert "__interrupt__" not in result, "❌ Graph không được dừng lại nữa sau khi resume!"
#         assert result["hitl_decision"].approved is True
#         assert result["hitl_decision"].action == "approved"
#         print(f"✅ Resume thành công: hitl_decision={result['hitl_decision']}")

#         # --- Bước 3: chạy lại từ đầu với thread_id KHÁC, test case EDIT ---
#         print("\n### Bước 3: Test case EDIT (dùng thread_id mới) ###")
#         config_2 = {"configurable": {"thread_id": "debug-hitl-thread-002"}}
#         await graph.ainvoke({"plan": sample_plan, "hitl_decision": None, "final_plan": None}, config=config_2)

#         edited_plan_dict = sample_plan.model_dump()
#         edited_plan_dict["title"] = "MCP cho AI Engineer (đã chỉnh sửa)"

#         result = await graph.ainvoke(
#             Command(resume={"action": "edited", "edited_plan": edited_plan_dict, "feedback": None}),
#             config=config_2,
#         )
#         assert result["hitl_decision"].edited is True
#         assert result["final_plan"].title == "MCP cho AI Engineer (đã chỉnh sửa)"
#         print(f"✅ Edit thành công: final_plan.title = '{result['final_plan'].title}'")

#         # --- Bước 4: test case REJECT ---
#         print("\n### Bước 4: Test case REJECT (dùng thread_id mới) ###")
#         config_3 = {"configurable": {"thread_id": "debug-hitl-thread-003"}}
#         await graph.ainvoke({"plan": sample_plan, "hitl_decision": None, "final_plan": None}, config=config_3)

#         result = await graph.ainvoke(
#             Command(resume={"action": "rejected", "edited_plan": None, "feedback": "Thêm phần bảo mật"}),
#             config=config_3,
#         )
#         assert result["hitl_decision"].approved is False
#         assert result["hitl_decision"].feedback == "Thêm phần bảo mật"
#         print(f"✅ Reject thành công: feedback='{result['hitl_decision'].feedback}'")

#         print("\n✅ Tất cả test pass! Cơ chế interrupt/resume hoạt động đúng.")

#     asyncio.run(_debug())