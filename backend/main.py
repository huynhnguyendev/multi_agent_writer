"""
FastAPI application - entry point của backend/.

Khởi tạo app, cấu hình CORS (cho phép frontend dev ở port khác gọi
được, không cần Auth theo yêu cầu đã chốt), đăng ký routes + error
handlers, và chạy init_db() khi app khởi động (tạo bảng
workflow_runs/workflow_tasks nếu chưa có, idempotent).
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from agents.db.connection import close_engine, init_db
from backend.middleware import register_error_handlers
from backend.routes import workflow_router

BASE_DIR = Path(__file__).resolve().parent.parent  # root project (multi_agent_writer/)
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_engine()


app = FastAPI(
    title="Multi-Agent Writer API",
    description="API cho hệ thống viết bài blog tự động bằng multi-agent (LangGraph).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(workflow_router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", tags=["frontend"])
async def serve_index(request: Request):
    """Trả về giao diện chính - frontend gọi API cùng origin, không cần CORS phức tạp."""
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok"}