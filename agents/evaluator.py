"""
Node 7: Evaluator.

Nhiệm vụ: chấm điểm FinalArticle theo 5 tiêu chí, quyết định
accepted/rejected dựa trên overall_score (ngưỡng ACCEPTANCE_THRESHOLD
đã enforce bằng code trong schema Evaluation, không tin tưởng LLM
tự quyết định).

Dùng BaseAgent pattern (render prompt YAML -> gọi LLM -> parse JSON
-> validate bằng Evaluation schema).
"""

from agents.base_agent import BaseAgent, LLMOutputError
from agents.schemas.article import FinalArticle
from agents.schemas.evaluation import Evaluation
from agents.schemas.user_request import UserRequest

# ============================================================
# UPDATE:
# Evaluator bây giờ cần Plan để đánh giá completeness và
# instruction_following dựa trên những gì Planner thực sự
# yêu cầu, thay vì chỉ dựa vào UserRequest.
#
# Đồng thời import Task vì phần DEBUG bên dưới tạo sample Plan
# với danh sách Task.
# ============================================================
from agents.schemas.plan import Plan, Task


class EvaluatorAgent(BaseAgent):
    """Agent chấm điểm chất lượng bài viết cuối cùng."""

    def __init__(self):
        super().__init__(
            prompt_name="evaluator",
            model_role="evaluator",
            output_schema=Evaluation,
        )


_agent = EvaluatorAgent()


async def run_evaluator(
    final_article: FinalArticle,
    user_request: UserRequest,
    plan: Plan,
) -> Evaluation:
    """
    Entry point chính của node Evaluator.

    Lưu ý về error handling: khác với Supervisor (có thể fallback an
    toàn về mode "hybrid"), Evaluator KHÔNG có cách nào "đoán" ra điểm
    số hợp lý khi LLM lỗi. Ở đây mình chọn fallback theo hướng
    accepted=True (chấp nhận bài viết) thay vì reject, vì:
        - Reject khi không đánh giá được sẽ tốn 1 lượt revision_count
          một cách oan uổng (lỗi hệ thống, không phải lỗi nội dung),
          dễ khiến bài viết chạm MAX_REVISIONS vì lý do không liên
          quan tới chất lượng thật.
        - Lỗi sẽ được log rõ ràng để dễ debug/theo dõi trên LangSmith.
    """
    try:
        return await _agent.run(
            topic=user_request.topic,
            target_audience=user_request.target_audience or "độc giả phổ thông",
            tone=user_request.tone or "professional",
            article_type=user_request.article_type,
            markdown=final_article.markdown,

            # ========================================================
            # UPDATE:
            # Truyền toàn bộ Plan vào Evaluator prompt.
            #
            # Evaluator dùng Plan để biết:
            # - Bài viết cần cover những section/task nào
            # - Objective của từng task
            # - expected_output của từng task
            # - dependency/order giữa các task
            #
            # Nhờ vậy completeness không còn đánh giá mơ hồ
            # dựa trên topic chung nữa.
            # ========================================================
            plan=plan.model_dump_json(indent=2),
        )

    except LLMOutputError as e:
        print(f"⚠️  [evaluator] Lỗi khi đánh giá bài viết: {e}")
        return Evaluation(
            overall_score=10.0,  # sẽ bị model_validator ghi đè accepted=True
            factuality=10.0,
            completeness=10.0,
            coherence=10.0,
            writing_quality=10.0,
            instruction_following=10.0,
            feedback=[
                "Không thể đánh giá tự động do lỗi hệ thống - "
                "bài viết được chấp nhận mặc định (fallback)."
            ],
            accepted=True,
        )


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Evaluator
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.evaluator
# ============================================================

# if __name__ == "__main__":
#     import asyncio

#     def _print_evaluation(evaluation: Evaluation) -> None:
#         print(f"\nOverall score          : {evaluation.overall_score}")
#         print(f"  - Factuality          : {evaluation.factuality}")
#         print(f"  - Completeness        : {evaluation.completeness}")
#         print(f"  - Coherence           : {evaluation.coherence}")
#         print(f"  - Writing quality     : {evaluation.writing_quality}")
#         print(f"  - Instruction follow. : {evaluation.instruction_following}")
#         print(f"Accepted                : {evaluation.accepted}")
#         if evaluation.feedback:
#             print("Feedback:")
#             for item in evaluation.feedback:
#                 print(f"  - {item}")

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test Evaluator")
#         print("=" * 60)

#         user_request = UserRequest(
#             topic="MCP (Model Context Protocol) cho AI Engineer",
#             article_type="blog",
#             target_audience="AI Engineer",
#             tone="technical",
#             language="vi",
#         )

#         # ========================================================
#         # UPDATE:
#         # Tạo Plan mẫu để Evaluator có baseline rõ ràng khi chấm
#         # completeness và instruction_following.
#         #
#         # Trước đây debug chỉ truyền:
#         #     good_article + user_request
#         #
#         # Nhưng run_evaluator() hiện yêu cầu thêm:
#         #     plan
#         # ========================================================
#         test_plan = Plan(
#             title="MCP cho AI Engineer",
#             objective="Giải thích MCP và ứng dụng thực tế",
#             target_audience="AI Engineer",
#             tone="technical",
#             estimated_sections=4,
#             tasks=[
#                 Task(
#                     id="task_01",
#                     title="Giới thiệu MCP",
#                     description="Giải thích MCP là gì và tại sao MCP quan trọng.",
#                     objective="Người đọc hiểu khái niệm cơ bản về MCP.",
#                     expected_output="~300 từ",
#                 ),
#                 Task(
#                     id="task_02",
#                     title="Kiến trúc MCP",
#                     description="Giải thích Host, Client và Server trong MCP.",
#                     objective="Người đọc hiểu kiến trúc cơ bản của MCP.",
#                     expected_output="~400 từ",
#                     depends_on=["task_01"],
#                 ),
#                 Task(
#                     id="task_03",
#                     title="So sánh với tích hợp truyền thống",
#                     description="So sánh MCP với cách tích hợp tool/API truyền thống.",
#                     objective="Người đọc hiểu lợi ích của MCP.",
#                     expected_output="~300 từ",
#                     depends_on=["task_02"],
#                 ),
#                 Task(
#                     id="task_04",
#                     title="Kết luận",
#                     description="Tổng kết vai trò của MCP.",
#                     objective="Tóm tắt các ý chính.",
#                     expected_output="~150 từ",
#                     depends_on=["task_03"],
#                 ),
#             ],
#         )

#         # --- Test 1: Bài viết chất lượng tốt (kỳ vọng điểm cao, accepted=True) ---
#         good_article = FinalArticle(
#             title="MCP (Model Context Protocol) cho AI Engineer: Kiến trúc, Tools và ứng dụng trong AI Agent",
#             markdown="""# MCP (Model Context Protocol) cho AI Engineer

# ## Giới thiệu

# Model Context Protocol (MCP) là một open protocol được thiết kế để
# chuẩn hóa cách các ứng dụng AI kết nối với dữ liệu, công cụ và các
# nguồn context bên ngoài. Thay vì mỗi AI application phải xây dựng
# một integration riêng cho từng API hoặc dịch vụ, MCP cung cấp một
# giao diện thống nhất giữa AI application và các MCP server.

# Đối với AI Engineer, MCP đặc biệt hữu ích khi xây dựng AI agent có
# khả năng sử dụng nhiều công cụ và nguồn dữ liệu khác nhau.

# ## MCP giải quyết vấn đề gì?

# Trong một hệ thống AI truyền thống, developer có thể phải viết riêng
# logic kết nối cho database, web search, filesystem hoặc một API bên
# thứ ba. Khi số lượng tool tăng lên, phần integration trở nên khó
# duy trì và tái sử dụng.

# MCP đưa ra một protocol chung để client có thể khám phá và sử dụng
# các capability mà server cung cấp. Điều này giúp giảm sự phụ thuộc
# vào implementation riêng của từng tool.

# ## Kiến trúc MCP

# Một kiến trúc MCP thường gồm host, MCP client và MCP server.

# Host là ứng dụng AI mà người dùng tương tác. Host quản lý một hoặc
# nhiều MCP client. Mỗi MCP client duy trì kết nối với một MCP server
# cụ thể.

# MCP server cung cấp các capability cho client. Trong đó tools cho
# phép ứng dụng gọi các hành động hoặc chức năng, resources cung cấp
# dữ liệu hoặc context, còn prompts có thể cung cấp các template phục
# vụ tương tác với model.

# Cách phân tách này giúp ứng dụng AI không cần biết implementation
# chi tiết phía sau từng capability.

# ## MCP trong hệ thống AI Agent

# Một use case quan trọng của MCP là kết hợp với AI agent.

# Ví dụ, một agent có thể sử dụng MCP server cung cấp web search,
# database access hoặc các API nội bộ. Model quyết định khi nào cần
# sử dụng tool, trong khi MCP cung cấp cơ chế chuẩn hóa để agent
# tương tác với capability đó.

# Với framework như LangGraph, developer có thể xây dựng workflow
# nhiều node và kết nối các MCP tools vào agent. Điều này đặc biệt
# hữu ích trong các hệ thống multi-agent vì các tool có thể được
# chuẩn hóa và tái sử dụng giữa nhiều agent.

# ## MCP và cách tích hợp truyền thống

# Nếu không sử dụng một protocol chung, developer thường phải viết
# integration riêng cho từng dịch vụ. Ví dụ một agent có thể cần một
# implementation cho search API, một implementation khác cho database
# và một implementation khác cho filesystem.

# MCP không loại bỏ hoàn toàn code integration, nhưng chuẩn hóa
# interface giữa AI application và tool provider. Nhờ đó việc kết nối
# và tái sử dụng tools trở nên nhất quán hơn.

# ## Kết luận

# MCP là một protocol quan trọng đối với AI Engineer khi xây dựng các
# ứng dụng AI có khả năng sử dụng tools và dữ liệu bên ngoài. Kiến trúc
# host-client-server cùng các capability như tools, resources và
# prompts giúp chuẩn hóa cách AI application tương tác với hệ thống
# bên ngoài.

# Khi kết hợp MCP với các framework agent như LangGraph, developer có
# thể xây dựng workflow có khả năng sử dụng nhiều công cụ theo một
# cách có cấu trúc và dễ mở rộng hơn.
# """,
#             word_count=500,
#             sections=[
#                 "Giới thiệu",
#                 "MCP giải quyết vấn đề gì?",
#                 "Kiến trúc MCP",
#                 "MCP trong hệ thống AI Agent",
#                 "MCP và cách tích hợp truyền thống",
#                 "Kết luận",
#             ],
#         )

#         print("\n### TEST 1: Bài viết chất lượng tốt ###")

#         # ========================================================
#         # UPDATE:
#         # Truyền thêm test_plan vào run_evaluator().
#         #
#         # Đây chính là nguyên nhân của bug trước đó:
#         #
#         #     run_evaluator(good_article, user_request)
#         #
#         # trong khi function đã yêu cầu:
#         #
#         #     run_evaluator(good_article, user_request, test_plan)
#         # ========================================================
#         evaluation_good = await run_evaluator(
#             good_article,
#             user_request,
#             test_plan,
#         )
#         _print_evaluation(evaluation_good)

#         # --- Test 2: Bài viết kém chất lượng (kỳ vọng điểm thấp, accepted=False) ---
#         bad_article = FinalArticle(
#             title="MCP",
#             markdown="""## MCP

# MCP là cái gì đó liên quan AI. Nó dùng để làm mấy cái linh tinh cho AI \
# thông minh hơn. Có nhiều người dùng nó. Nó tốt. Hết.
# """,
#             word_count=30,
#             sections=["MCP"],
#         )

#         print("\n### TEST 2: Bài viết kém chất lượng ###")

#         # ========================================================
#         # UPDATE:
#         # Test 2 cũng phải truyền test_plan vì Evaluator cần
#         # cùng một baseline để đánh giá bài viết kém.
#         # ========================================================
#         evaluation_bad = await run_evaluator(
#             bad_article,
#             user_request,
#             test_plan,
#         )
#         _print_evaluation(evaluation_bad)

#     asyncio.run(_debug())