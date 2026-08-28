"""
Multi-Agent Writer - Package chứa toàn bộ logic agent của hệ thống.

Export API cấp cao nhất để nơi khác (backend/, notebook/, hoặc script
ngoài) chỉ cần import từ đây, không cần biết cấu trúc nội bộ:

    from agents import run_workflow, UserRequest

    result = await run_workflow(
        UserRequest(topic="MCP cho AI Engineer", language="vi")
    )

Các thành phần chi tiết hơn (từng node, schemas, tools...) vẫn có thể
import trực tiếp từ submodule tương ứng khi cần, ví dụ:

    from agents.schemas import Plan, Task
    from agents.executor import execute_plan
"""

from agents.graph import build_graph_builder, get_compiled_graph, run_workflow
from agents.schemas.state import WriterState
from agents.schemas.user_request import UserRequest

__version__ = "0.1.0"

__all__ = [
    "run_workflow",
    "build_graph_builder",
    "get_compiled_graph",
    "UserRequest",
    "WriterState",
]