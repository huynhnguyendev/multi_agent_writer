"""
Kết nối SQLAlchemy (async) tới PostgreSQL, dùng chung DATABASE_URL với
checkpoint (AsyncPostgresSaver) và cache (agents/cache.py).

2 bảng workflow_runs / workflow_tasks (định nghĩa ở models.py) sẽ dùng
chung engine/session từ file này, tách biệt hoàn toàn với bảng
checkpoint nội bộ của LangGraph (do AsyncPostgresSaver tự quản lý) và
bảng agent_cache (do psycopg_pool tự quản lý ở cache.py) - không đụng
độ tên bảng vì mỗi bên tạo bảng riêng.

Cách dùng (trong agents/db/progress_tracker.py sau này):

    from agents.db.connection import get_session

    async with get_session() as session:
        session.add(WorkflowRun(...))
        await session.commit()
"""

import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Fix cho Windows: driver async (psycopg/asyncpg) không tương thích với
# ProactorEventLoop mặc định của Windows, cần chuyển sang SelectorEventLoop.
# Lặp lại fix này vì file có thể chạy độc lập (python -m agents.db.connection).
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

_RAW_DATABASE_URL = os.getenv("DATABASE_URL", "")

if not _RAW_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL chưa được set trong file .env. "
        "Vui lòng kiểm tra lại trước khi dùng agents/db."
    )


def _to_async_sqlalchemy_url(url: str) -> str:
    """
    Chuyển DATABASE_URL dạng "postgresql://..." (đang dùng cho psycopg
    ở checkpoint/cache) sang dạng SQLAlchemy async: "postgresql+psycopg://...".

    Dùng driver psycopg (đã cài sẵn cho AsyncPostgresSaver/cache.py) thay
    vì asyncpg, để không phải cài thêm dependency mới, và đồng bộ driver
    dùng xuyên suốt cả project.
    """
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


ASYNC_DATABASE_URL = _to_async_sqlalchemy_url(_RAW_DATABASE_URL)

# echo=False mặc định (không log SQL ra console). pool_pre_ping kiểm
# tra connection còn sống trước khi dùng, pool_recycle chủ động tái
# tạo connection sau mỗi 280s (dưới ngưỡng timeout phổ biến của nhiều
# Postgres server/managed provider) để tránh dùng phải connection đã
# bị server/OS âm thầm đóng do idle quá lâu.
_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=280,
)

_session_factory = async_sessionmaker(
    bind=_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@asynccontextmanager
async def get_session():
    """
    Context manager cấp 1 AsyncSession dùng cho 1 đơn vị công việc
    (unit of work). Tự rollback nếu có exception, không tự commit -
    caller chịu trách nhiệm gọi `await session.commit()` khi cần.

    Nếu gặp lỗi mất kết nối (OperationalError - connection đã bị
    server/OS đóng do idle), tự động dispose pool cũ và thử lại 1 lần
    với connection mới, trước khi để lỗi propagate ra ngoài.

    Cách dùng:
        async with get_session() as session:
            session.add(obj)
            await session.commit()
    """
    from sqlalchemy.exc import OperationalError

    try:
        async with _session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
    except OperationalError as e:
        print(f"⚠️  [db] Mất kết nối DB ({e}), đang thử tái kết nối...")
        await _engine.dispose()

        async with _session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise


async def init_db() -> None:
    """
    Tạo toàn bộ bảng đã khai báo trong agents/db/models.py (nếu chưa có).

    Idempotent - gọi nhiều lần không sao (CREATE TABLE IF NOT EXISTS
    ngầm định qua checkfirst=True mặc định của SQLAlchemy metadata.create_all).
    """
    from agents.db.models import Base  # import trễ để tránh circular import

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_engine() -> None:
    """Đóng engine (dùng khi cần shutdown sạch, ví dụ trong test)."""
    await _engine.dispose()


# ============================================================
# DEBUG - Chạy trực tiếp file này để test kết nối DB
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.db.connection
# ============================================================

# if __name__ == "__main__":
#     import asyncio

#     from sqlalchemy import text

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test kết nối Database")
#         print("=" * 60)
#         print(f"ASYNC_DATABASE_URL (đã ẩn password): "
#               f"{ASYNC_DATABASE_URL.split('@')[-1] if '@' in ASYNC_DATABASE_URL else ASYNC_DATABASE_URL}")

#         try:
#             async with get_session() as session:
#                 result = await session.execute(text("SELECT 1"))
#                 value = result.scalar()
#                 assert value == 1, "❌ Query test thất bại!"
#                 print("\n✅ Kết nối DB thành công (SELECT 1 trả về đúng giá trị).")
#         except Exception as e:
#             print(f"\n❌ Lỗi kết nối DB: {e}")
#             return

#         await close_engine()
#         print("✅ Đóng engine thành công.")

#     asyncio.run(_debug())