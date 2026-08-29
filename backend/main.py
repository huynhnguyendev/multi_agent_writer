"""
FastAPI application - entry point của backend/.

Khởi tạo app, cấu hình CORS (cho phép frontend dev ở port khác gọi
được, không cần Auth theo yêu cầu đã chốt), đăng ký routes + error
handlers, và chạy init_db() khi app khởi động (tạo bảng
workflow_runs/workflow_tasks nếu chưa có, idempotent).
"""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Fix cho Windows: lặp lại phòng thủ giống các file khác trong project
# (psycopg async mode không tương thích ProactorEventLoop mặc định).
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from agents.db.connection import close_engine, init_db
from backend.middleware import register_error_handlers
from backend.routes import workflow_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Chạy khi app khởi động / tắt (thay cho @app.on_event đã deprecated)."""
    await init_db()
    yield
    await close_engine()


app = FastAPI(
    title="Multi-Agent Writer API",
    description="API cho hệ thống viết bài blog tự động bằng multi-agent (LangGraph).",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: mở cho tất cả origin vì đây là tool cá nhân/nội bộ, không cần Auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(workflow_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Endpoint kiểm tra server còn sống - hữu ích cho FE/monitoring."""
    return {"status": "ok"}