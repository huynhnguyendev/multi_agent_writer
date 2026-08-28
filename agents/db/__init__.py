"""
Export API của agents/db/ để tiện import từ 1 chỗ duy nhất.

Thay vì:
    from agents.db.connection import get_session, init_db
    from agents.db.models import WorkflowRun, WorkflowTask
    from agents.db.progress_tracker import create_workflow_run, ...

Có thể viết gọn:
    from agents.db import get_session, WorkflowRun, create_workflow_run
"""

from agents.db.connection import close_engine, get_session, init_db
from agents.db.models import (
    TASK_STATUSES,
    WORKFLOW_STATUSES,
    Base,
    WorkflowRun,
    WorkflowTask,
)
from agents.db.progress_tracker import (
    NODE_PROGRESS,
    create_workflow_run,
    get_workflow_with_tasks,
    update_workflow_run,
    upsert_task,
)

__all__ = [
    # connection
    "get_session",
    "init_db",
    "close_engine",
    # models
    "Base",
    "WorkflowRun",
    "WorkflowTask",
    "WORKFLOW_STATUSES",
    "TASK_STATUSES",
    # progress_tracker
    "NODE_PROGRESS",
    "create_workflow_run",
    "update_workflow_run",
    "upsert_task",
    "get_workflow_with_tasks",
]