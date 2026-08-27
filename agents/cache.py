"""
Caching layer cho kết quả gọi các external tool (Tavily, Wikimedia),
theo đúng thiết kế đã chốt:

    Cache key : SHA-256(provider + tham số request đã canonical hóa)
    TTL       : Tavily -> 24h, Wikimedia -> 7d
    Backend   : PostgreSQL (dùng chung DATABASE_URL với checkpoint)

Cách dùng (sẽ tích hợp vào tavily_search.py / wikimedia_images.py):

    from agents.cache import get_cached, set_cached, TAVILY_TTL_SECONDS

    key_params = {"query": query, "max_results": max_results}
    cached = await get_cached("tavily", key_params)
    if cached is not None:
        return ResearchResult(**cached)

    result = await _do_real_tavily_call(...)
    await set_cached("tavily", key_params, result.model_dump(), TAVILY_TTL_SECONDS)
    return result
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool

# Fix cho Windows: psycopg (async mode) không tương thích với
# ProactorEventLoop mặc định của Windows, cần chuyển sang
# SelectorEventLoop. Giống hệt fix đã áp dụng ở graph.py - cần lặp lại
# ở đây vì file này có thể được chạy độc lập (python -m agents.cache).
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# TTL (giây) theo đúng yêu cầu đã chốt.
TAVILY_TTL_SECONDS = 24 * 60 * 60       # 24h
WIKIMEDIA_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 ngày

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_cache (
    key VARCHAR(64) PRIMARY KEY,
    value JSONB NOT NULL,
    provider VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    ttl_seconds INT NOT NULL
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_agent_cache_expires
    ON agent_cache (expires_at);
"""

# Singleton connection pool - tránh mở connection mới mỗi lần gọi cache.
_pool: AsyncConnectionPool | None = None
_table_ready = False


async def _get_pool() -> AsyncConnectionPool:
    """Trả về singleton connection pool, mở lazy ở lần gọi đầu tiên."""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(DATABASE_URL, open=False)
        await _pool.open()
    return _pool


async def _ensure_table() -> None:
    """Tạo bảng agent_cache nếu chưa có (idempotent), chỉ chạy 1 lần/process."""
    global _table_ready
    if _table_ready:
        return

    pool = await _get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_CREATE_TABLE_SQL)
            await cur.execute(_CREATE_INDEX_SQL)
        await conn.commit()

    _table_ready = True


def build_cache_key(provider: str, params: dict) -> str:
    """
    Sinh cache key = SHA-256(provider + tham số đã canonical hóa).

    Canonical hóa bằng cách sort_keys=True khi dump JSON, đảm bảo
    {"query": "a", "limit": 5} và {"limit": 5, "query": "a"} luôn ra
    cùng 1 key (thứ tự key trong dict không ảnh hưởng).
    """
    canonical = json.dumps(params, sort_keys=True, ensure_ascii=True)
    raw = f"{provider}::{canonical}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def get_cached(provider: str, params: dict) -> dict | None:
    """
    Lấy giá trị đã cache cho (provider, params), None nếu cache miss
    hoặc đã hết hạn (expired record được coi như miss, KHÔNG tự xóa
    ngay tại đây để giữ hàm get đơn giản - dọn dẹp record hết hạn do
    hàm riêng `purge_expired()` đảm nhiệm).
    """
    await _ensure_table()
    key = build_cache_key(provider, params)

    pool = await _get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT value, expires_at FROM agent_cache WHERE key = %s",
                (key,),
            )
            row = await cur.fetchone()

    if row is None:
        return None

    value, expires_at = row
    if expires_at < datetime.now(timezone.utc):
        return None  # đã hết hạn, coi như cache miss

    return value


async def set_cached(provider: str, params: dict, value: dict, ttl_seconds: int) -> None:
    """
    Lưu (hoặc ghi đè) giá trị vào cache cho (provider, params), với
    TTL tính bằng giây kể từ thời điểm gọi.
    """
    await _ensure_table()
    key = build_cache_key(provider, params)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    pool = await _get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO agent_cache (key, value, provider, expires_at, ttl_seconds)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    created_at = NOW(),
                    expires_at = EXCLUDED.expires_at,
                    ttl_seconds = EXCLUDED.ttl_seconds
                """,
                (key, json.dumps(value), provider, expires_at, ttl_seconds),
            )
        await conn.commit()


async def purge_expired() -> int:
    """
    Xóa toàn bộ record đã hết hạn khỏi bảng cache. Trả về số dòng đã xóa.

    Hàm này không tự động chạy - có thể gọi định kỳ (cron job, hoặc
    thủ công) để dọn dẹp bảng, tránh phình to vô hạn theo thời gian.
    """
    await _ensure_table()

    pool = await _get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM agent_cache WHERE expires_at < NOW()"
            )
            deleted = cur.rowcount
        await conn.commit()

    return deleted


async def close_pool() -> None:
    """Đóng connection pool (dùng khi cần shutdown sạch, ví dụ trong test)."""
    global _pool, _table_ready
    if _pool is not None:
        await _pool.close()
        _pool = None
        _table_ready = False


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Cache Layer
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.cache
# ============================================================

# if __name__ == "__main__":
#     import asyncio

#     async def _debug():
#         print("=" * 60)
#         print("DEBUG: Test Cache Layer")
#         print("=" * 60)

#         provider = "tavily"
#         params = {"query": "Model Context Protocol", "max_results": 5}
#         fake_value = {"query": "Model Context Protocol", "sources": ["fake source 1", "fake source 2"]}

#         # --- Test 1: Cache miss ban đầu ---
#         print("\n### TEST 1: Cache miss ban đầu ###")
#         result = await get_cached(provider, params)
#         assert result is None, "❌ Lẽ ra phải là cache miss (chưa từng set)!"
#         print("✅ Cache miss đúng như kỳ vọng (chưa từng lưu).")

#         # --- Test 2: Set rồi get lại ngay, phải ra đúng giá trị ---
#         print("\n### TEST 2: Set cache rồi get lại ###")
#         await set_cached(provider, params, fake_value, ttl_seconds=60)
#         result = await get_cached(provider, params)
#         assert result == fake_value, f"❌ Giá trị lấy ra không khớp: {result}"
#         print(f"✅ Cache hit đúng, giá trị: {result}")

#         # --- Test 3: Cache key phải giống nhau dù thứ tự key trong dict khác nhau ---
#         print("\n### TEST 3: Cache key ổn định dù đổi thứ tự key trong dict ###")
#         params_reordered = {"max_results": 5, "query": "Model Context Protocol"}
#         key_1 = build_cache_key(provider, params)
#         key_2 = build_cache_key(provider, params_reordered)
#         assert key_1 == key_2, "❌ Cache key khác nhau dù params giống hệt (chỉ đổi thứ tự)!"
#         print(f"✅ Cache key ổn định: {key_1[:16]}...")

#         # --- Test 4: TTL hết hạn -> phải coi là cache miss ---
#         print("\n### TEST 4: TTL hết hạn (ttl_seconds=0) ###")
#         expired_params = {"query": "expired test case"}
#         await set_cached(provider, expired_params, {"foo": "bar"}, ttl_seconds=0)
#         await asyncio.sleep(1)  # đợi 1s để chắc chắn đã qua thời điểm hết hạn
#         result = await get_cached(provider, expired_params)
#         assert result is None, "❌ Record đã hết hạn nhưng vẫn được coi là cache hit!"
#         print("✅ Record hết hạn được coi là cache miss đúng như kỳ vọng.")

#         # --- Test 5: purge_expired dọn dẹp record hết hạn ---
#         print("\n### TEST 5: purge_expired() ###")
#         deleted = await purge_expired()
#         print(f"✅ Đã xóa {deleted} record hết hạn.")

#         await close_pool()
#         print("\n✅ Tất cả test pass!")

#     asyncio.run(_debug())