"""Export router chính để đăng ký vào FastAPI app (backend/main.py)."""

from backend.routes.workflow import router as workflow_router

__all__ = ["workflow_router"]