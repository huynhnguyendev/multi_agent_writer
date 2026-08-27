"""
Xử lý dependency graph (DAG) của các Task trong Plan.

Trách nhiệm:
    1. Chia danh sách Task thành các "batch" theo topological sort,
       để Executor biết batch nào chạy trước, batch nào chạy song song.
    2. Lấy context (nội dung) của các task mà 1 task cụ thể phụ thuộc,
       dựa trên danh sách WorkerOutput đã hoàn thành.

Lưu ý: Plan schema đã validate không có cycle và không có depends_on
trỏ tới task_id không tồn tại (xem agents/schemas/plan.py), nên ở đây
không cần validate lại, chỉ cần thực hiện thuật toán Kahn's algorithm
thuần túy.
"""

from agents.schemas.plan import Task
from agents.schemas.worker import WorkerOutput


def build_execution_batches(tasks: list[Task]) -> list[list[Task]]:
    """
    Chia danh sách task thành các batch theo topological sort
    (thuật toán Kahn's algorithm).

    Mỗi batch là danh sách các task có thể chạy SONG SONG với nhau
    (vì tất cả dependency của chúng đã nằm ở batch trước).

    Ví dụ với plan thực tế đã test ở Planner:
        task_01 (không phụ thuộc)
        task_02 (phụ thuộc task_01)
        task_03 (phụ thuộc task_02)
        task_04 (phụ thuộc task_02)
        task_05 (phụ thuộc task_03, task_04)

    Kết quả:
        Batch 1: [task_01]
        Batch 2: [task_02]
        Batch 3: [task_03, task_04]
        Batch 4: [task_05]
    """
    tasks_by_id = {task.id: task for task in tasks}

    # in_degree[task_id] = số lượng dependency CHƯA được xử lý
    in_degree: dict[str, int] = {task.id: len(task.depends_on) for task in tasks}

    # dependents[task_id] = danh sách các task_id phụ thuộc vào task_id này
    # (dùng để giảm in_degree của "con" khi "cha" đã được xử lý xong)
    dependents: dict[str, list[str]] = {task.id: [] for task in tasks}
    for task in tasks:
        for dep_id in task.depends_on:
            dependents[dep_id].append(task.id)

    batches: list[list[Task]] = []
    remaining = set(tasks_by_id.keys())

    while remaining:
        # Batch hiện tại = tất cả task còn lại có in_degree == 0
        current_batch_ids = [
            task_id for task_id in remaining if in_degree[task_id] == 0
        ]

        if not current_batch_ids:
            # Không thể xảy ra vì Plan đã validate no-cycle, nhưng giữ
            # lại safety check để tránh vòng lặp vô hạn nếu có bug.
            raise RuntimeError(
                "Không thể tiếp tục topological sort - có thể tồn tại "
                "cycle chưa được phát hiện. Task còn lại: "
                f"{remaining}"
            )

        batches.append([tasks_by_id[task_id] for task_id in current_batch_ids])

        for task_id in current_batch_ids:
            remaining.remove(task_id)
            for child_id in dependents[task_id]:
                in_degree[child_id] -= 1

    return batches


def get_dependency_context(
    task: Task,
    completed_outputs: list[WorkerOutput],
) -> list[dict]:
    """
    Lấy nội dung (title + content) của các task mà `task` phụ thuộc,
    dựa trên danh sách WorkerOutput đã hoàn thành ở các batch trước.

    Trả về list[dict] dạng [{"title": ..., "content": ...}, ...] để
    render trực tiếp vào biến `dependency_context` trong worker.yaml.

    Nếu 1 dependency bị lỗi (success=False), BỎ QUA nó khỏi context
    (theo chiến lược "bỏ qua và log lỗi") thay vì đưa content rỗng/lỗi
    vào prompt gây nhiễu cho Worker con.
    """
    if not task.depends_on:
        return []

    outputs_by_task_id = {
        output.task_id: output
        for output in completed_outputs
        if output.success
    }

    context = []
    for dep_id in task.depends_on:
        dep_output = outputs_by_task_id.get(dep_id)
        if dep_output is not None:
            context.append({"title": dep_output.title, "content": dep_output.content})

    return context


# ============================================================
# DEBUG - Chạy trực tiếp file này để test thuật toán batching
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.executor.task_manager
# ============================================================

if __name__ == "__main__":

    def _make_task(task_id: str, depends_on: list[str] | None = None) -> Task:
        return Task(
            id=task_id,
            title=f"Task {task_id}",
            description="mô tả test",
            objective="mục tiêu test",
            expected_output="output test",
            depends_on=depends_on or [],
        )

    print("=" * 60)
    print("DEBUG: Test build_execution_batches")
    print("=" * 60)

    # Case 1: giống hệt plan thực tế đã test ở Planner
    tasks_case_1 = [
        _make_task("task_01"),
        _make_task("task_02", ["task_01"]),
        _make_task("task_03", ["task_02"]),
        _make_task("task_04", ["task_02"]),
        _make_task("task_05", ["task_03", "task_04"]),
    ]

    print("\n--- Case 1: DAG nhiều tầng (giống plan thực tế) ---")
    batches = build_execution_batches(tasks_case_1)
    for i, batch in enumerate(batches, start=1):
        print(f"Batch {i}: {[t.id for t in batch]}")

    # Case 2: tất cả độc lập -> phải ra đúng 1 batch duy nhất chứa hết
    tasks_case_2 = [_make_task(f"task_0{i}") for i in range(1, 6)]
    print("\n--- Case 2: Tất cả task độc lập ---")
    batches = build_execution_batches(tasks_case_2)
    for i, batch in enumerate(batches, start=1):
        print(f"Batch {i}: {[t.id for t in batch]}")
    assert len(batches) == 1 and len(batches[0]) == 5, "❌ Case 2 sai!"
    print("✅ Case 2 đúng: chỉ có 1 batch chứa cả 5 task.")

    # Case 3: chuỗi tuần tự hoàn toàn -> mỗi batch chỉ có 1 task
    tasks_case_3 = [
        _make_task("task_01"),
        _make_task("task_02", ["task_01"]),
        _make_task("task_03", ["task_02"]),
    ]
    print("\n--- Case 3: Chuỗi tuần tự (mỗi batch 1 task) ---")
    batches = build_execution_batches(tasks_case_3)
    for i, batch in enumerate(batches, start=1):
        print(f"Batch {i}: {[t.id for t in batch]}")
    assert len(batches) == 3, "❌ Case 3 sai!"
    print("✅ Case 3 đúng: 3 batch riêng biệt.")

    # Test get_dependency_context
    print("\n" + "=" * 60)
    print("DEBUG: Test get_dependency_context")
    print("=" * 60)

    fake_outputs = [
        WorkerOutput(task_id="task_01", title="Giới thiệu", content="Nội dung task 1...", success=True),
        WorkerOutput(task_id="task_02", title="Kiến trúc", content="Nội dung task 2...", success=False, error="LLM timeout"),
    ]

    task_05 = _make_task("task_05", ["task_01", "task_02"])
    context = get_dependency_context(task_05, fake_outputs)

    print(f"\nDependency context cho task_05 (task_02 bị lỗi, phải bị bỏ qua):")
    for item in context:
        print(f"  - {item['title']}: {item['content'][:50]}...")

    assert len(context) == 1 and context[0]["title"] == "Giới thiệu", "❌ Lỗi filter task thất bại!"
    print("\n✅ Đúng: chỉ lấy được context của task_01 (thành công), bỏ qua task_02 (lỗi).")