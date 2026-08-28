"""
Hook registry nhẹ để các agent (đặc biệt Worker) có thể "báo cáo"
tiến trình real-time ra bên ngoài, MÀ KHÔNG cần nhét callback function
vào WriterState (state phải serialize được để checkpoint, callback
thì không serialize được).

Cách hoạt động: bên ngoài (ví dụ backend/services/workflow_manager.py)
đăng ký 1 async callback gắn với workflow_id trước khi chạy graph.
agents/executor/worker.py chỉ cần gọi notify_task_update(workflow_id, ...)
mà không cần biết ai đang lắng nghe (nếu không ai đăng ký, gọi hàm này
là no-op, an toàn cho các trường hợp chạy debug/test độc lập không
qua workflow_manager).

Đây là in-memory registry (mất khi restart process) - phù hợp vì mục
đích chỉ là progress reporting real-time, không phải nguồn dữ liệu
authoritative (dữ liệu gốc vẫn nằm ở WriterState + checkpoint).
"""

from typing import Awaitable, Callable

TaskHook = Callable[[str, str, str, int, str | None], Awaitable[None]]
# Chữ ký: async def hook(task_id, title, status, progress, error) -> None

_task_hooks: dict[str, TaskHook] = {}


def register_task_hook(workflow_id: str, hook: TaskHook) -> None:
    """Đăng ký callback nhận thông báo tiến trình task cho 1 workflow_id."""
    _task_hooks[workflow_id] = hook


def unregister_task_hook(workflow_id: str) -> None:
    """Hủy đăng ký callback (gọi khi workflow chạy xong/dừng)."""
    _task_hooks.pop(workflow_id, None)


async def notify_task_update(
    workflow_id: str,
    task_id: str,
    title: str,
    status: str,
    progress: int,
    error: str | None = None,
) -> None:
    """
    Gọi hook đã đăng ký cho workflow_id (nếu có). No-op an toàn nếu
    không có ai đăng ký (ví dụ khi chạy python -m agents.executor.worker
    độc lập để debug, không qua workflow_manager).
    """
    hook = _task_hooks.get(workflow_id)
    if hook is not None:
        await hook(task_id, title, status, progress, error)