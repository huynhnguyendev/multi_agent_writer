# 📋 PROJECT PLAN: Multi-Agent Writer

> Tài liệu này mô tả kiến trúc THỰC TẾ của dự án tại thời điểm hiện tại
> (đã build xong `agents/`, `backend/`, giao diện `static/` + `templates/`),
> không còn là bản kế hoạch ban đầu nữa.

---

## 🎯 Tổng Quan

**Tên dự án**: Multi-Agent Writer

**Mục tiêu**: Hệ thống tự động viết bài blog chất lượng cao bằng kiến trúc multi-agent, có con người xác nhận kế hoạch (HITL), chạy song song theo dependency graph, tự đánh giá và tự sửa lại nếu chưa đạt điểm.

**Stack**: LangGraph, LangChain, FastAPI, PostgreSQL (checkpoint + cache + progress metadata), MCP (Tavily + Wikimedia), Vanilla JS/HTML/CSS (frontend).

---

## 📐 Kiến Trúc Tổng Thể

```text
┌─────────────────────────────────────────────────────────────┐
│         FRONTEND (static/ + templates/, dark theme)         │
│   Composer → Plan (HITL) → Tasks → Article, polling 3s      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                   REST API (cùng origin)
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    BACKEND (FastAPI)                         │
│  routes/workflow.py → services/workflow_manager.py          │
│  (chạy graph ở background task, xử lý interrupt/resume HITL, │
│   đồng bộ tiến trình real-time vào DB qua agents/hooks.py)   │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              AGENTS (LangGraph StateGraph)                  │
│                                                             │
│  guardrail → supervisor → planner ⇄ hitl(interrupt) →       │
│  executor(DAG song song) → image_resolver →                 │
│  synthesizer ⇄ evaluator → save_output                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Cấu Trúc Thư Mục Hiện Tại

```text
multi_agent_writer/
│
├── agents/
│   ├── db/
│   │   ├── connection.py
│   │   │   └── SQLAlchemy async engine/session
│   │   │      (pool_recycle chống mất kết nối)
│   │   ├── models.py
│   │   │   └── WorkflowRun, WorkflowTask
│   │   │      (metadata cho UI, KHÔNG phải checkpoint)
│   │   ├── progress_tracker.py
│   │   │   └── create/update/upsert/query trạng thái workflow
│   │   └── __init__.py
│   │
│   ├── schemas/
│   │   ├── user_request.py
│   │   ├── guardrail.py
│   │   ├── supervisor.py
│   │   ├── plan.py
│   │   │   └── Task có depends_on + order
│   │   │      validator chặn cycle và dependency không hợp lệ
│   │   ├── hitl.py
│   │   ├── research.py
│   │   ├── image.py
│   │   ├── worker.py
│   │   ├── article.py
│   │   ├── evaluation.py
│   │   │   └── 6 tiêu chí, visual_support,
│   │   │      ACCEPTANCE_THRESHOLD=9, MAX_REVISIONS=5
│   │   ├── state.py
│   │   │   └── WriterState
│   │   └── __init__.py
│   │
│   ├── prompts/
│   │   ├── input_guardrails.yaml
│   │   │   └── Policy cho GPT-OSS-Safeguard
│   │   ├── supervisor.yaml
│   │   ├── planner.yaml
│   │   ├── worker.yaml
│   │   ├── synthesizer.yaml
│   │   │   └── Chèn ảnh đúng vị trí,
│   │   │      KHÔNG tự thêm phần Nguồn ảnh
│   │   ├── evaluator.yaml
│   │   ├── prompts_loader.py
│   │   └── __init__.py
│   │
│   ├── tools/
│   │   ├── mcp_client.py
│   │   │   └── Singleton MultiServerMCPClient
│   │   ├── tavily_search.py
│   │   │   └── tool "tavily_search", cache 24h
│   │   ├── wikimedia_images.py
│   │   │   └── tool "wikimedia_search_images", cache 7 ngày
│   │   ├── research_normalizer.py
│   │   └── __init__.py
│   │
│   ├── executor/
│   │   ├── task_manager.py
│   │   │   └── build_execution_batches() bằng Kahn's algorithm
│   │   ├── worker.py
│   │   │   └── run_worker()
│   │   │      research + LLM + retry/backoff
│   │   ├── parallel_executor.py
│   │   │   └── execute_plan()
│   │   │      chạy batch song song
│   │   ├── image_resolver.py
│   │   │   └── resolve_images()
│   │   │      lấy ảnh Wikimedia và chọn ảnh lớn nhất
│   │   └── __init__.py
│   │
│   ├── hooks.py
│   │   └── Registry nhẹ để Worker báo tiến trình
│   │      real-time ra ngoài
│   │
│   ├── models.py
│   │   └── MODEL_REGISTRY tập trung
│   │
│   ├── base_agent.py
│   │   └── BaseAgent dùng structured output
│   │      (with_structured_output)
│   │
│   ├── input_guardrails.py
│   │   └── Rule-based + GPT-OSS-Safeguard
│   │
│   ├── supervisor.py
│   ├── planner.py
│   ├── hitl_handler.py
│   │   └── request_plan_approval()
│   │      dùng interrupt() của LangGraph
│   │
│   ├── synthesizer.py
│   │   └── Tổng hợp + chèn ảnh + attribution
│   │
│   ├── evaluator.py
│   │   └── Chấm 6 tiêu chí
│   │
│   ├── graph.py
│   │   └── LangGraph StateGraph +
│   │      AsyncPostgresSaver checkpoint
│   │
│   ├── cache.py
│   │   └── PostgreSQL cache
│   │
│   ├── logger.py
│   │   └── Logging console + workflow log + errors.log
│   │
│   └── __init__.py
│
├── backend/
│   ├── main.py
│   │   └── FastAPI app + static + Jinja2Templates
│   │
│   ├── schemas/
│   │   ├── requests.py
│   │   ├── responses.py
│   │   └── __init__.py
│   │
│   ├── routes/
│   │   ├── workflow.py
│   │   │   └── API endpoints cho workflow
│   │   └── __init__.py
│   │
│   ├── services/
│   │   ├── workflow_manager.py
│   │   │   └── Chạy graph background,
│   │   │      interrupt/resume HITL,
│   │   │      timeout và progress tracking
│   │   └── __init__.py
│   │
│   ├── middleware/
│   │   ├── error_handler.py
│   │   │   └── Global exception handler
│   │   └── __init__.py
│   │
│   └── __init__.py
│
├── static/
│   ├── style.css
│   │   └── Dark theme + pipeline rail
│   ├── script.js
│   │   └── API + polling + HITL state
│   └── favicon.jpg
│
├── templates/
│   └── index.html
│       └── Compose / Plan / Tasks / Article + Log
│
├── logs/
│   └── Log file theo từng workflow
│
├── outputs/
│   └── Các bài viết Markdown được sinh ra
│
├── .env
│   └── Environment variables
│
├── .gitignore
│
├── app.py
│   └── Entry point
│
├── check_gemini_models.py
│   └── Script kiểm tra Gemini models
│
├── check_groq_models.py
│   └── Script kiểm tra Groq models
│
├── LICENSE
│
├── PROJECT_PLAN.md
│   └── Tài liệu kiến trúc và kế hoạch project
│
├── README.md
│   └── Documentation / giới thiệu project
│
├── requirements.txt
│   └── Python dependencies
│
├── test_prompts.py
│   └── Test prompt / prompt loading
│
└── test_schemas.py
    └── Test Pydantic schemas
```

> **Lưu ý:** `notebook/`, `config/`, `tests/`, `logs/` và `outputs/` được giữ trong cấu trúc tài liệu vì đây là các thư mục thuộc project hiện tại. Nếu một thư mục chưa có file hoặc chưa được sử dụng nhiều, có thể bổ sung chi tiết sau.

---

## 🧠 Models Đang Dùng

| Role                         | Provider | Model                          | Ghi chú                           |
| ---------------------------- | -------- | ------------------------------ | --------------------------------- |
| `input_guardrails`           | Groq SDK | `openai/gpt-oss-safeguard-20b` | Policy-based reasoning classifier |
| `supervisor`                 | Gemini   | `gemini-3.1-flash-lite`        |                                   |
| `planner`                    | Gemini   | `gemini-3.1-flash-lite`        |                                   |
| `worker` / `research_worker` | Groq     | `openai/gpt-oss-20b`           | `reasoning_effort="low"`          |
| `synthesizer`                | Gemini   | `gemini-3.5-flash-lite`        |                                   |
| `evaluator`                  | Gemini   | `gemini-3.1-flash-lite`        |                                   |
| `fallback`                   | Groq     | `openai/gpt-oss-120b`          | Dự phòng                          |

`BaseAgent` sử dụng `with_structured_output()`.

Riêng Groq sử dụng `method="json_mode"` để tránh vấn đề tool-calling với GPT-OSS.

---

## 🔄 Luồng Workflow Chi Tiết

```text
START
  │
  ▼
guardrail
  │
  ├── invalid ──→ END (blocked)
  │
  ▼
supervisor
  │
  ▼
planner
  │
  ▼
HITL
  │
  ├── reject ──→ planner
  │
  └── approved / edited / timeout
          │
          ▼
      executor
          │
          │ DAG + parallel batches
          ▼
    image_resolver
          │
          ▼
     synthesizer
          │
          ▼
      evaluator
          │
          ├── score < 9 ──→ synthesizer
          │                   │
          │                   └── tối đa 5 revisions
          │
          └── score >= 9
                    │
                    ▼
              save_output
                    │
                    ▼
                   END
```

---

## 🧩 Task Dependency — DAG

Mỗi `Task` có:

- `id`
- `title`
- `description`
- `objective`
- `expected_output`
- `requires_research`
- `research_queries`
- `depends_on`
- `order`

`Plan` có validation để:

1. Không cho `depends_on` trỏ tới task không tồn tại.
2. Không cho phép dependency cycle.
3. Dùng DFS 3 màu để phát hiện cycle.

`build_execution_batches()` sử dụng **Kahn's algorithm** để chia task thành các batch.

Ví dụ:

```text
Batch 1:  A   B
           \ /
            ↓
Batch 2:    C
            ↓
Batch 3:    E
```

Các task không phụ thuộc nhau có thể chạy song song.

---

## 👤 HITL — Human-in-the-loop

Hệ thống sử dụng cơ chế:

```python
interrupt()
```

và:

```python
Command(resume=...)
```

của LangGraph.

Không sử dụng `input()` vì workflow được chạy thông qua FastAPI.

### Các trạng thái HITL

```text
Planner
   │
   ▼
HITL interrupt
   │
   ├── Approve
   ├── Edit
   ├── Reject
   └── Timeout
```

Backend lưu trạng thái HITL và Plan để frontend có thể hiển thị.

Timer auto-approve được quản lý bởi `workflow_manager.py`.

Frontend có thể:

- `POST /hitl/pause` khi mở form Edit/Reject.
- `POST /hitl/resume` khi đóng form mà không submit.
- `POST /hitl` khi gửi quyết định cuối cùng.

---

## 🌐 Backend API

| Method | Endpoint                     | Mục đích                |
| ------ | ---------------------------- | ----------------------- |
| POST   | `/workflow`                  | Tạo workflow mới        |
| GET    | `/workflow/{id}/status`      | Lấy trạng thái workflow |
| POST   | `/workflow/{id}/hitl`        | Gửi quyết định HITL     |
| POST   | `/workflow/{id}/hitl/pause`  | Tạm dừng timer HITL     |
| POST   | `/workflow/{id}/hitl/resume` | Resume timer HITL       |
| GET    | `/workflow/{id}/article`     | Lấy bài viết cuối       |
| GET    | `/workflow/{id}/download`    | Download Markdown       |
| GET    | `/workflow/{id}/errors`      | Lấy danh sách lỗi       |
| GET    | `/health`                    | Health check            |
| GET    | `/`                          | Trả frontend            |

### Real-time Progress

Frontend không sử dụng WebSocket.

Thay vào đó:

```text
Frontend
   │
   │ GET /status
   │
   ▼
Polling mỗi 3 giây
```

Worker cập nhật progress thông qua:

```text
agents/hooks.py
        │
        ▼
workflow_manager / progress tracker
        │
        ▼
PostgreSQL
        │
        ▼
Frontend polling
```

---

## 💾 Database Architecture

Project sử dụng **3 lớp dữ liệu riêng biệt**:

### 1. LangGraph Checkpoint

```text
AsyncPostgresSaver
```

Chịu trách nhiệm:

- Lưu `WriterState`.
- Resume workflow.
- Lưu trạng thái graph.
- Lưu nội dung bài viết trong workflow state.

Đây là **nguồn sự thật chính cho workflow state**.

### 2. Workflow Metadata Database

Nằm trong:

```text
agents/db/
```

Bao gồm:

```text
workflow_runs
workflow_tasks
```

Mục đích:

- Tracking workflow.
- Tracking từng task.
- Progress %.
- Status.
- Metadata phục vụ frontend.

Không lưu trùng toàn bộ nội dung bài viết.

### 3. External Tool Cache

Nằm trong:

```text
agents/cache.py
```

Cache sử dụng PostgreSQL.

Cache key:

```text
SHA-256(
    provider + canonicalized request parameters
)
```

TTL:

| Provider  |    TTL |
| --------- | -----: |
| Tavily    | 24 giờ |
| Wikimedia | 7 ngày |

---

## 🖼️ Xử Lý Ảnh Minh Họa

Pipeline:

```text
Worker
  │
  │ image_queries
  ▼
image_resolver
  │
  │ Wikimedia MCP
  ▼
Image Candidates
  │
  │ chọn ảnh có diện tích lớn nhất
  ▼
ImageSpec
  │
  ▼
Synthesizer
  │
  │ chèn Markdown image
  ▼
Final Article
```

Worker được yêu cầu tạo image query:

- Bằng tiếng Anh.
- Ngắn gọn.
- Khoảng 2–4 từ.
- Mang tính khái niệm/phổ quát.

Ví dụ:

```text
Model Context Protocol
```

thay vì:

```text
Sơ đồ kiến trúc Model Context Protocol cho AI Engineer
```

### Attribution

Synthesizer **không tự tạo attribution**.

Attribution được xử lý bằng code để tránh LLM bịa nguồn ảnh.

Khi revision, attribution cũ được strip trước để tránh bị lặp.

---

## ✍️ Worker

Một Worker nhận **một Task cụ thể**.

Pipeline:

```text
Task
 │
 ├── requires_research?
 │        │
 │        └── Tavily
 │
 ├── dependency_context
 │
 ▼
Worker LLM
 │
 ▼
WorkerOutput
```

Worker có retry nội bộ:

```text
MAX_WORKER_RETRIES = 2
```

Tức tối đa **3 lần thử**.

```text
Attempt 1
   │
   └── wait 8s
          │
          ▼
Attempt 2
   │
   └── wait 8s
          │
          ▼
Attempt 3
   │
   ▼
WorkerOutput(success=False)
```

Worker không raise exception ra ngoài workflow.

---

## 🔍 Research

Nếu:

```python
requires_research=True
```

Worker sử dụng các:

```python
research_queries
```

do Planner sinh ra.

Giới hạn:

```text
MAX_RESEARCH_QUERIES_PER_TASK = 2
MAX_RESULTS_PER_QUERY = 3
```

Các source trùng URL được loại bỏ trước khi truyền vào LLM.

---

## 🧪 Evaluator

Evaluator chấm bài theo 6 tiêu chí:

| Tiêu chí                | Ý nghĩa                     |
| ----------------------- | --------------------------- |
| `factuality`            | Độ chính xác                |
| `completeness`          | Độ đầy đủ                   |
| `coherence`             | Tính mạch lạc               |
| `writing_quality`       | Chất lượng diễn đạt         |
| `instruction_following` | Tuân thủ yêu cầu            |
| `visual_support`        | Mức độ hỗ trợ bằng hình ảnh |

Mỗi tiêu chí:

```text
0 → 10
```

Acceptance threshold:

```text
overall_score >= 9
```

Nếu chưa đạt:

```text
Synthesizer
     ↓
Evaluator
     ↓
score < 9
     ↓
Revision
```

Tối đa:

```text
MAX_REVISIONS = 5
```

Nếu hết số lần revision mà vẫn chưa đạt, hệ thống vẫn xuất bài với điểm hiện tại.

---

## 🖥️ Frontend

Frontend sử dụng:

```text
Vanilla HTML
Vanilla CSS
Vanilla JavaScript
```

Cấu trúc:

```text
templates/
└── index.html

static/
├── style.css
├── script.js
└── favicon.jpg
```

### Các khu vực chính

```text
┌──────────────────────────────────────────┐
│                 Pipeline                 │
├──────────┬───────────────────────────────┤
│ Compose  │                               │
│ Plan     │        Main Content           │
│ Tasks    │                               │
│ Article  │                               │
├──────────┴───────────────────────────────┤
│                   Log                    │
└──────────────────────────────────────────┘
```

### Article

Frontend hỗ trợ:

- Render Markdown thành HTML.
- Xem Markdown raw.
- Copy nội dung.
- Download `.md`.

---

## 🐞 Các Vấn Đề Kỹ Thuật Đã Gặp

| Vấn đề                          | Nguyên nhân                               | Giải pháp                          |
| ------------------------------- | ----------------------------------------- | ---------------------------------- |
| LLM trả JSON lỗi                | Ép model tự generate JSON bằng prompt     | `with_structured_output()`         |
| Groq + GPT-OSS lỗi JSON/tool    | Bug với method mặc định                   | `method="json_mode"`               |
| Worker content rỗng             | Reasoning tiêu tốn output budget          | `reasoning_effort="low"`           |
| Rate limit khi chạy parallel    | Groq free tier giới hạn TPM               | Retry + backoff                    |
| `ProactorEventLoop`             | Windows event loop                        | `WindowsSelectorEventLoopPolicy()` |
| `MissingGreenlet`               | Lazy loading SQLAlchemy async             | `selectinload()`                   |
| Checkpoint warning              | Sai tên parameter                         | `allowed_msgpack_modules`          |
| Progress cập nhật trễ           | Executor chỉ emit sau khi node hoàn thành | `agents/hooks.py`                  |
| Wikimedia không tìm thấy ảnh    | Query tiếng Việt dài / quá trừu tượng     | Query tiếng Anh ngắn               |
| Bài không ảnh vẫn điểm cao      | Evaluator thiếu visual criterion          | Thêm `visual_support`              |
| FE mất form đang nhập           | Polling ghi đè UI state                   | `planUiMode`                       |
| FE hiển thị Plan cũ             | Không cập nhật cache sau Edit             | `state.cachedPlan = editedPlan`    |
| HITL auto-approve khi đang Edit | Backend không biết FE đang mở form        | `/hitl/pause` + `/hitl/resume`     |

---

## 🧪 Các File Test & Debug

Project hiện có các script kiểm tra ở root:

```text
check_gemini_models.py
check_groq_models.py
test_prompts.py
test_schemas.py
```

Mục đích:

- Kiểm tra model/provider.
- Kiểm tra prompt loading.
- Kiểm tra Pydantic schemas.
- Debug nhanh mà không cần chạy toàn bộ workflow.

Các test chuyên sâu có thể tiếp tục được bổ sung vào:

```text
tests/
```

---

## 🚀 Cách Chạy Dự Án

Từ thư mục root:

```bash
python app.py
```

Mở trình duyệt:

```text
http://127.0.0.1:8000/
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

---

## 📌 Các Thành Phần Quan Trọng

| Component  | Vai trò                                        |
| ---------- | ---------------------------------------------- |
| LangGraph  | Orchestration + StateGraph + checkpoint        |
| LangChain  | Abstraction cho LLM/tools                      |
| Gemini     | Supervisor / Planner / Synthesizer / Evaluator |
| Groq       | Worker / Research Worker / Guardrail           |
| PostgreSQL | Checkpoint + metadata + cache                  |
| Tavily     | Web research                                   |
| Wikimedia  | Image search                                   |
| MCP        | Chuẩn hóa kết nối external tools               |
| FastAPI    | Backend API                                    |
| Vanilla JS | Frontend                                       |
| Pydantic   | Schema                                         |

---

**Cập nhật lần cuối**: 29/08/2026

**Trạng thái**: `agents/` + `backend/` + giao diện cơ bản đã hoàn chỉnh, chạy end-to-end thành công.
