"""
Schema cho Plan và Task.

Planner biến:
    User Request → Plan
                      ├── Task 1
                      ├── Task 2
                      ├── ...
                      └── Task N

Đây là phần rất quan trọng vì toàn bộ Worker phía sau
sẽ phụ thuộc vào Plan.

Task Dependency (DAG):
    - Nếu task.depends_on = [] → task độc lập, có thể chạy song song.
    - Nếu task.depends_on = ["task_01"] → task phải chờ task_01
      hoàn thành xong mới được chạy.
    - Executor sẽ dùng topological sort để chia task thành các
      "batch" và chạy song song trong từng batch.
"""

from pydantic import BaseModel, Field, field_validator

class Task(BaseModel):
    """Một task cụ thể trong Plan, sẽ được giao cho 1 Worker xử lý."""

    # ID duy nhất của task.
    # Ví dụ: task_01, task_02, task_03
    # ID này cực kỳ quan trọng khi fan-out worker + xác định dependency.
    id: str = Field(
        ...,
        description="ID duy nhất của task, ví dụ: 'task_01'",
    )

    # Tên task
    # Ví dụ: "Giải thích kiến trúc MCP"
    title: str = Field(
        ...,
        description="Tên ngắn gọn của task",
    )

    # Mô tả chi tiết task
    description: str = Field(
        ...,
        description="Mô tả chi tiết task phải làm gì",
    )

    # Mục tiêu của task.
    # Khác với description:
    #   description = task phải làm gì
    #   objective   = task cần đạt được điều gì
    objective: str = Field(
        ...,
        description="Mục tiêu cụ thể mà task cần đạt được",
    )

    # Task có cần research hay không.
    # Đây là quyết định ở cấp Planner, nhưng Worker vẫn có thể
    # tự quyết định thêm khi thực thi.
    requires_research: bool = Field(
        default=False,
        description="True nếu task cần research thông tin bên ngoài",
    )

    # Nếu requires_research = True thì Worker có thể dùng các query này.
    research_queries: list[str] = Field(
        default_factory=list,
        description="Danh sách query gợi ý để research (nếu cần)",
    )

    # Mô tả output mà Worker phải tạo ra.
    # Ví dụ: "Một section khoảng 500 từ, giải thích architecture của MCP."
    expected_output: str = Field(
        ...,
        description="Mô tả output mong muốn của task",
    )

    # ==========================================================
    # TASK DEPENDENCY (DAG)
    # ==========================================================
    #
    # Danh sách ID của các task khác mà task này phụ thuộc vào.
    #
    # Ví dụ:
    #   task_02.depends_on = ["task_01"]
    #   → task_02 chỉ chạy sau khi task_01 hoàn thành.
    #
    # Nếu để rỗng [] → task độc lập, có thể chạy song song
    # ngay từ đầu cùng các task độc lập khác.
    # ==========================================================
    depends_on: list[str] = Field(
        default_factory=list,
        description="Danh sách task_id mà task này phụ thuộc vào",
    )

    # Thứ tự ưu tiên hiển thị trong bài viết cuối cùng (dùng cho Synthesizer
    # sắp xếp section theo đúng trình tự logic, không phải thứ tự chạy xong).
    order: int = Field(
        default=0,
        description="Thứ tự hiển thị của section này trong bài viết cuối cùng",
    )

    @field_validator("depends_on")
    @classmethod
    def no_self_dependency(cls, v: list[str], info) -> list[str]:
        """Một task không được phép tự phụ thuộc vào chính nó."""
        task_id = info.data.get("id")
        if task_id and task_id in v:
            raise ValueError(f"Task '{task_id}' không thể tự phụ thuộc vào chính nó")
        return v


class Plan(BaseModel):
    """Bản kế hoạch tổng thể cho bài viết, do Planner tạo ra."""

    # Tên bài viết cuối cùng
    title: str = Field(
        ...,
        description="Tiêu đề bài viết",
    )

    # Mục tiêu tổng thể của bài
    objective: str = Field(
        ...,
        description="Mục tiêu tổng thể của bài viết",
    )

    # Đối tượng độc giả
    target_audience: str = Field(
        ...,
        description="Đối tượng độc giả của bài viết",
    )

    # Văn phong
    tone: str = Field(
        ...,
        description="Văn phong của bài viết",
    )

    # Danh sách task.
    # Đây chính là dữ liệu được dùng để fan-out (giới hạn 3-7 tasks).
    tasks: list[Task] = Field(
        ...,
        min_length=3,
        max_length=7,
        description="Danh sách task (3-7 tasks)",
    )

    # Số section dự kiến.
    # Đây chỉ là metadata, không nhất thiết phải bằng len(tasks).
    estimated_sections: int = Field(
        default=0,
        description="Số section dự kiến trong bài viết",
    )

    @field_validator("tasks")
    @classmethod
    def validate_dependencies_exist(cls, tasks: list[Task]) -> list[Task]:
        """
        Đảm bảo mọi task_id trong depends_on đều thực sự tồn tại
        trong danh sách tasks. Tránh trường hợp Planner (LLM) hallucinate
        ra một task_id không có thật.
        """
        valid_ids = {task.id for task in tasks}
        for task in tasks:
            for dep_id in task.depends_on:
                if dep_id not in valid_ids:
                    raise ValueError(
                        f"Task '{task.id}' phụ thuộc vào '{dep_id}' "
                        f"nhưng task này không tồn tại trong plan"
                    )
        return tasks

    @field_validator("tasks")
    @classmethod
    def validate_no_cycle(cls, tasks: list[Task]) -> list[Task]:
        """
        Đảm bảo dependency graph không có chu trình (cycle).
        Nếu có cycle → không thể topological sort được → Executor sẽ deadlock.

        Dùng thuật toán DFS đơn giản để phát hiện cycle.
        """
        graph = {task.id: task.depends_on for task in tasks}

        WHITE, GRAY, BLACK = 0, 1, 2
        state = {task_id: WHITE for task_id in graph}

        def dfs(node: str) -> bool:
            state[node] = GRAY
            for neighbor in graph.get(node, []):
                if state.get(neighbor) == GRAY:
                    return True  # phát hiện cycle
                if state.get(neighbor) == WHITE and dfs(neighbor):
                    return True
            state[node] = BLACK
            return False

        for task_id in graph:
            if state[task_id] == WHITE:
                if dfs(task_id):
                    raise ValueError(
                        "Phát hiện dependency cycle trong plan. "
                        "Vui lòng kiểm tra lại trường 'depends_on' của các task."
                    )
        return tasks