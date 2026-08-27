"""
Node 6: Synthesizer (Final Writer).

Nhiệm vụ: tổng hợp danh sách WorkerOutput (đã sắp xếp theo order) +
Plan gốc thành 1 FinalArticle hoàn chỉnh, mạch lạc, nhất quán văn phong.

Cũng chính là node được gọi lại trong vòng lặp Revision (Synthesizer
<-> Evaluator) khi Evaluator từ chối bài viết - lúc đó sẽ truyền thêm
`previous_article` + `revision_feedback` để Synthesizer viết lại có
định hướng thay vì viết lại từ đầu một cách ngẫu nhiên.

Lưu ý: các task bị lỗi (WorkerOutput.success=False) sẽ được LOẠI BỎ
khỏi input đưa cho LLM (theo chiến lược "bỏ qua và log lỗi"), và được
ghi nhận lại trong FinalArticle.skipped_task_ids.
"""

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent, LLMOutputError
from agents.schemas.article import FinalArticle
from agents.schemas.plan import Plan
from agents.schemas.user_request import UserRequest
from agents.schemas.worker import WorkerOutput

# ============================================================
# OUTPUT DIRECTORY - nơi lưu file .md khi bài viết được Evaluator duyệt
# ============================================================

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"

class _SynthesizerLLMOutput(BaseModel):
    """
    Schema NỘI BỘ chỉ dùng để parse/validate output thô của LLM.

    Các field còn lại của FinalArticle (word_count, images,
    skipped_task_ids, version) do CODE tự tính, không phải LLM sinh ra.
    """

    title: str
    markdown: str
    sections: list[str] = Field(default_factory=list)


class SynthesizerAgent(BaseAgent):
    """Agent tổng hợp các section thành bài viết hoàn chỉnh."""

    def __init__(self):
        super().__init__(
            prompt_name="synthesizer",
            model_role="synthesizer",
            output_schema=_SynthesizerLLMOutput,
        )


_agent = SynthesizerAgent()


def _count_words(text: str) -> int:
    """Đếm số từ đơn giản bằng cách split theo whitespace."""
    return len(text.split())


async def run_synthesizer(
    plan: Plan,
    worker_outputs: list[WorkerOutput],
    user_request: UserRequest,
    revision_feedback: list[str] | None = None,
    previous_article: FinalArticle | None = None,
) -> FinalArticle:
    """
    Entry point chính của node Synthesizer.

    Args:
        plan: Plan đã được approve (dùng title/objective/tone gốc).
        worker_outputs: Kết quả từ Executor, ĐÃ sắp xếp theo order
            (execute_plan() đã tự sắp xếp sẵn).
        user_request: Yêu cầu gốc của user.
        revision_feedback: Feedback từ Evaluator, chỉ truyền khi đây
            là lần viết lại (revision), None nếu là lần viết đầu tiên.
        previous_article: Bài viết ở lần viết trước đó (chỉ truyền khi
            revision), dùng để LLM biết cần sửa cái gì thay vì viết
            lại hoàn toàn từ đầu.

    Raises:
        LLMOutputError: nếu LLM không tạo ra được output hợp lệ sau
            khi đã retry. Synthesizer KHÔNG có fallback hợp lý (không
            thể "đoán đại" ra 1 bài viết), nên để lỗi propagate lên
            cho graph.py tự quyết định (dừng workflow, báo lỗi user).
    """
    successful_outputs = [o for o in worker_outputs if o.success]
    skipped_task_ids = [o.task_id for o in worker_outputs if not o.success]

    if skipped_task_ids:
        print(
            f"⚠️  [synthesizer] Bỏ qua {len(skipped_task_ids)} task bị lỗi: "
            f"{skipped_task_ids}"
        )

    sections_payload = [
        {"task_id": o.task_id, "title": o.title, "content": o.content}
        for o in successful_outputs
    ]

    llm_output: _SynthesizerLLMOutput = await _agent.run(
        title=plan.title,
        objective=plan.objective,
        target_audience=plan.target_audience,
        tone=plan.tone,
        language=user_request.language,
        sections=sections_payload,
        revision_feedback=revision_feedback,
        previous_markdown=previous_article.markdown if previous_article else None,
    )

    next_version = (previous_article.version + 1) if previous_article else 1

    return FinalArticle(
        title=llm_output.title,
        markdown=llm_output.markdown,
        word_count=_count_words(llm_output.markdown),
        sections=llm_output.sections,
        images=[],  # TODO: gắn ảnh Wikimedia vào bước sau (image subgraph riêng)
        skipped_task_ids=skipped_task_ids,
        version=next_version,
    )

def _slugify(text: str) -> str:
    """
    Chuyển title (có thể chứa tiếng Việt có dấu) thành slug an toàn
    để đặt tên file, ví dụ:
        "MCP cho AI Engineer!" -> "mcp-cho-ai-engineer"
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w\s-]", "", ascii_text).strip().lower()
    slug = re.sub(r"[\s_-]+", "-", cleaned)
    return slug or "untitled"


def _ensure_output_dir() -> Path:
    """
    Đảm bảo thư mục outputs/ tồn tại ở root project.

    Chỉ in log + tạo mới nếu CHƯA tồn tại (lần đầu tiên). Nếu đã có
    sẵn thì bỏ qua hoàn toàn, không làm gì thêm (đúng yêu cầu).
    """
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"📁 [synthesizer] Lần đầu tạo thư mục outputs/ tại: {OUTPUT_DIR}")
    return OUTPUT_DIR


def save_article_to_markdown(
    article: FinalArticle,
    workflow_id: str | None = None,
) -> Path:
    """
    Ghi FinalArticle ra file .md trong thư mục outputs/ ở root project.

    CHỈ nên gọi hàm này SAU KHI Evaluator đã accepted=True (do graph.py
    quyết định gọi ở thời điểm nào), không gọi ngay trong run_synthesizer()
    vì tại thời điểm đó bài viết CHƯA được Evaluator chấm điểm.

    Tên file: {slug-title}_{timestamp_với_microsecond}[_{workflow_id}].md
    Ví dụ: mcp-cho-ai-engineer_20260827_153045_123456.md

    Returns:
        Path tới file .md vừa ghi (để log/trace, hoặc trả về cho user
        qua API sau này).
    """
    output_dir = _ensure_output_dir()

    # Dùng %f (microsecond) để đảm bảo unique dù gọi liên tiếp trong
    # cùng 1 giây (ví dụ retry nhanh, hoặc chạy nhiều test liên tiếp).
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    slug = _slugify(article.title)

    filename_parts = [slug, timestamp]
    if workflow_id:
        # Không cắt ngắn tùy tiện - giữ nguyên workflow_id để đảm bảo
        # unique. Nếu workflow_id là UUID dài, có thể cắt an toàn hơn
        # bằng cách lấy 8 ký tự cuối (thường là phần random nhất),
        # nhưng ở đây giữ nguyên cho đơn giản và chắc chắn không đụng độ.
        filename_parts.append(workflow_id)
    filename = "_".join(filename_parts) + ".md"

    filepath = output_dir / filename
    filepath.write_text(article.markdown, encoding="utf-8")

    print(f"✅ [synthesizer] Đã lưu bài viết vào: {filepath}")
    return filepath


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Synthesizer
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.synthesizer
# ============================================================

# if __name__ == "__main__":
#     import asyncio

#     from agents.schemas.plan import Task

#     def _print_article(article: FinalArticle) -> None:
#         print(f"\nTitle          : {article.title}")
#         print(f"Version        : {article.version}")
#         print(f"Word count     : {article.word_count}")
#         print(f"Sections       : {article.sections}")
#         print(f"Skipped tasks  : {article.skipped_task_ids}")
#         print("-" * 60)
#         print(article.markdown)

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test Synthesizer")
#         print("=" * 60)

#         user_request = UserRequest(
#             topic="MCP (Model Context Protocol) cho AI Engineer",
#             article_type="blog",
#             target_audience="AI Engineer",
#             tone="technical",
#             language="vi",
#         )

#         plan = Plan(
#             title="MCP cho AI Engineer",
#             objective="Giải thích MCP và giá trị thực tiễn cho AI Engineer.",
#             target_audience="AI Engineer",
#             tone="technical",
#             estimated_sections=3,
#             tasks=[
#                 Task(id="task_01", title="Giới thiệu", description="...", objective="...", expected_output="...", order=0),
#                 Task(id="task_02", title="Kiến trúc", description="...", objective="...", expected_output="...", order=1, depends_on=["task_01"]),
#                 Task(id="task_03", title="Kết luận", description="...", objective="...", expected_output="...", order=2, depends_on=["task_02"]),
#             ],
#         )

#         worker_outputs = [
#             WorkerOutput(
#                 task_id="task_01",
#                 title="Giới thiệu MCP",
#                 content="MCP (Model Context Protocol) là một tiêu chuẩn mở do Anthropic phát triển, cho phép LLM kết nối với dữ liệu và công cụ bên ngoài một cách nhất quán.",
#                 success=True,
#             ),
#             WorkerOutput(
#                 task_id="task_02",
#                 title="Kiến trúc kỹ thuật",
#                 content="",
#                 success=False,
#                 error="LLM timeout sau 3 lần retry",
#             ),
#             WorkerOutput(
#                 task_id="task_03",
#                 title="Kết luận",
#                 content="Tóm lại, MCP mở ra một hướng đi mới cho việc chuẩn hóa tích hợp AI với thế giới bên ngoài.",
#                 success=True,
#             ),
#         ]

#         # --- Test 1: Tổng hợp lần đầu (có 1 task bị lỗi, phải bị bỏ qua) ---
#         print("\n### TEST 1: Tổng hợp lần đầu (task_02 bị lỗi) ###")
#         article = None
#         try:
#             article = await run_synthesizer(plan, worker_outputs, user_request)
#             _print_article(article)
#         except LLMOutputError as e:
#             print(f"❌ Synthesizer thất bại: {e}")

#         # --- Test 2: Revision - giả lập Evaluator từ chối, yêu cầu viết lại ---
#         if article is not None:
#             print("\n\n### TEST 2: Revision sau khi Evaluator từ chối ###")
#             revised_article = await run_synthesizer(
#                 plan,
#                 worker_outputs,
#                 user_request,
#                 revision_feedback=[
#                     "Phần giới thiệu quá ngắn, cần mở rộng thêm về bối cảnh ra đời của MCP.",
#                     "Cần thêm ví dụ cụ thể để bài viết sinh động hơn.",
#                 ],
#                 previous_article=article,
#             )
#             _print_article(revised_article)
#             assert revised_article.version == article.version + 1, "❌ Version không tăng đúng!"
#             print(f"\n✅ Version tăng đúng: {article.version} -> {revised_article.version}")

#         # --- Test 3: Lưu bài viết ra file .md (giả lập Evaluator đã duyệt) ---
#         if article is not None:
#             print("\n\n### TEST 3: Lưu bài viết ra outputs/ (giả lập evaluator.accepted=True) ###")

#             # Gọi 2 lần liên tiếp để chứng minh: folder chỉ log "tạo mới" ở
#             # lần đầu tiên (nếu chưa tồn tại), lần sau không log lại.
#             filepath_1 = save_article_to_markdown(article, workflow_id="test-workflow-001")
#             filepath_2 = save_article_to_markdown(article, workflow_id="test-workflow-002")

#             assert filepath_1.parent == OUTPUT_DIR, "❌ File không nằm trong outputs/!"
#             assert filepath_1.exists(), "❌ File 1 không được tạo!"
#             assert filepath_2.exists(), "❌ File 2 không được tạo!"
#             assert filepath_1 != filepath_2, "❌ 2 file bị trùng tên (thiếu timestamp/workflow_id)!"

#             print(f"\n✅ Đúng: outputs/ chỉ được tạo 1 lần, 2 file khác tên nhau:")
#             print(f"   - {filepath_1.name}")
#             print(f"   - {filepath_2.name}")

#     asyncio.run(_debug())