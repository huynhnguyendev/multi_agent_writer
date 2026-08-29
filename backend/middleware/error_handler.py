"""
Global exception handler cho FastAPI app.

Bắt các exception KHÔNG được xử lý ở tầng route (ví dụ lỗi kết nối DB
đột ngột, lỗi không lường trước từ agents/), trả về JSON lỗi chuẩn
thay vì raw HTML traceback 500 mặc định của Starlette - giúp FE luôn
nhận được response dạng JSON dễ xử lý.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("multi_agent_writer.backend")


def register_error_handlers(app: FastAPI) -> None:
    """Đăng ký exception handler dùng chung cho toàn bộ app."""

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Lỗi không xử lý được tại %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Đã xảy ra lỗi hệ thống không mong muốn.",
                "error": str(exc),
            },
        )