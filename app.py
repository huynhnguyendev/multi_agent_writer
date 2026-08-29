"""
Entry point chạy toàn bộ dự án Multi-Agent Writer.

Chạy file này để khởi động backend API server:
    python app.py

Server sẽ chạy tại http://127.0.0.1:8000
Swagger UI (test API trực tiếp trên trình duyệt): http://127.0.0.1:8000/docs
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )