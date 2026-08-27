"""
Node 4: HITL (Human-in-the-Loop).

Node này KHÔNG gọi LLM - chỉ xử lý logic chờ phản hồi từ user.

Ở giai đoạn hiện tại (chưa có backend/ với WebSocket), mình mô phỏng
việc chờ user bằng input() trên terminal, có timeout 60s (theo đúng
yêu cầu: hết 60s không phản hồi -> tự động approve và chạy tiếp).

Khi làm tới backend/ (WebSocket), hàm `wait_for_hitl_decision` này sẽ
được thay thế bằng phiên bản chờ message từ client qua WebSocket,
nhưng chữ ký hàm (nhận Plan, trả về HITLDecision + Plan cuối cùng)
sẽ được giữ nguyên để graph.py không cần sửa gì khi chuyển đổi.

3 lựa chọn của user:
    [A]pprove -> tiếp tục workflow với plan hiện tại
    [E]dit    -> cho user paste lại JSON plan đã sửa, validate lại
    [R]eject  -> quay lại Planner, kèm feedback để tạo plan mới
    (không phản hồi trong 60s -> tự động approve)
"""

import asyncio
import json
import time

from pydantic import ValidationError

from agents.schemas.hitl import HITLDecision
from agents.schemas.plan import Plan

HITL_TIMEOUT_SECONDS = 60


def _print_plan_summary(plan: Plan) -> None:
    """In tóm tắt Plan ra terminal để user xem trước khi quyết định."""
    print("\n" + "=" * 60)
    print("📋 PLAN CẦN XÁC NHẬN")
    print("=" * 60)
    print(f"Title       : {plan.title}")
    print(f"Objective   : {plan.objective}")
    print(f"Audience    : {plan.target_audience}")
    print(f"Tone        : {plan.tone}")
    print(f"Số tasks    : {len(plan.tasks)}")
    print("-" * 60)

    for task in plan.tasks:
        deps = ", ".join(task.depends_on) if task.depends_on else "—"
        print(f"[{task.id}] {task.title}  (depends_on: {deps})")

    print("=" * 60)


async def _prompt_choice() -> str:
    """
    Hỏi user chọn A/E/R, lặp lại nếu input không hợp lệ.
    Chạy input() trong thread riêng (asyncio.to_thread) vì input() là
    hàm blocking, không thể chạy trực tiếp trong event loop async.
    """
    while True:
        raw = await asyncio.to_thread(
            input, "\n👉 Chọn hành động - [A]pprove / [E]dit / [R]eject: "
        )
        choice = raw.strip().lower()
        if choice in ("a", "e", "r"):
            return choice
        print("⚠️  Lựa chọn không hợp lệ, vui lòng nhập A, E, hoặc R.")


async def _edit_plan_flow(plan: Plan) -> Plan:
    """
    Cho user paste lại toàn bộ JSON của Plan để chỉnh sửa thủ công.

    Flow:
        1. In ra JSON hiện tại của plan.
        2. User paste JSON mới (kết thúc bằng dòng chỉ chứa "END").
           Nếu để trống (chỉ gõ "END" ngay) -> giữ nguyên plan cũ.
        3. Validate lại bằng Plan schema (bao gồm cả cycle detection).
           Nếu lỗi -> báo lỗi, cho user thử lại hoặc hủy edit (giữ plan cũ).
    """
    print("\n" + "-" * 60)
    print("✏️  CHỈNH SỬA PLAN")
    print("-" * 60)
    print("Plan hiện tại (JSON):\n")
    print(plan.model_dump_json(indent=2))
    print("-" * 60)
    print(
        "Paste JSON plan đã chỉnh sửa bên dưới, kết thúc bằng dòng "
        "chỉ chứa 'END'.\n(Để trống rồi gõ 'END' ngay = giữ nguyên plan cũ)\n"
    )

    while True:
        lines: list[str] = []
        while True:
            line = await asyncio.to_thread(input)
            if line.strip() == "END":
                break
            lines.append(line)

        raw_json = "\n".join(lines).strip()

        if not raw_json:
            print("↩️  Không có thay đổi, giữ nguyên plan cũ.")
            return plan

        try:
            data = json.loads(raw_json)
            edited_plan = Plan(**data)
            print("✅ Plan mới hợp lệ!")
            return edited_plan
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"❌ Plan không hợp lệ: {e}")
            retry = await asyncio.to_thread(
                input, "Thử paste lại? (y = thử lại / n = hủy, giữ plan cũ): "
            )
            if retry.strip().lower() != "y":
                print("↩️  Hủy chỉnh sửa, giữ nguyên plan cũ.")
                return plan
            print("\nPaste lại JSON, kết thúc bằng dòng 'END':\n")


async def wait_for_hitl_decision(
    plan: Plan,
    timeout_seconds: int = HITL_TIMEOUT_SECONDS,
) -> tuple[HITLDecision, Plan]:
    """
    Entry point chính của node HITL.

    Returns:
        (HITLDecision, Plan) - Plan trả về là bản cuối cùng sẽ dùng
        cho các bước tiếp theo:
            - approved/timeout: giữ nguyên plan gốc
            - edited: plan đã được user sửa
            - rejected: vẫn trả về plan gốc (không dùng), vì graph sẽ
              gọi lại Planner với feedback để tạo plan HOÀN TOÀN MỚI
    """
    _print_plan_summary(plan)
    print(f"\n⏳ Bạn có {timeout_seconds}s để phản hồi (hết giờ = tự động approve)...")

    start = time.monotonic()

    try:
        choice = await asyncio.wait_for(_prompt_choice(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        print("\n⏰ Hết thời gian chờ - tự động APPROVE và tiếp tục workflow.")
        return (
            HITLDecision(
                action="timeout",
                approved=True,
                edited=False,
                feedback=None,
                response_time_seconds=None,
            ),
            plan,
        )

    elapsed = round(time.monotonic() - start, 2)

    if choice == "a":
        print("✅ Đã APPROVE plan.")
        decision = HITLDecision(
            action="approved",
            approved=True,
            edited=False,
            response_time_seconds=elapsed,
        )
        return decision, plan

    if choice == "e":
        edited_plan = await _edit_plan_flow(plan)
        was_edited = edited_plan.model_dump() != plan.model_dump()
        print("✅ Đã xác nhận plan (có chỉnh sửa)." if was_edited else "✅ Đã APPROVE plan (không đổi gì).")
        decision = HITLDecision(
            action="edited" if was_edited else "approved",
            approved=True,
            edited=was_edited,
            response_time_seconds=elapsed,
        )
        return decision, edited_plan

    # choice == "r"
    feedback = await asyncio.to_thread(
        input, "📝 Nhập feedback để Planner cải thiện plan: "
    )
    print("🔁 Đã REJECT plan, sẽ quay lại Planner với feedback trên.")
    decision = HITLDecision(
        action="rejected",
        approved=False,
        edited=False,
        feedback=feedback.strip() or None,
        response_time_seconds=elapsed,
    )
    return decision, plan


# ============================================================
# DEBUG - Chạy trực tiếp file này để test HITL
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.hitl_handler
#
# Gợi ý test:
#   - Thử chọn "a" -> xem action="approved"
#   - Thử chọn "r" -> nhập feedback -> xem action="rejected"
#   - Thử chọn "e" -> để trống rồi "END" -> xem giữ nguyên plan
#   - Thử chọn "e" -> paste JSON đã sửa 1 field -> xem action="edited"
#   - Không gõ gì, đợi hết 60s (hoặc sửa timeout_seconds=10 để test nhanh)
# ============================================================

# if __name__ == "__main__":
#     from agents.schemas.plan import Task

#     async def _debug():
#         sample_plan = Plan(
#             title="MCP cho AI Engineer",
#             objective="Giải thích MCP và ứng dụng thực tế",
#             target_audience="AI Engineer",
#             tone="technical",
#             estimated_sections=3,
#             tasks=[
#                 Task(
#                     id="task_01",
#                     title="Giới thiệu MCP",
#                     description="Giải thích MCP là gì",
#                     objective="Người đọc hiểu khái niệm cơ bản",
#                     expected_output="~300 từ",
#                 ),
#                 Task(
#                     id="task_02",
#                     title="Kiến trúc MCP",
#                     description="Giải thích client/server/host",
#                     objective="Người đọc hiểu kiến trúc",
#                     expected_output="~400 từ",
#                     depends_on=["task_01"],
#                 ),
#                 Task(
#                     id="task_03",
#                     title="Kết luận",
#                     description="Tổng kết bài viết",
#                     objective="Chốt lại ý chính",
#                     expected_output="~150 từ",
#                     depends_on=["task_02"],
#                 ),
#             ],
#         )

#         print("=" * 60)
#         print("DEBUG: Test HITL Handler")
#         print("=" * 60)
#         print("💡 Tip: sửa timeout_seconds=10 trong code nếu muốn test nhanh case timeout.")

#         decision, final_plan = await wait_for_hitl_decision(sample_plan, timeout_seconds=60)

#         print("\n" + "=" * 60)
#         print("KẾT QUẢ HITL")
#         print("=" * 60)
#         print(f"Action              : {decision.action}")
#         print(f"Approved            : {decision.approved}")
#         print(f"Edited              : {decision.edited}")
#         print(f"Feedback            : {decision.feedback}")
#         print(f"Response time (s)   : {decision.response_time_seconds}")
#         print(f"\nPlan title cuối cùng: {final_plan.title}")

#     asyncio.run(_debug())