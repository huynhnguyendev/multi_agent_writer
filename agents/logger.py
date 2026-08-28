"""
Logging layer cho toàn bộ project - ghi log ra cả console lẫn file,
theo đúng yêu cầu đã chốt:

    - Mỗi node đi qua đều log lại (bắt đầu, kết thúc, kết quả tóm tắt).
    - Log ra file để debug sau, mỗi lần chạy workflow có 1 file riêng:
        logs/workflow_{workflow_id}_{timestamp}.log
    - Lỗi (WARNING/ERROR) luôn được gộp thêm vào 1 file chung:
        logs/errors.log
    - Log level:
        DEBUG - luồng thực hiện chi tiết
        INFO  - mốc quan trọng (chuyển node, quyết định)
        WARN  - lỗi không quan trọng (API retry, fallback)
        ERROR - lỗi quan trọng (dừng workflow)

Cách dùng (trong 1 node function ở graph.py, ví dụ):

    from agents.logger import get_workflow_logger, log_node_start, log_node_end

    logger = get_workflow_logger(state["workflow_id"])
    log_node_start(logger, "planner")
    ...
    log_node_end(logger, "planner", {"tasks": len(plan.tasks)})

Cách dùng cho log lỗi chung (không gắn với 1 workflow cụ thể), ví dụ
trong agents/tools/*.py:

    from agents.logger import get_logger

    logger = get_logger(__name__)
    logger.warning("Lỗi khi gọi Tavily: %s", e)
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"

ROOT_LOGGER_NAME = "multi_agent_writer"

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_errors_handler_attached = False
_workflow_loggers: dict[str, logging.Logger] = {}


def _ensure_logs_dir() -> Path:
    """
    Đảm bảo thư mục logs/ tồn tại ở root project.

    Chỉ log dòng thông báo ở lần đầu tiên tạo mới (tương tự cách
    outputs/ được tạo ở synthesizer.py), nếu đã có sẵn thì bỏ qua.
    """
    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"📁 [logger] Lần đầu tạo thư mục logs/ tại: {LOGS_DIR}")
    return LOGS_DIR


def _get_root_logger() -> logging.Logger:
    """
    Lấy (và cấu hình lần đầu) root logger dùng chung cho cả project.

    Root logger có sẵn 1 console handler (INFO+) và 1 file handler
    errors.log (WARNING+) - mọi child logger (get_logger, workflow
    logger) đều tự động propagate log lên đây, nên KHÔNG cần tự thêm
    console/error handler riêng ở từng nơi gọi.
    """
    global _errors_handler_attached

    logger = logging.getLogger(ROOT_LOGGER_NAME)

    if not _errors_handler_attached:
        logger.setLevel(logging.DEBUG)
        _ensure_logs_dir()

        formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        errors_handler = logging.FileHandler(LOGS_DIR / "errors.log", encoding="utf-8")
        errors_handler.setLevel(logging.WARNING)
        errors_handler.setFormatter(formatter)
        logger.addHandler(errors_handler)

        _errors_handler_attached = True

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Lấy 1 logger con (child logger) gắn dưới root logger của project.

    Dùng cho các module KHÔNG gắn liền với 1 workflow_id cụ thể (ví dụ
    agents/tools/*.py, agents/cache.py) - log của chúng vẫn tự động đi
    ra console + errors.log (nếu >= WARNING) thông qua propagation,
    không cần setup gì thêm.
    """
    _get_root_logger()  # đảm bảo root logger đã setup console + errors.log
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def get_workflow_logger(workflow_id: str) -> logging.Logger:
    """
    Lấy (hoặc tạo mới) logger riêng cho 1 lần chạy workflow cụ thể.

    Logger này có thêm 1 file handler riêng (DEBUG+) ghi vào:
        logs/workflow_{workflow_id}_{timestamp}.log

    File chỉ được tạo 1 LẦN cho mỗi workflow_id trong suốt vòng đời
    process (cache lại trong _workflow_loggers), tránh tạo nhiều file
    trùng lặp nếu gọi hàm này nhiều lần cho cùng 1 workflow.

    Log vẫn tự động propagate lên root logger (console + errors.log),
    nên gọi hàm này là đủ, không cần gọi thêm get_logger().
    """
    if workflow_id in _workflow_loggers:
        return _workflow_loggers[workflow_id]

    _get_root_logger()  # đảm bảo root logger đã setup
    _ensure_logs_dir()

    logger = logging.getLogger(f"{ROOT_LOGGER_NAME}.workflow.{workflow_id}")
    logger.setLevel(logging.DEBUG)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = LOGS_DIR / f"workflow_{workflow_id}_{timestamp}.log"

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    file_handler = logging.FileHandler(filepath, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _workflow_loggers[workflow_id] = logger
    logger.info("=== Bắt đầu workflow %s, log file: %s ===", workflow_id, filepath.name)

    return logger


def log_node_start(logger: logging.Logger, node_name: str, **context) -> None:
    """
    Log thời điểm bắt đầu 1 node, kèm context tóm tắt (key=value).

    Ví dụ:
        log_node_start(logger, "planner", plan_revision_count=0)
        -> "[planner] BẮT ĐẦU | plan_revision_count=0"
    """
    ctx_str = " | ".join(f"{k}={v}" for k, v in context.items())
    suffix = f" | {ctx_str}" if ctx_str else ""
    logger.info("[%s] BẮT ĐẦU%s", node_name, suffix)


def log_node_end(logger: logging.Logger, node_name: str, **context) -> None:
    """
    Log thời điểm kết thúc 1 node, kèm context tóm tắt kết quả.

    Ví dụ:
        log_node_end(logger, "planner", tasks=5, title="MCP cho AI Engineer")
        -> "[planner] KẾT THÚC | tasks=5 | title=MCP cho AI Engineer"
    """
    ctx_str = " | ".join(f"{k}={v}" for k, v in context.items())
    suffix = f" | {ctx_str}" if ctx_str else ""
    logger.info("[%s] KẾT THÚC%s", node_name, suffix)


def log_node_error(logger: logging.Logger, node_name: str, error: Exception | str) -> None:
    """Log lỗi xảy ra trong 1 node (ghi vào cả file workflow lẫn errors.log)."""
    logger.error("[%s] LỖI | %s", node_name, error)


# ============================================================
# DEBUG - Chạy trực tiếp file này để test Logger
# ============================================================
#
# Cách chạy (đứng ở thư mục root của project multi_agent_writer/):
#   python -m agents.logger
# ============================================================

# if __name__ == "__main__":
#     import time

#     print("=" * 60)
#     print("DEBUG: Test Logger")
#     print("=" * 60)

#     # --- Test 1: get_logger (module-level, không gắn workflow) ---
#     print("\n### TEST 1: get_logger (module-level) ###")
#     module_logger = get_logger("tools.tavily_search")
#     module_logger.debug("Đây là dòng DEBUG (không hiện ở console vì console level=INFO)")
#     module_logger.info("Đây là dòng INFO (hiện ở console)")
#     module_logger.warning("Đây là dòng WARNING (hiện ở console + errors.log)")

#     # --- Test 2: get_workflow_logger + log_node_start/end ---
#     print("\n### TEST 2: Workflow logger + log_node_start/end ###")
#     fake_workflow_id = "debug-test-001"
#     wf_logger = get_workflow_logger(fake_workflow_id)

#     log_node_start(wf_logger, "guardrail")
#     time.sleep(0.2)
#     log_node_end(wf_logger, "guardrail", is_valid=True)

#     log_node_start(wf_logger, "planner", plan_revision_count=0)
#     time.sleep(0.2)
#     log_node_end(wf_logger, "planner", tasks=5, title="Test Plan")

#     log_node_error(wf_logger, "executor", "Rate limit reached, retrying...")

#     # --- Test 3: gọi lại get_workflow_logger với CÙNG workflow_id -> không tạo file mới ---
#     print("\n### TEST 3: Gọi lại cùng workflow_id (không tạo file trùng) ###")
#     wf_logger_again = get_workflow_logger(fake_workflow_id)
#     assert wf_logger_again is wf_logger, "❌ Phải trả về CÙNG instance logger, không tạo mới!"
#     print("✅ Đúng: cùng workflow_id trả về cùng 1 logger instance (không tạo file trùng).")

#     # --- Kiểm tra file thực sự đã được tạo ---
#     log_files = list(LOGS_DIR.glob(f"workflow_{fake_workflow_id}_*.log"))
#     assert len(log_files) == 1, f"❌ Kỳ vọng đúng 1 file log, tìm thấy {len(log_files)}!"
#     print(f"✅ File log đã tạo: {log_files[0].name}")

#     errors_log = LOGS_DIR / "errors.log"
#     assert errors_log.exists(), "❌ errors.log chưa được tạo!"
#     print(f"✅ errors.log tồn tại tại: {errors_log}")

#     print("\n✅ Tất cả test pass! Kiểm tra nội dung file log để xác nhận format.")