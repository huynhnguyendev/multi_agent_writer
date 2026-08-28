"""
Logic xử lý MỘT Worker - nhận 1 Task cụ thể, trả về WorkerOutput.

Trách nhiệm của 1 Worker:
    1. Nếu task.requires_research: gọi Tavily search với các
       research_queries đã có sẵn trong Task (do Planner đề xuất).
    2. Lấy context từ các task mà nó phụ thuộc (nếu có), dựa trên
       WorkerOutput của các task đã hoàn thành ở batch trước.
    3. Gọi LLM (worker.yaml prompt) để viết nội dung section.
    4. Trả về WorkerOutput hoàn chỉnh.

Error handling: theo chiến lược "bỏ qua và log lỗi" - nếu có lỗi ở
bất kỳ bước nào (research fail, LLM fail...), Worker KHÔNG raise
exception ra ngoài mà trả về WorkerOutput(success=False, error=...).
Có retry nội bộ tối đa MAX_WORKER_RETRIES lần cho các lỗi tạm thời,
kèm delay (backoff) giữa các lần retry để tránh dính lại đúng rate
limit TPM của Groq (free tier) khi nhiều worker chạy song song
trong cùng 1 batch, trước khi đánh dấu thất bại hẳn.
"""

import asyncio

from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent, LLMOutputError
from agents.executor.task_manager import get_dependency_context
from agents.schemas import Task, ResearchSource, SupervisorDecision, UserRequest, WorkerOutput
from agents.tools import tavily_search

MAX_WORKER_RETRIES = 2

# Delay (giây) trước mỗi lần retry, để "hồi" lại token budget/phút của
# Groq free tier trước khi thử lại (tránh dính lại đúng rate limit).
WORKER_RETRY_BACKOFF_SECONDS = 8

# Giới hạn số research_queries thực sự đi search (tránh 1 task có quá
# nhiều query làm tốn thời gian/chi phí), theo đúng field research_queries
# mà Planner đã đề xuất trong Task.
MAX_RESEARCH_QUERIES_PER_TASK = 2
MAX_RESULTS_PER_QUERY = 3


class _WorkerLLMOutput(BaseModel):
    """
    Schema NỘI BỘ chỉ dùng để parse/validate output thô của LLM.

    Khác với WorkerOutput (schema chính thức của toàn bộ hệ thống),
    schema này KHÔNG có task_id, sources, success, error, retry_count
    - những field đó do code (không phải LLM) tự điền vào sau khi
    LLM trả lời xong.
    """

    title: str
    content: str
    used_research: bool = False
    image_queries: list[str] = Field(default_factory=list)


class WorkerAgent(BaseAgent):
    """Agent viết nội dung cho 1 task, dùng chung cho cả research/no-research."""

    def __init__(self, model_role: str = "worker"):
        super().__init__(
            prompt_name="worker",
            model_role=model_role,
            output_schema=_WorkerLLMOutput,
        )


# 2 instance riêng biệt theo đúng MODEL_REGISTRY (hiện tại cùng model,
# nhưng tách sẵn để sau này dễ đổi model riêng cho research_worker).
_worker_agent = WorkerAgent(model_role="worker")
_research_worker_agent = WorkerAgent(model_role="research_worker")


async def _gather_research(task: Task) -> list[ResearchSource]:
    """
    Gọi Tavily search cho từng research_query của task (giới hạn số
    lượng query để tránh tốn kém), gộp lại và loại bỏ source trùng URL.
    """
    queries = task.research_queries[:MAX_RESEARCH_QUERIES_PER_TASK]
    if not queries:
        return []

    results = await asyncio.gather(
        *[tavily_search(q, max_results=MAX_RESULTS_PER_QUERY) for q in queries]
    )

    seen_urls: set[str] = set()
    sources: list[ResearchSource] = []
    for result in results:
        for source in result.sources:
            if source.url and source.url not in seen_urls:
                seen_urls.add(source.url)
                sources.append(source)

    return sources


async def _run_worker_once(
    task: Task,
    user_request: UserRequest,
    supervisor: SupervisorDecision | None,
    completed_outputs: list[WorkerOutput],
) -> WorkerOutput:
    """Chạy 1 lần xử lý task (không retry). Có thể raise exception."""
    sources: list[ResearchSource] = []
    if task.requires_research:
        sources = await _gather_research(task)

    dependency_context = get_dependency_context(task, completed_outputs)

    agent = _research_worker_agent if task.requires_research else _worker_agent

    llm_output: _WorkerLLMOutput = await agent.run(
        topic=user_request.topic,
        target_audience=user_request.target_audience or "độc giả phổ thông",
        tone=user_request.tone or "professional",
        language=user_request.language,
        task_title=task.title,
        task_description=task.description,
        task_objective=task.objective,
        task_expected_output=task.expected_output,
        dependency_context=dependency_context,
        research_sources=[s.model_dump() for s in sources],
    )

    return WorkerOutput(
        task_id=task.id,
        title=llm_output.title,
        content=llm_output.content,
        sources=sources,
        used_research=llm_output.used_research,
        image_queries=llm_output.image_queries,
        success=True,
        error=None,
        retry_count=0,
    )


async def run_worker(
    task: Task,
    user_request: UserRequest,
    supervisor: SupervisorDecision | None = None,
    completed_outputs: list[WorkerOutput] | None = None,
) -> WorkerOutput:
    """
    Entry point chính của 1 Worker. Retry tối đa MAX_WORKER_RETRIES lần
    nếu gặp lỗi, trước khi đánh dấu WorkerOutput(success=False).

    Có delay (backoff) giữa các lần retry (KHÔNG delay trước lần thử
    đầu tiên, và KHÔNG delay sau lần thử cuối cùng vì sắp trả kết quả
    thất bại luôn rồi, delay lúc đó chỉ tốn thời gian vô ích).

    KHÔNG BAO GIỜ raise exception ra ngoài - đây là node cần đảm bảo
    Executor có thể chạy song song nhiều worker mà 1 worker lỗi không
    làm sập cả batch (theo chiến lược "bỏ qua và log lỗi").
    """
    completed_outputs = completed_outputs or []
    last_error: Exception | None = None

    for attempt in range(MAX_WORKER_RETRIES + 1):
        try:
            output = await _run_worker_once(task, user_request, supervisor, completed_outputs)
            output.retry_count = attempt
            return output
        except (LLMOutputError, Exception) as e:
            last_error = e
            print(
                f"⚠️  [worker:{task.id}] Lần thử {attempt + 1} thất bại: {e}"
            )

            is_last_attempt = attempt == MAX_WORKER_RETRIES
            if not is_last_attempt:
                print(
                    f"   ⏳ Chờ {WORKER_RETRY_BACKOFF_SECONDS}s trước khi retry "
                    "(tránh dính lại rate limit)..."
                )
                await asyncio.sleep(WORKER_RETRY_BACKOFF_SECONDS)

    print(f"❌ [worker:{task.id}] Thất bại hẳn sau {MAX_WORKER_RETRIES + 1} lần thử.")
    return WorkerOutput(
        task_id=task.id,
        title=task.title,
        content="",
        sources=[],
        used_research=False,
        image_queries=[],
        success=False,
        error=str(last_error),
        retry_count=MAX_WORKER_RETRIES + 1,
    )


# ============================================================
# DEBUG - Chạy trực tiếp file này để test 1 Worker
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.executor.worker
# ============================================================

# if __name__ == "__main__":

#     def _print_output(output: WorkerOutput) -> None:
#         print(f"\nTask ID       : {output.task_id}")
#         print(f"Success       : {output.success}")
#         if not output.success:
#             print(f"Error         : {output.error}")
#             return
#         print(f"Title         : {output.title}")
#         print(f"Used research : {output.used_research}")
#         print(f"Sources       : {[s.url for s in output.sources]}")
#         print(f"Image queries : {output.image_queries}")
#         print(f"Content:\n{output.content}")

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test Worker")
#         print("=" * 60)

#         user_request = UserRequest(
#             topic="MCP (Model Context Protocol) cho AI Engineer",
#             article_type="blog",
#             target_audience="AI Engineer",
#             tone="technical",
#             language="vi",
#         )

#         # --- Test 1: Task KHÔNG cần research ---
#         task_no_research = Task(
#             id="task_01",
#             title="Giới thiệu MCP",
#             description="Giải thích MCP là gì ở mức khái niệm cơ bản.",
#             objective="Người đọc hiểu MCP là gì và tại sao nó quan trọng.",
#             expected_output="Đoạn văn khoảng 200 từ.",
#             requires_research=False,
#         )

#         print("\n### TEST 1: Task không cần research ###")
#         output_1 = await run_worker(task_no_research, user_request)
#         _print_output(output_1)

#         # --- Test 2: Task CẦN research (gọi Tavily thật) ---
#         task_with_research = Task(
#             id="task_02",
#             title="Tình hình phát triển MCP gần đây",
#             description="Nêu các cập nhật, phiên bản mới của MCP gần đây.",
#             objective="Người đọc biết được xu hướng phát triển mới nhất của MCP.",
#             expected_output="Đoạn văn khoảng 250 từ, có dẫn chứng cụ thể.",
#             requires_research=True,
#             research_queries=["Model Context Protocol latest updates 2026"],
#         )

#         print("\n### TEST 2: Task cần research (gọi Tavily thật) ###")
#         output_2 = await run_worker(task_with_research, user_request)
#         _print_output(output_2)

#         # --- Test 3: Task phụ thuộc vào task_01 (dùng dependency_context) ---
#         task_dependent = Task(
#             id="task_03",
#             title="Kết luận",
#             description="Tổng kết lại những gì đã trình bày ở phần giới thiệu.",
#             objective="Chốt lại ý chính, liên kết với nội dung đã viết trước đó.",
#             expected_output="Đoạn văn khoảng 150 từ.",
#             requires_research=False,
#             depends_on=["task_01"],
#         )

#         print("\n### TEST 3: Task phụ thuộc task_01 (test dependency_context) ###")
#         output_3 = await run_worker(
#             task_dependent,
#             user_request,
#             completed_outputs=[output_1],
#         )
#         _print_output(output_3)

#     asyncio.run(_debug())