"""
LangGraph workflow chính - ghép toàn bộ 7 node lại với nhau, có
checkpoint vào PostgreSQL (dùng AsyncPostgresSaver).

Sơ đồ luồng:

    START
      │
      ▼
    guardrail ──(invalid)──> END (blocked)
      │ (valid)
      ▼
    supervisor
      │
      ▼
    planner <─────────────────────┐
      │ (thất bại LLM)            │ (rejected, còn lượt revise)
      ├──(fail)──> END            │
      ▼                           │
    hitl ───────────────────(rejected)
      │ (approved/edited/timeout, hoặc hết lượt revise plan -> force)
      ▼
    executor (fan-out workers theo batch, xem agents/executor/)
      │
      ▼
    image_resolver (resolve ảnh Wikimedia từ image_queries, 1 lần duy nhất)
      │
      ▼
    synthesizer <──────────────────┐
      │ (thất bại LLM)             │ (rejected, còn lượt revise)
      ├──(fail)──> END             │
      ▼                            │
    evaluator ───────────────(not accepted, revision_count < MAX)
      │ (accepted, hoặc hết lượt revise -> force accept)
      ▼
    save_output
      │
      ▼
     END

Logging: mỗi node đi qua đều được log qua agents/logger.py, ghi ra cả
console lẫn file riêng logs/workflow_{workflow_id}_{timestamp}.log.
"""

import os
import sys
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Fix cho Windows: psycopg (async mode) không tương thích với
# ProactorEventLoop mặc định của Windows, cần chuyển sang
# SelectorEventLoop. Không ảnh hưởng gì trên Linux/macOS.
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from agents.evaluator import run_evaluator
from agents.executor import execute_plan, resolve_images
from agents.hitl_handler import request_plan_approval
from agents.input_guardrails import check_input
from agents.logger import get_workflow_logger, log_node_end, log_node_error, log_node_start
from agents.planner import run_planner
from agents.schemas import MAX_REVISIONS, WriterState, UserRequest
from agents.supervisor import run_supervisor
from agents.synthesizer import run_synthesizer, save_article_to_markdown
from agents.base_agent import LLMOutputError

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Số lần tối đa Planner được tạo lại plan do user reject ở HITL.
# Khác với MAX_REVISIONS (giới hạn revision của FinalArticle ở
# Synthesizer<->Evaluator), giới hạn này áp cho vòng lặp
# Planner<->HITL, tránh trường hợp user reject vô hạn lần.
MAX_PLAN_REVISIONS = 3


# ============================================================
# NODE FUNCTIONS
# ============================================================
# Mỗi node function nhận WriterState đầy đủ, trả về DICT chỉ chứa
# các field cần UPDATE (LangGraph tự merge vào state chung).
# ============================================================


async def guardrail_node(state: WriterState) -> dict:
    logger = get_workflow_logger(state["workflow_id"])
    user_request = state["user_request"]
    raw_input = user_request.raw_input or user_request.topic

    log_node_start(logger, "guardrail")
    result = await check_input(raw_input)
    log_node_end(
        logger, "guardrail",
        is_valid=result.is_valid, category=result.category, reason=result.reason,
    )

    return {"guardrail": result}


def route_after_guardrail(state: WriterState) -> str:
    if state["guardrail"] is not None and state["guardrail"].is_valid:
        return "continue"
    return "blocked"


async def supervisor_node(state: WriterState) -> dict:
    logger = get_workflow_logger(state["workflow_id"])

    log_node_start(logger, "supervisor")
    decision = await run_supervisor(state["user_request"])
    log_node_end(logger, "supervisor", mode=decision.mode, reasoning=decision.reasoning)

    return {"supervisor": decision}


async def planner_node(state: WriterState) -> dict:
    logger = get_workflow_logger(state["workflow_id"])

    log_node_start(logger, "planner", plan_revision_count=state["plan_revision_count"])

    feedback = None
    if state.get("hitl") is not None and not state["hitl"].approved:
        feedback = state["hitl"].feedback

    try:
        plan = await run_planner(state["user_request"], state["supervisor"], feedback=feedback)
        log_node_end(logger, "planner", title=plan.title, tasks=len(plan.tasks))
        return {"plan": plan}
    except LLMOutputError as e:
        error_msg = f"[planner] Thất bại sau khi retry: {e}"
        log_node_error(logger, "planner", error_msg)
        return {"plan": None, "errors": [error_msg]}


def route_after_planner(state: WriterState) -> str:
    return "hitl" if state["plan"] is not None else "failed"


def hitl_node(state: WriterState) -> dict:
    """
    Node này giờ là SYNC (không async def), vì gọi interrupt() bên
    trong - LangGraph sẽ tự dừng graph ngay tại lời gọi này, trả
    quyền điều khiển ra ngoài cho code đang gọi graph.ainvoke().

    Logic đếm 60s timeout KHÔNG còn nằm ở đây nữa (khác bản cũ dùng
    asyncio.wait_for chặn trực tiếp) - giờ do
    backend/services/workflow_manager.py đảm nhiệm: nó gọi graph,
    nhận về __interrupt__, tự đếm 60s bằng background task, nếu hết
    giờ mà chưa có ai gọi API /hitl thì tự gửi
    Command(resume={"action": "timeout", ...}) để graph tiếp tục.
    """
    logger = get_workflow_logger(state["workflow_id"])
    log_node_start(logger, "hitl")

    # Nếu đã hết lượt revise plan, ép approve luôn plan hiện tại,
    # KHÔNG gọi interrupt() nữa (tránh loop reject vô hạn) - graph đi
    # thẳng qua executor mà không cần dừng chờ user lần nữa.
    if state["plan_revision_count"] >= MAX_PLAN_REVISIONS:
        msg = f"Đã đạt giới hạn {MAX_PLAN_REVISIONS} lần tạo lại plan. Tự động chấp nhận plan hiện tại."
        logger.warning("[hitl] %s", msg)

        from agents.schemas.hitl import HITLDecision

        decision = HITLDecision(
            action="timeout",
            approved=True,
            edited=False,
            feedback=None,
        )
        log_node_end(logger, "hitl", action=decision.action, approved=decision.approved, forced=True)
        return {"hitl": decision, "approved_plan": state["plan"]}

    decision, final_plan = request_plan_approval(state["plan"])

    log_node_end(logger, "hitl", action=decision.action, approved=decision.approved, edited=decision.edited)

    update: dict = {"hitl": decision}
    if decision.approved:
        update["approved_plan"] = final_plan
    else:
        update["plan_revision_count"] = state["plan_revision_count"] + 1

    return update


def route_after_hitl(state: WriterState) -> str:
    return "executor" if state["hitl"].approved else "planner"


async def executor_node(state: WriterState) -> dict:
    logger = get_workflow_logger(state["workflow_id"])

    log_node_start(logger, "executor", tasks=len(state["approved_plan"].tasks))

    outputs = await execute_plan(
        plan=state["approved_plan"],
        user_request=state["user_request"],
        supervisor=state["supervisor"],
    )

    success_count = sum(1 for o in outputs if o.success)
    log_node_end(logger, "executor", success=success_count, total=len(outputs))

    return {"worker_outputs": outputs}


async def image_resolver_node(state: WriterState) -> dict:
    logger = get_workflow_logger(state["workflow_id"])

    log_node_start(logger, "image_resolver")

    specs = await resolve_images(state["worker_outputs"])

    log_node_end(logger, "image_resolver", resolved=len(specs))

    return {"image_specs": specs}


async def synthesizer_node(state: WriterState) -> dict:
    logger = get_workflow_logger(state["workflow_id"])

    log_node_start(logger, "synthesizer", revision_count=state["revision_count"])

    is_revision = state.get("evaluation") is not None and not state["evaluation"].accepted
    revision_feedback = state["evaluation"].feedback if is_revision else None
    previous_article = state.get("final_article") if is_revision else None

    try:
        article = await run_synthesizer(
            plan=state["approved_plan"],
            worker_outputs=state["worker_outputs"],
            user_request=state["user_request"],
            image_specs=state.get("image_specs") or [],
            revision_feedback=revision_feedback,
            previous_article=previous_article,
        )
        log_node_end(
            logger, "synthesizer",
            title=article.title, version=article.version, word_count=article.word_count,
        )
        return {"final_article": article}
    except LLMOutputError as e:
        error_msg = f"[synthesizer] Thất bại sau khi retry: {e}"
        log_node_error(logger, "synthesizer", error_msg)
        return {"final_article": None, "errors": [error_msg]}


def route_after_synthesizer(state: WriterState) -> str:
    return "evaluator" if state["final_article"] is not None else "failed"


async def evaluator_node(state: WriterState) -> dict:
    logger = get_workflow_logger(state["workflow_id"])

    log_node_start(logger, "evaluator")

    evaluation = await run_evaluator(
        final_article=state["final_article"],
        user_request=state["user_request"],
        plan=state["approved_plan"],
    )

    log_node_end(
        logger, "evaluator",
        overall_score=evaluation.overall_score, accepted=evaluation.accepted,
    )

    update: dict = {"evaluation": evaluation}
    if not evaluation.accepted:
        update["revision_count"] = state["revision_count"] + 1

    return update


def route_after_evaluator(state: WriterState) -> str:
    if state["evaluation"].accepted:
        return "save_output"

    if state["revision_count"] >= MAX_REVISIONS:
        logger = get_workflow_logger(state["workflow_id"])
        logger.warning(
            "[evaluator] Đã đạt giới hạn %d lần revision. Chấp nhận bài viết với điểm hiện tại.",
            MAX_REVISIONS,
        )
        return "save_output"

    return "synthesizer"


async def save_output_node(state: WriterState) -> dict:
    logger = get_workflow_logger(state["workflow_id"])

    log_node_start(logger, "save_output")

    filepath = save_article_to_markdown(state["final_article"], workflow_id=state["workflow_id"])

    log_node_end(logger, "save_output", filepath=str(filepath))
    logger.info("=== Kết thúc workflow %s ===", state["workflow_id"])

    return {"output_markdown": state["final_article"].markdown}


# ============================================================
# BUILD GRAPH
# ============================================================

def build_graph_builder() -> StateGraph:
    """Khai báo toàn bộ node + edge, CHƯA compile (chưa gắn checkpointer)."""
    builder = StateGraph(WriterState)

    builder.add_node("guardrail", guardrail_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("planner", planner_node)
    builder.add_node("hitl", hitl_node)
    builder.add_node("executor", executor_node)
    builder.add_node("image_resolver", image_resolver_node)
    builder.add_node("synthesizer", synthesizer_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_node("save_output", save_output_node)

    builder.add_edge(START, "guardrail")
    builder.add_conditional_edges(
        "guardrail", route_after_guardrail, {"continue": "supervisor", "blocked": END}
    )
    builder.add_edge("supervisor", "planner")
    builder.add_conditional_edges(
        "planner", route_after_planner, {"hitl": "hitl", "failed": END}
    )
    builder.add_conditional_edges(
        "hitl", route_after_hitl, {"executor": "executor", "planner": "planner"}
    )
    builder.add_edge("executor", "image_resolver")
    builder.add_edge("image_resolver", "synthesizer")
    builder.add_conditional_edges(
        "synthesizer", route_after_synthesizer, {"evaluator": "evaluator", "failed": END}
    )
    builder.add_conditional_edges(
        "evaluator", route_after_evaluator, {"synthesizer": "synthesizer", "save_output": "save_output"}
    )
    builder.add_edge("save_output", END)

    return builder


@asynccontextmanager
async def get_compiled_graph():
    """
    Context manager tạo checkpointer PostgreSQL + compile graph.

    Cách dùng:
        async with get_compiled_graph() as graph:
            result = await graph.ainvoke(initial_state, config=...)
    """
    async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
        await checkpointer.setup()  # Tạo bảng checkpoint nếu chưa có (idempotent)
        graph = build_graph_builder().compile(checkpointer=checkpointer)
        yield graph


def build_initial_state(user_request: UserRequest, workflow_id: str) -> WriterState:
    """Tạo state khởi tạo cho 1 lần chạy workflow mới."""
    return {
        "workflow_id": workflow_id,
        "user_request": user_request,
        "guardrail": None,
        "supervisor": None,
        "plan": None,
        "approved_plan": None,
        "hitl": None,
        "plan_revision_count": 0,
        "worker_outputs": [],
        "image_specs": [],
        "final_article": None,
        "evaluation": None,
        "revision_count": 0,
        "errors": [],
        "output_markdown": None,
    }


async def run_workflow(user_request: UserRequest, workflow_id: str | None = None) -> WriterState:
    """
    Entry point cấp cao nhất - chạy toàn bộ workflow từ đầu tới cuối.

    `workflow_id` cũng chính là `thread_id` cho checkpoint của LangGraph
    (dùng để resume nếu bị gián đoạn giữa chừng - resume bằng cách gọi
    lại graph.ainvoke(None, config=cùng thread_id) thay vì initial_state).
    """
    workflow_id = workflow_id or str(uuid.uuid4())
    initial_state = build_initial_state(user_request, workflow_id)
    config = {"configurable": {"thread_id": workflow_id}}

    async with get_compiled_graph() as graph:
        final_state = await graph.ainvoke(initial_state, config=config)

    return final_state


# ============================================================
# DEBUG - Chạy trực tiếp file này để test FULL WORKFLOW end-to-end
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.graph
#
# Đây là bài test tốn thời gian nhất (full pipeline thật), sẽ dừng
# lại ở bước HITL chờ bạn gõ A/E/R trên terminal.
# ============================================================

# if __name__ == "__main__":
#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Full Workflow End-to-End")
#         print("=" * 60)

#         user_request = UserRequest(
#             topic="MCP (Model Context Protocol) cho AI Engineer",
#             article_type="blog",
#             target_audience="AI Engineer",
#             tone="technical",
#             language="vi",
#             raw_input="Viết một bài blog bằng tiếng Việt về MCP cho AI Engineer.",
#         )

#         final_state = await run_workflow(user_request)

#         print("\n" + "=" * 60)
#         print("KẾT QUẢ CUỐI CÙNG CỦA WORKFLOW")
#         print("=" * 60)
#         print(f"Workflow ID     : {final_state['workflow_id']}")
#         print(f"Guardrail valid : {final_state['guardrail'].is_valid if final_state['guardrail'] else None}")
#         print(f"Plan revisions  : {final_state['plan_revision_count']}")
#         print(f"Article revisions: {final_state['revision_count']}")
#         print(f"Errors          : {final_state['errors']}")

#         if final_state.get("output_markdown"):
#             print(f"\n✅ Bài viết cuối cùng đã lưu thành công.")
#             print(f"Overall score: {final_state['evaluation'].overall_score}")
#             print(f"📄 Xem log chi tiết tại: logs/workflow_{final_state['workflow_id']}_*.log")
#         else:
#             print("\n❌ Workflow không hoàn thành (bị block hoặc lỗi giữa chừng).")

#     asyncio.run(_debug())