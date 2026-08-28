"""
SQLAlchemy models cho lớp metadata phục vụ UI/API (KHÔNG phải bảng
checkpoint của LangGraph - bảng đó do AsyncPostgresSaver tự quản lý
riêng, xem agents/graph.py).

2 bảng:
    workflow_runs  - 1 dòng / 1 lần chạy workflow, theo dõi trạng thái
                      tổng thể + tiến trình % để hiển thị thanh progress
                      bar chính trên UI.
    workflow_tasks - N dòng / 1 workflow, mỗi dòng ứng với 1 task trong
                      Plan, theo dõi trạng thái + tiến trình riêng từng
                      task khi Executor chạy song song.

Cách dùng (ở agents/db/progress_tracker.py sau này):

    from agents.db.models import WorkflowRun, WorkflowTask
    from agents.db.connection import get_session

    async with get_session() as session:
        session.add(WorkflowRun(workflow_id="...", topic="...", status="running"))
        await session.commit()
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload


class Base(DeclarativeBase):
    """Base class chung cho toàn bộ model trong agents/db/."""
    pass


def _utcnow() -> datetime:
    """Helper trả về thời gian hiện tại theo UTC (dùng làm default cho timestamp)."""
    return datetime.now(timezone.utc)


# ============================================================
# WORKFLOW STATUS - các giá trị hợp lệ cho WorkflowRun.status
# ============================================================
#
# pending    -> vừa tạo record, chưa bắt đầu chạy node nào
# running    -> đang chạy (guardrail/supervisor/planner/executor/...)
# waiting_hitl -> đang dừng ở node HITL, chờ user phản hồi
# blocked    -> bị chặn ở Input Guardrails (is_valid=False)
# completed  -> đã lưu output_markdown thành công (save_output xong)
# failed     -> lỗi không phục hồi được (planner/synthesizer fail hẳn)
# ============================================================

WORKFLOW_STATUSES = (
    "pending",
    "running",
    "waiting_hitl",
    "blocked",
    "completed",
    "failed",
)

# Các giá trị hợp lệ cho WorkflowTask.status - đơn giản hơn vì task
# không có khái niệm "waiting_hitl" hay "blocked".
TASK_STATUSES = ("pending", "running", "success", "failed")


class WorkflowRun(Base):
    """1 dòng / 1 lần chạy workflow - trạng thái tổng thể phục vụ UI."""

    __tablename__ = "workflow_runs"

    # Dùng CHÍNH workflow_id (UUID string) làm khóa chính, khớp với
    # thread_id đang dùng cho checkpoint LangGraph ở graph.py - giúp
    # tra cứu chéo dễ dàng giữa 2 hệ thống khi cần debug.
    workflow_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    topic: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # Node hiện tại đang chạy/vừa hoàn thành - hữu ích để UI biết đang
    # ở giai đoạn nào (guardrail, planner, executor, evaluator...).
    current_node: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Tiến trình tổng thể của TOÀN BỘ workflow (0-100), tính bằng code
    # dựa theo current_node (xem progress_tracker.py sau này).
    overall_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    plan_title: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tiến trình riêng của giai đoạn Planner<->HITL (0-100), ví dụ tăng
    # dần qua các lần plan bị reject rồi tạo lại, hoặc đơn giản là
    # 100 ngay khi HITL approve.
    plan_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    article_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Quan hệ 1-N tới WorkflowTask, cascade delete để xóa workflow thì
    # tự động xóa hết task con liên quan (tránh record mồ côi).
    tasks: Mapped[list["WorkflowTask"]] = relationship(
        back_populates="workflow_run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowRun(workflow_id={self.workflow_id!r}, "
            f"status={self.status!r}, overall_progress={self.overall_progress})>"
        )


class WorkflowTask(Base):
    """N dòng / 1 workflow - trạng thái riêng từng task trong Plan (do Executor chạy)."""

    __tablename__ = "workflow_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflow_runs.workflow_id", ondelete="CASCADE"), nullable=False
    )

    # task_id nội bộ trong Plan, ví dụ "task_01" - KHÔNG phải khóa
    # chính vì cùng 1 task_id có thể xuất hiện nhiều lần nếu sau này
    # muốn track lại lịch sử retry (hiện tại đơn giản là 1 dòng/task).
    task_id: Mapped[str] = mapped_column(String(20), nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # Tiến trình riêng của task này (0-100). Vì Worker hiện tại không
    # có bước con để báo tiến trình chi tiết (chỉ có running/success/
    # failed), giá trị thực tế sẽ là 0 (pending), 50 (running), 100
    # (success/failed) - đơn giản nhưng đủ để vẽ progress bar trên UI.
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="tasks")

    def __repr__(self) -> str:
        return (
            f"<WorkflowTask(task_id={self.task_id!r}, "
            f"status={self.status!r}, progress={self.progress})>"
        )


# ============================================================
# DEBUG - Chạy trực tiếp file này để test tạo bảng + CRUD cơ bản
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.db.models
# ============================================================

# if __name__ == "__main__":
#     import asyncio

#     from sqlalchemy import select

#     from agents.db.connection import close_engine, get_session, init_db

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test agents/db/models.py")
#         print("=" * 60)

#         print("\n### Bước 1: Tạo bảng (nếu chưa có) ###")
#         await init_db()
#         print("✅ init_db() chạy xong (workflow_runs + workflow_tasks đã sẵn sàng).")

#         fake_workflow_id = "debug-db-test-001"

#         print("\n### Bước 2: Tạo 1 WorkflowRun + 2 WorkflowTask ###")
#         async with get_session() as session:
#             # Xóa record cũ nếu có (để test lại nhiều lần không bị lỗi trùng PK)
#             existing = await session.get(WorkflowRun, fake_workflow_id)
#             if existing:
#                 await session.delete(existing)
#                 await session.commit()

#             run = WorkflowRun(
#                 workflow_id=fake_workflow_id,
#                 topic="MCP cho AI Engineer",
#                 status="running",
#                 current_node="executor",
#                 overall_progress=40,
#                 plan_title="Giải mã MCP",
#                 plan_progress=100,
#             )
#             run.tasks.append(WorkflowTask(task_id="task_01", title="Giới thiệu", status="success", progress=100))
#             run.tasks.append(WorkflowTask(task_id="task_02", title="Kiến trúc", status="running", progress=50))

#             session.add(run)
#             await session.commit()
#             print(f"✅ Đã tạo: {run}")

#         print("\n### Bước 3: Query lại, kiểm tra quan hệ tasks ###")
#         async with get_session() as session:
#             result = await session.execute(
#                 select(WorkflowRun)
#                 .options(selectinload(WorkflowRun.tasks))
#                 .where(WorkflowRun.workflow_id == fake_workflow_id)
#             )
#             fetched_run = result.scalar_one()

#             print(f"Fetched: {fetched_run}")
#             print(f"Số tasks: {len(fetched_run.tasks)}")
#             for t in fetched_run.tasks:
#                 print(f"  - {t}")

#             assert len(fetched_run.tasks) == 2, "❌ Số task không đúng!"
#             assert fetched_run.status == "running", "❌ Status không đúng!"
#             print("\n✅ Query + quan hệ 1-N hoạt động đúng.")

#         print("\n### Bước 4: Test cascade delete ###")
#         async with get_session() as session:
#             run_to_delete = await session.get(WorkflowRun, fake_workflow_id)
#             await session.delete(run_to_delete)
#             await session.commit()

#             result = await session.execute(
#                 select(WorkflowTask).where(WorkflowTask.workflow_id == fake_workflow_id)
#             )
#             remaining_tasks = result.scalars().all()
#             assert len(remaining_tasks) == 0, "❌ Cascade delete không hoạt động, task con vẫn còn!"
#             print("✅ Cascade delete đúng: xóa WorkflowRun tự xóa hết WorkflowTask con.")

#         await close_engine()
#         print("\n✅ Tất cả test pass!")

#     asyncio.run(_debug())