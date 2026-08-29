# 🖋️ Multi-Agent Writer

Hệ thống tự động viết bài blog bằng kiến trúc **multi-agent** với **LangGraph**, kết hợp **Human-in-the-Loop (HITL)**, thực thi task song song theo **Dependency DAG**, research qua MCP, tìm ảnh minh họa từ Wikimedia Commons, tự đánh giá chất lượng và tự revision khi bài viết chưa đạt yêu cầu.

### Workflow tổng quát

**Nhập yêu cầu → Guardrail → Supervisor → Planner → HITL → Executor (DAG song song) → Image Resolver → Synthesizer → Evaluator → Revision nếu cần → Xuất Markdown**

---

## 📐 Kiến trúc

```text
┌─────────────────────────────────────────────────────────────┐
│         FRONTEND (static/ + templates/, dark theme)         │
│   Compose → Plan (HITL) → Tasks → Article, polling 3s       │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST API
┌───────────────────────────▼─────────────────────────────────┐
│                    BACKEND (FastAPI)                        │
│   routes/workflow.py → services/workflow_manager.py         │
│                                                             │
│   - Chạy graph ở background                                 │
│   - Xử lý interrupt/resume của HITL                         │
│   - Đồng bộ progress real-time vào DB                       │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              AGENTS (LangGraph StateGraph)                  │
│                                                             │
│  guardrail → supervisor → planner ⇄ hitl(interrupt) →      │
│  executor(DAG song song) → image_resolver →                 │
│  synthesizer ⇄ evaluator → save_output                     │
└─────────────────────────────────────────────────────────────┘
```

### Stack

- **Orchestration:** LangGraph, LangChain
- **Backend:** FastAPI
- **Database:** PostgreSQL
- **LLM:** Google Gemini, Groq
- **Research:** Tavily qua MCP
- **Image search:** Wikimedia Commons qua MCP
- **Frontend:** Vanilla HTML / CSS / JavaScript
- **Observability:** Logging + LangSmith
- **Validation:** Pydantic

---

## ✨ Tính năng chính

### 1. Multi-Agent Pipeline

Workflow được chia thành các trách nhiệm rõ ràng thay vì dùng một LLM duy nhất cho toàn bộ bài viết:

- **Input Guardrails** — kiểm tra input trước khi workflow bắt đầu.
- **Supervisor** — quyết định chiến lược `closed_book`, `open_book` hoặc `hybrid`.
- **Planner** — chia yêu cầu thành Plan gồm các Task có dependency.
- **HITL** — con người xác nhận, chỉnh sửa hoặc từ chối Plan.
- **Executor** — chạy các Worker theo Dependency DAG.
- **Image Resolver** — tìm ảnh Wikimedia dựa trên query do Worker đề xuất.
- **Synthesizer** — tổng hợp các section thành bài viết hoàn chỉnh và chèn ảnh.
- **Evaluator** — đánh giá chất lượng và yêu cầu revision nếu chưa đạt.
- **Save Output** — lưu bài viết cuối cùng thành file Markdown.

### 2. Task Dependency DAG

Mỗi `Task` có thể khai báo:

```text
depends_on: ["task_01", "task_02"]
```

Planner tạo dependency graph, sau đó Executor dùng **Kahn's algorithm** để chia task thành các batch:

```text
Batch 1:  Task A ─────┐
          Task B ─────┼── chạy song song
          Task C ─────┘
                 │
                 ▼
Batch 2:  Task D ─────┐
          Task E ─────┘
              chạy song song
```

- Task không phụ thuộc nhau có thể chạy đồng thời.
- Task phụ thuộc chỉ chạy sau khi dependency hoàn thành.
- `Plan` có validation chống:
  - `depends_on` trỏ tới task không tồn tại.
  - Dependency cycle.

### 3. Research có kiểm soát

Planner có thể tạo `research_queries` cho từng Task.

Worker chỉ gọi Tavily khi:

```text
task.requires_research == True
```

Research result được normalize thành `ResearchSource` thay vì đưa raw response của provider trực tiếp vào State.

Mỗi task giới hạn số query và số kết quả để kiểm soát token/cost:

- Tối đa **2 research queries / task**
- Tối đa **3 results / query**

### 4. MCP Tools + PostgreSQL Cache

Project sử dụng MCP để tách agent khỏi implementation cụ thể của external tool:

```text
Worker
   │
   ▼
Tavily Search
   │
   ▼
MCP
   │
   ▼
Tavily Server
```

Các tool hiện tại:

- `tavily_search`
- `wikimedia_search_images`

Kết quả external tool được cache trong PostgreSQL:

| Provider  |    TTL |
| --------- | -----: |
| Tavily    | 24 giờ |
| Wikimedia | 7 ngày |

Cache key được tạo từ:

```text
SHA-256(provider + canonicalized request parameters)
```

### 5. Human-in-the-Loop thật sự

HITL sử dụng cơ chế native:

```python
interrupt()
```

của LangGraph, kết hợp:

```text
Command(resume=...)
```

Không sử dụng `input()` trong workflow web.

Người dùng có thể:

- **Approve** Plan.
- **Edit** Plan rồi approve.
- **Reject** Plan và gửi feedback để Planner lập lại.
- Không phản hồi → backend tự động approve sau **60 giây**.

Khi người dùng đang mở form Edit/Reject, frontend có thể pause timer để tránh việc Plan bị auto-approve trong lúc đang chỉnh sửa.

### 6. Real-time Progress

Frontend không sử dụng WebSocket mà dùng:

```text
Polling mỗi 3 giây
```

Worker cập nhật trạng thái qua `agents/hooks.py` ngay khi bắt đầu/kết thúc:

```text
running → success
running → failed
```

Vì vậy UI có thể hiển thị tiến trình từng task trong khi Executor vẫn đang chạy.

### 7. Image Resolver

Worker có thể đề xuất tối đa các image query phù hợp cho section.

Query được định hướng:

- **Tiếng Anh**
- Ngắn gọn khoảng **2–4 từ**
- Mang tính khái niệm/phổ quát
- Phù hợp với Wikimedia Commons

Image Resolver:

```text
Worker
  │
  └── image_queries
          │
          ▼
   Wikimedia MCP
          │
          ▼
     candidates
          │
          ▼
   chọn ảnh có diện tích lớn nhất
          │
          ▼
   image_markdown
```

Synthesizer chỉ chèn ảnh dựa trên dữ liệu đã được resolver cung cấp, không tự bịa URL.

Phần **Nguồn ảnh / attribution** được tạo bằng code thay vì yêu cầu LLM tự sinh credit.

Khi revision xảy ra, attribution cũ được strip trước để tránh bị lặp.

### 8. Quality Evaluation + Revision

Evaluator chấm **6 tiêu chí**, mỗi tiêu chí từ 0–10:

1. `factuality`
2. `completeness`
3. `coherence`
4. `writing_quality`
5. `instruction_following`
6. `visual_support`

Ngưỡng chấp nhận:

```text
overall_score >= 9
```

`visual_support` được đánh giá dựa trên **số ảnh thực tế đã được nhúng**, thay vì chỉ dựa vào việc LLM tự đánh giá.

Nếu bài chưa đạt:

```text
Synthesizer
     ↓
Evaluator
     ↓
score < 9
     ↓
revision
     ↓
Synthesizer
     ↓
...
```

Tối đa **5 lần revision**. Nếu vẫn chưa đạt sau giới hạn, hệ thống vẫn xuất bài với điểm hiện tại.

---

## 🔧 Yêu cầu hệ thống

| Thành phần        | Yêu cầu                    |
| ----------------- | -------------------------- |
| Python            | 3.11                       |
| PostgreSQL        | 14+                        |
| Node.js           | ≥ 18                       |
| Groq API          | Required                   |
| Google Gemini API | Required                   |
| Tavily API        | Required                   |
| LangSmith         | Optional, dùng cho tracing |

Node.js cần thiết vì Wikimedia MCP server hiện được khởi chạy thông qua `npx`.

Kiểm tra:

```bash
node -v
```

---

## 🚀 Cài đặt

### 1. Tạo môi trường Python

```bash
conda create -n multi-agent-writer python=3.11 -y
conda activate multi-agent-writer
```

### 2. Cài dependencies

```bash
pip install -r requirements.txt
```

### 3. Tạo PostgreSQL database

Tạo một database PostgreSQL cho project, ví dụ:

```text
multi_agent_writer
```

Project sử dụng PostgreSQL cho nhiều mục đích độc lập:

```text
PostgreSQL
├── LangGraph Checkpoint
├── Workflow Metadata
└── External Tool Cache
```

### 4. Cấu hình `.env`

Tạo `.env` tại thư mục root:

```env
GROQ_API_KEY="..."
GEMINI_API_KEY="..."
TAVILY_API_KEY="..."

DATABASE_URL="postgresql://user:password@localhost:5432/multi_agent_writer"

LANGSMITH_TRACING="true"
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_API_KEY="..."
LANGSMITH_PROJECT="Multi Agent Writer"
```

> `DATABASE_URL` sử dụng PostgreSQL với driver `psycopg`. Không đổi sang `postgresql+asyncpg://` nếu code hiện tại đang dùng cấu hình `psycopg`.

---

## ▶️ Chạy dự án

Từ thư mục root:

```bash
python app.py
```

Sau khi server khởi động:

| Chức năng       | URL                            |
| --------------- | ------------------------------ |
| 🖥️ Web UI       | `http://127.0.0.1:8000/`       |
| 📄 Swagger UI   | `http://127.0.0.1:8000/docs`   |
| ❤️ Health Check | `http://127.0.0.1:8000/health` |

---

## 📁 Cấu trúc thư mục

```text
multi_agent_writer/
│
├── agents/
│   ├── db/
│   │   ├── connection.py
│   │   ├── models.py
│   │   └── progress_tracker.py
│   │
│   ├── schemas/
│   │   ├── user_request.py
│   │   ├── guardrail.py
│   │   ├── supervisor.py
│   │   ├── plan.py
│   │   ├── hitl.py
│   │   ├── research.py
│   │   ├── image.py
│   │   ├── worker.py
│   │   ├── article.py
│   │   ├── evaluation.py
│   │   └── state.py
│   │
│   ├── prompts/
│   │   ├── input_guardrails.yaml
│   │   ├── supervisor.yaml
│   │   ├── planner.yaml
│   │   ├── worker.yaml
│   │   ├── synthesizer.yaml
│   │   ├── evaluator.yaml
│   │   └── prompts_loader.py
│   │
│   ├── tools/
│   │   ├── mcp_client.py
│   │   ├── tavily_search.py
│   │   ├── wikimedia_images.py
│   │   └── research_normalizer.py
│   │
│   ├── executor/
│   │   ├── task_manager.py
│   │   ├── worker.py
│   │   ├── parallel_executor.py
│   │   └── image_resolver.py
│   │
│   ├── hooks.py
│   ├── models.py
│   ├── base_agent.py
│   ├── input_guardrails.py
│   ├── supervisor.py
│   ├── planner.py
│   ├── hitl_handler.py
│   ├── synthesizer.py
│   ├── evaluator.py
│   ├── graph.py
│   ├── cache.py
│   └── logger.py
│
├── backend/
│   ├── main.py
│   ├── schemas/
│   │   ├── requests.py
│   │   └── responses.py
│   ├── routes/
│   │   └── workflow.py
│   ├── services/
│   │   └── workflow_manager.py
│   └── middleware/
│       └── error_handler.py
│
├── static/
│   ├── style.css
│   └── script.js
│
├── templates/
│   └── index.html
│
├── outputs/
├── logs/
│
├── .env
├── .gitignore
├── app.py
├── check_gemini_models.py
├── check_groq_models.py
├── test_prompts.py
├── test_schemas.py
├── LICENSE
├── requirements.txt
├── README.md
└── PROJECT_PLAN.md
```

### Một số thư mục/file đáng chú ý

- `agents/graph.py` — entry point xây dựng LangGraph workflow.
- `agents/base_agent.py` — abstraction chung cho các LLM agent và structured output.
- `agents/models.py` — registry tập trung cho model theo từng role.
- `agents/executor/worker.py` — xử lý một Task, research nếu cần, gọi LLM, retry/backoff.
- `agents/executor/task_manager.py` — xây dựng execution batches bằng Kahn's algorithm.
- `agents/executor/parallel_executor.py` — fan-out Worker theo từng batch.
- `agents/executor/image_resolver.py` — resolve image query thành ảnh Wikimedia.
- `agents/hooks.py` — bridge để Worker cập nhật progress ra backend mà không phụ thuộc ngược vào `backend/`.
- `agents/hitl_handler.py` — xử lý `interrupt()` của LangGraph.
- `backend/services/workflow_manager.py` — quản lý workflow background, interrupt/resume và HITL timeout.
- `agents/cache.py` — PostgreSQL cache dùng chung cho external tools.
- `outputs/` — nơi lưu bài viết Markdown sau khi workflow hoàn thành.
- `logs/` — log theo workflow và `errors.log`.

---

## 🧠 Model đang sử dụng

Model được tập trung quản lý trong `agents/models.py`.

| Role               | Provider           | Model                          | Ghi chú                           |
| ------------------ | ------------------ | ------------------------------ | --------------------------------- |
| `input_guardrails` | Groq SDK trực tiếp | `openai/gpt-oss-safeguard-20b` | Policy-based reasoning classifier |
| `supervisor`       | Gemini             | `gemini-3.1-flash-lite`        |                                   |
| `planner`          | Gemini             | `gemini-3.1-flash-lite`        |                                   |
| `worker`           | Groq               | `openai/gpt-oss-20b`           | `reasoning_effort="low"`          |
| `research_worker`  | Groq               | `openai/gpt-oss-20b`           | `reasoning_effort="low"`          |
| `synthesizer`      | Gemini             | `gemini-3.5-flash-lite`        |                                   |
| `evaluator`        | Gemini             | `gemini-3.1-flash-lite`        |                                   |
| `fallback`         | Groq               | `openai/gpt-oss-120b`          | Dự phòng                          |

### Structured Output

Các agent chính sử dụng:

```text
with_structured_output()
```

Riêng Groq được cấu hình `method="json_mode"` để tránh vấn đề tương thích của `gpt-oss` với cơ chế tool-calling mặc định.

Input Guardrails là ngoại lệ: sử dụng **Groq SDK trực tiếp**, không đi qua `BaseAgent`.

---

## 🔄 Workflow chi tiết

```text
START
  │
  ▼
Guardrail
  │
  ├── invalid ───────────────► END (blocked)
  │
  ▼ valid
Supervisor
  │
  ▼
Planner
  │
  ▼
HITL
  │
  ├── reject ──► Planner (với feedback)
  │
  ├── edit ────► validate Plan ──► Executor
  │
  └── approve / timeout ────────► Executor
                                    │
                                    ▼
                            Executor (DAG)
                                    │
                                    ▼
                            Image Resolver
                                    │
                                    ▼
                              Synthesizer
                                    │
                                    ▼
                              Evaluator
                                    │
                         ┌──────────┴──────────┐
                         │                     │
                    score < 9             score >= 9
                         │                     │
                         ▼                     ▼
                    Revision             Save Output
                         │                     │
                         └──► Synthesizer      ▼
                                          END
```

---

## 🌐 Backend API

Các endpoint chính trong `backend/routes/workflow.py`:

| Method | Endpoint                     | Mục đích                                       |
| ------ | ---------------------------- | ---------------------------------------------- |
| `POST` | `/workflow`                  | Tạo workflow mới và chạy background            |
| `GET`  | `/workflow/{id}/status`      | Lấy trạng thái workflow, Plan và task progress |
| `POST` | `/workflow/{id}/hitl`        | Submit quyết định HITL                         |
| `POST` | `/workflow/{id}/hitl/pause`  | Pause timer auto-approve                       |
| `POST` | `/workflow/{id}/hitl/resume` | Resume/reset timer                             |
| `GET`  | `/workflow/{id}/article`     | Lấy bài viết cuối cùng                         |
| `GET`  | `/workflow/{id}/download`    | Download file Markdown                         |
| `GET`  | `/workflow/{id}/errors`      | Lấy danh sách lỗi                              |
| `GET`  | `/health`                    | Health check                                   |
| `GET`  | `/`                          | Trả frontend `index.html`                      |

Swagger UI cung cấp schema và khả năng test trực tiếp các API:

```text
http://127.0.0.1:8000/docs
```

---

## 💾 Thiết kế Database

Project cố ý tách PostgreSQL thành **3 lớp trách nhiệm**:

### 1. LangGraph Checkpoint

`AsyncPostgresSaver`

Chịu trách nhiệm lưu state/checkpoint của LangGraph để workflow có thể:

- resume sau `interrupt()`
- tiếp tục workflow sau HITL
- khôi phục state khi workflow bị gián đoạn

Đây là nguồn dữ liệu chính cho workflow state.

### 2. Workflow Metadata

SQLAlchemy trong:

```text
agents/db/
```

Các bảng metadata như:

```text
workflow_runs
workflow_tasks
```

Chỉ phục vụ tracking/UI:

- workflow status
- task status
- progress
- error metadata

Không lưu trùng nội dung bài viết.

### 3. External Tool Cache

Cache trong:

```text
agents/cache.py
```

Lưu kết quả external tool để giảm số lần gọi API.

```text
Tavily     → TTL 24h
Wikimedia  → TTL 7 ngày
```

---

## 🛡️ Error Handling & Reliability

Worker sử dụng chiến lược:

```text
Fail → Log → Retry → Backoff → Retry → Fail gracefully
```

Không để exception của một Worker phá toàn bộ workflow.

Cấu hình hiện tại:

```text
MAX_WORKER_RETRIES = 2
WORKER_RETRY_BACKOFF_SECONDS = 8
```

Tức là một Worker có tối đa:

```text
3 lần thử
```

Nếu vẫn thất bại:

```python
WorkerOutput(success=False, error=...)
```

được trả về thay vì raise exception ra ngoài.

### Một số vấn đề đã xử lý

- Groq `gpt-oss` JSON/tool-calling compatibility → dùng `json_mode`.
- Reasoning model tiêu tốn output budget → `reasoning_effort="low"`.
- Nhiều Worker chạy song song gây rate limit → retry + backoff.
- Windows `ProactorEventLoop` với psycopg → sử dụng `WindowsSelectorEventLoopPolicy`.
- SQLAlchemy async lazy loading → `selectinload()`.
- Checkpoint deserialize warning → khai báo `allowed_msgpack_modules`.
- Worker progress bị cập nhật muộn → `agents/hooks.py`.
- Wikimedia query không hiệu quả → query tiếng Anh ngắn.
- Evaluator bỏ qua ảnh → thêm `visual_support`.
- HITL form bị polling ghi đè → frontend quản lý `planUiMode`.
- HITL timeout chạy trong lúc đang Edit/Reject → `/hitl/pause` và `/hitl/resume`.

---

## 🧪 Testing & Debug

Project hiện có các script kiểm tra ở root:

```text
check_gemini_models.py
check_groq_models.py
test_prompts.py
test_schemas.py
```

Có thể dùng chúng để kiểm tra:

- model/API configuration
- prompt loading
- Pydantic schema validation

Các test có thể được mở rộng thành test suite riêng khi project phát triển thêm.

---

## 📊 Observability

Project có hai lớp theo dõi:

### Runtime logging

```text
logs/
├── <workflow_id>.log
└── errors.log
```

Mỗi workflow có log riêng, đồng thời lỗi quan trọng được ghi vào `errors.log`.

### LangSmith

Có thể bật tracing thông qua `.env`:

```env
LANGSMITH_TRACING="true"
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_API_KEY="..."
LANGSMITH_PROJECT="Multi Agent Writer"
```

---

## 📄 Output

Sau khi workflow hoàn thành, bài viết được lưu tại:

```text
outputs/
```

Ví dụ:

```text
outputs/
└── <workflow_id>.md
```

Backend cũng cung cấp endpoint:

```text
GET /workflow/{id}/article
GET /workflow/{id}/download
```

để frontend đọc và tải bài viết.

---

## 🧭 Design Principles

Project hiện được xây dựng theo một số nguyên tắc chính:

### Separation of Concerns

Mỗi thành phần chỉ chịu trách nhiệm cho một phần của workflow:

```text
Planner      → Plan
Worker       → Section
Resolver     → Images
Synthesizer  → Final article
Evaluator    → Quality
```

### Provider Independence

Agent không phụ thuộc trực tiếp vào raw response của provider.

Ví dụ research được normalize thành:

```text
ResearchSource
```

để implementation bên dưới có thể thay đổi:

```text
Tavily
   ↓
MCP Search
   ↓
Google Search
```

mà Worker không cần biết chi tiết implementation.

### State vs Metadata

Checkpoint LangGraph và workflow metadata được tách riêng:

```text
LangGraph Checkpoint
    → workflow state

SQLAlchemy metadata
    → UI/progress tracking
```

Tránh lưu trùng nội dung bài viết.

### Code > LLM đối với dữ liệu deterministic

Những phần cần tính chính xác được xử lý bằng code thay vì giao cho LLM:

- dependency validation
- cycle detection
- execution ordering
- image URL handling
- attribution generation
- score acceptance enforcement
- retry/backoff
- progress tracking

---

## 📌 Project Status

**Current status:** `agents/` + `backend/` + frontend cơ bản đã hoàn thiện và workflow chạy end-to-end.

Các thành phần chính hiện đã có:

- ✅ LangGraph workflow
- ✅ Multi-agent architecture
- ✅ Planner + dependency DAG
- ✅ Parallel Worker execution
- ✅ Research qua Tavily MCP
- ✅ Wikimedia image resolver
- ✅ HITL bằng `interrupt()` / resume
- ✅ PostgreSQL checkpoint
- ✅ PostgreSQL metadata
- ✅ PostgreSQL cache
- ✅ Real-time task progress qua polling
- ✅ Synthesizer + image insertion
- ✅ Evaluator + automatic revision
- ✅ Markdown output
- ✅ FastAPI backend
- ✅ Vanilla JS frontend
- ✅ Logging
- ✅ LangSmith tracing

---

## 📄 License

Dự án cá nhân / portfolio.

Xem file [`LICENSE`](LICENSE) để biết thông tin giấy phép hiện tại.

---

**Cập nhật lần cuối:** 29/08/2026

**Author:** _Huynh Nguyen Dev_
