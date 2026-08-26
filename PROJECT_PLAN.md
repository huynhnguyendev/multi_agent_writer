# 📋 KẾ HOẠCH DỰ ÁN: Multi-Agent Writer

## 🎯 **Tổng Quan Dự Án**

**Tên Dự Án**: Multi-Agent Writer  
**Mục Tiêu**: Xây dựng hệ thống tự động tạo bài viết chất lượng cao sử dụng LangGraph, LangChain, FastAPI  
**Stack Công Nghệ**: LangGraph, LangChain, FastAPI, PostgreSQL, MCP servers (Tavily, Wikimedia)  
**Các Models LLM**: Groq (Llama Guard), Gemini (3.1-flash-lite, 3.5-flash-lite), OpenAI (gpt-oss)

---

## 📐 **Tổng Quan Kiến Trúc**

```
┌─────────────────────────────────────────────────────────────┐
│                   GIAO DIỆN NGƯỜI DÙNG                      │
│                   (FastAPI + React/Vue)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   LangGraph Workflow       │
        └────────────────────────────┘

        ┌─────────────────────────────────────────┐
        │ 1. Kiểm Tra Input (Groq Llama Guard)   │
        ├─────────────────────────────────────────┤
        │ 2. Giám Sát (Gemini 3.1-flash-lite)    │
        ├─────────────────────────────────────────┤
        │ 3. Lập Kế Hoạch (Gemini 3.1-flash-lite)│
        ├─────────────────────────────────────────┤
        │ 4. HITL (Có Sự Tham Gia Con Người) 60s │
        ├─────────────────────────────────────────┤
        │ 5. Thực Hiện (Parallel Workers)        │
        │    ├─ Worker 1 (gpt-oss-20b)           │
        │    ├─ Worker 2 (gpt-oss-20b)           │
        │    └─ Worker N (3-7 workers)           │
        │       └─ Tools: Tavily, Wikimedia MCP  │
        ├─────────────────────────────────────────┤
        │ 6. Tổng Hợp (Gemini 3.5-flash-lite)   │
        ├─────────────────────────────────────────┤
        │ 7. Đánh Giá (Gemini 3.1-flash-lite)    │
        │    └─ Nếu score < 9: Retry (max 5x)   │
        └─────────────────────────────────────────┘

        ┌────────────────────────────┐
        │   External Services        │
        ├────────────────────────────┤
        │ • Groq API                 │
        │ • Gemini API               │
        │ • OpenAI API               │
        │ • Tavily (MCP)             │
        │ • Wikimedia (MCP)          │
        │ • LangSmith (Tracing)      │
        └────────────────────────────┘

        ┌────────────────────────────┐
        │   Data Layer               │
        ├────────────────────────────┤
        │ • PostgreSQL (Checkpoint)  │
        │ • Cache (optional)         │
        └────────────────────────────┘
```

---

## 📁 **Cấu Trúc Thư Mục Chi Tiết**

```
multi_agent_writer/
│
├── agents/                           ← Nơi chứa toàn bộ source code của agents
│   ├── __init__.py
│   ├── db/                          ← Database Models & Logic
│   │   ├── __init__.py
│   │   ├── models.py                ← SQLAlchemy models
│   │   ├── connection.py            ← Kết nối Database PostgreSQL
│   │   ├── checkpoint.py            ← Lưu/tải checkpoint từ DB
│   │   └── migrations/              ← Alembic migrations
│   │
│   ├── schemas/                     ← Pydantic Models & State
│   │   ├── __init__.py
│   │   ├── user_request.py          ← UserRequest schema
│   │   ├── guardrail.py             ← GuardrailResult
│   │   ├── supervisor.py            ← SupervisorDecision
│   │   ├── plan.py                  ← Plan, Task
│   │   ├── hitl.py                  ← HITLDecision
│   │   ├── research.py              ← ResearchResult, ResearchSource
│   │   ├── worker.py                ← WorkerOutput, WorkerState
│   │   ├── article.py               ← FinalArticle
│   │   ├── evaluation.py            ← Evaluation
│   │   ├── image.py                 ← ImageSpec, ImageCandidate
│   │   └── state.py                 ← WriterState (Main State)
│   │
│   ├── prompts/                     ← Prompt System của các agents
│   │   ├── __init__.py
│   │   ├── input_guardrails.yaml
│   │   ├── supervisor.yaml
│   │   ├── planner.yaml
│   │   ├── worker.yaml
│   │   ├── synthesizer.yaml
│   │   ├── evaluator.yaml
│   │   └── prompts_loader.py        ← Load prompts từ YAML files
│   │
│   ├── tools/                       ← MCP Tools
│   │   ├── __init__.py
│   │   ├── tavily_search.py         ← Tavily Search (MCP)
│   │   ├── wikimedia_images.py      ← Wikimedia Images (MCP)
│   │   ├── research_normalizer.py   ← Normalize research results
│   │   └── mcp_client.py            ← MCP Server Client
│   │
│   ├── base_agent.py                ← Base class cho tất cả agents
│   ├── input_guardrails.py          ← Node 1: Kiểm tra input (Groq Llama Guard)
│   ├── supervisor.py                ← Node 2: Route + Research decision (Gemini 3.1)
│   ├── planner.py                   ← Node 3: Tạo plan (Gemini 3.1)
│   ├── hitl_handler.py              ← Node 4: Human-in-the-Loop (WebSocket)
│   ├── executor.py                  ← Node 5: Fan-out workers
│   │   ├── worker.py                ← Single worker logic (gpt-oss-20b)
│   │   ├── task_manager.py          ← Task dependency handling (DAG)
│   │   └── parallel_executor.py     ← Orchestrate parallel execution
│   ├── synthesizer.py               ← Node 6: Tổng hợp bài viết (Gemini 3.5)
│   ├── evaluator.py                 ← Node 7: Chấm điểm (Gemini 3.1)
│   ├── graph.py                     ← LangGraph workflow definition
│   ├── cache.py                     ← Caching layer (PostgreSQL)
│   └── logger.py                    ← Logging setup
│
├── backend/                         ← FastAPI Application & Streaming (Làm sau)
│   ├── __init__.py
│   ├── main.py                      ← FastAPI app entry point
│   ├── routes/                      ← API endpoints
│   │   ├── __init__.py
│   │   ├── workflow.py              ← POST /workflow/start
│   │   ├── status.py                ← GET /workflow/{id}/status
│   │   └── hitl.py                  ← POST /workflow/{id}/hitl
│   ├── middleware/                  ← Custom middleware
│   │   ├── __init__.py
│   │   └── error_handler.py         ← Global error handling
│   └── websocket/                   ← WebSocket handlers
│       ├── __init__.py
│       └── ws_handler.py            ← Real-time updates
│
├── static/                          ← Frontend Assets (không cần quan tâm)
│   ├── css/
│   ├── js/
│   └── images/
│
├── templates/                       ← Frontend HTML (không cần quan tâm)
│   ├── index.html
│   ├── dashboard.html
│   └── ...
│
├── notebook/                        ← Jupyter notebooks (development/testing)
│   └── ...
│
├── config/                          ← Configuration Files
│   ├── __init__.py
│   ├── settings.py                  ← Env variables + Config
│   └── constants.py                 ← Constants (MAX_WORKERS, MAX_REVISIONS)
│
├── tests/                           ← Unit Tests & Integration Tests
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_guardrails.py
│   │   ├── test_planner.py
│   │   ├── test_executor.py
│   │   └── ...
│   ├── integration/
│   │   ├── test_workflow.py
│   │   └── test_e2e.py
│   └── fixtures/
│       ├── __init__.py
│       └── sample_data.py
│
├── logs/                            ← Log files (gitignore)
│   └── ...
│
├── .env                             ← Environment variables (gitignore)
├── .env.example                     ← Example env
├── .gitignore
├── requirements.txt                 ← Dependencies
├── app.py                           ← Entry point chạy toàn bộ dự án
├── README.md
├── PROJECT_PLAN.md                  ← Kế hoạch dự án
└── docker-compose.yml               ← Docker setup (optional)
```

### **📌 Giải Thích Các Folder Chính**

| Folder            | Mục Đích                                                            |
| ----------------- | ------------------------------------------------------------------- |
| `agents/`         | **Nơi chứa toàn bộ source code agents** - Bạn sẽ code chủ yếu ở đây |
| `agents/db/`      | Database models (SQLAlchemy), kết nối DB, checkpoint logic          |
| `agents/schemas/` | Pydantic schemas (UserRequest, Plan, Evaluation, WriterState, etc)  |
| `agents/prompts/` | YAML files chứa system prompts cho các agents                       |
| `agents/tools/`   | MCP tools integrations (Tavily, Wikimedia)                          |
| `backend/`        | FastAPI application, API routes, WebSocket (làm sau)                |
| `static/`         | Frontend assets (CSS, JS, images) - không cần quan tâm              |
| `templates/`      | Frontend HTML templates - không cần quan tâm                        |
| `config/`         | Settings, environment config, constants                             |
| `tests/`          | Unit tests, integration tests                                       |
| `app.py`          | **Entry point** - chạy file này để start dự án                      |

---

## 🔄 **Chi Tiết Từng Node**

### **Node 1: Input Guardrails (Kiểm Tra Đầu Vào)**

- **Model**: Groq Llama Guard 2 (86m)
- **Input**: `UserRequest`
- **Output**: `GuardrailResult`
- **Kiểm Tra**:
  - Phát hiện prompt injection
  - Kiểm tra an toàn nội dung
  - Validation input (độ dài, ngôn ngữ, etc.)
- **Logging**: Ghi log mỗi input + quyết định guardrail
- **Error Handling**: Nếu guardrail bị lỗi (API error), ghi log và reject
- **LangSmith**: Trace quyết định guardrail

---

### **Node 2: Supervisor (Giám Sát)**

- **Model**: Gemini 3.1-flash-lite
- **Input**: `UserRequest`
- **Output**: `SupervisorDecision` (mode: closed_book/open_book/hybrid)
- **Logic**:
  - Phân tích ý định người dùng
  - Quyết định chiến lược research
  - Tạo ra research queries (nếu cần)
- **Logging**: Ghi log quyết định supervisor + reasoning
- **LangSmith**: Trace việc lựa chọn mode

---

### **Node 3: Planner (Lập Kế Hoạch)**

- **Model**: Gemini 3.1-flash-lite
- **Input**: `UserRequest`, `SupervisorDecision`
- **Output**: `Plan` (với 3-7 tasks)
- **Logic**:
  - Tạo tiêu đề bài viết, outline, mục tiêu
  - Tạo danh sách tasks có cấu trúc với IDs
  - Thiết lập flag `requires_research` cho từng task
- **Task Dependency**: Ở giai đoạn này, chỉ định dependencies trong metadata
  - Ví dụ: `task_2.depends_on = ["task_1"]`
- **Logging**: Ghi log toàn bộ cấu trúc plan
- **LangSmith**: Trace việc tạo plan

---

### **Node 4: HITL (Human-in-the-Loop - Có Sự Tham Gia Con Người)**

- **Input**: `Plan` từ Planner
- **Timeout**: 60 giây
- **Hành Động Của User**:
  1. **Approve (Phê Duyệt)**: Tiếp tục tới Executor
  2. **Edit (Chỉnh Sửa)**: Dừng lại, cho user chỉnh sửa plan JSON, sau đó tiếp tục
  3. **Reject (Từ Chối)**: Quay lại Planner (tạo lại plan)
- **Output**: `HITLDecision` + optionally edited `Plan`
- **Implementation**:
  - WebSocket connection tới frontend
  - Lưu plan trong session
  - Xử lý timeout với auto-proceed
- **Logging**: Ghi log hành động của user + bất kỳ chỉnh sửa nào

---

### **Node 5: Executor (Thực Hiện Parallel Workers)**

#### **5a: Xử Lý Task Dependency**

- **Hai Trường Hợp**:
  1. **Independent Tasks** (không có phụ thuộc):
     - Fan-out tất cả 3-7 workers ngay lập tức
     - Sử dụng `asyncio.gather()` hoặc `ThreadPoolExecutor`
  2. **Dependent Tasks** (DAG - Directed Acyclic Graph):
     - Xây dựng dependency graph ở giai đoạn Planner
     - Tại Executor: Topological sort → thực hiện theo batch
     - Ví dụ:
       ```
       Batch 1: [Task 1]
       Batch 2: [Task 2, Task 3]  (cả hai phụ thuộc Task 1)
       Batch 3: [Task 4, Task 5, Task 6]
       ```

#### **5b: Logic Của Một Worker**

- **Model**: OpenAI gpt-oss-20b
- **Input**: `Task`, `UserRequest`, `SupervisorDecision`
- **Output**: `WorkerOutput` (nội dung section + metadata)
- **Decision Logic**:
  - Nếu `task.requires_research`:
    - Gọi Tavily search với `task.research_queries`
    - Normalize kết quả → `ResearchResult`
  - Nếu không:
    - Chỉ dùng kiến thức của LLM
  - Cho ảnh:
    - Tạo `image_queries`
    - Gọi Wikimedia MCP server
- **Logging**: Ghi log quyết định worker (research/no-research), nội dung tạo ra
- **LangSmith**: Trace mỗi lần thực hiện worker

#### **5c: Orchestrate Parallel Execution**

```python
# Pseudo-code
def execute_tasks(tasks: list[Task]) -> list[WorkerOutput]:
    if has_dependencies(tasks):
        batches = topological_sort(tasks)
        outputs = []
        for batch in batches:
            batch_outputs = asyncio.gather(
                *[run_worker(task) for task in batch]
            )
            outputs.extend(batch_outputs)
        return outputs
    else:
        # Tất cả độc lập - chạy tất cả cùng một lúc
        return asyncio.gather(
            *[run_worker(task) for task in tasks]
        )
```

---

### **Node 6: Synthesizer (Tổng Hợp Viết Bài)**

- **Model**: Gemini 3.5-flash-lite
- **Input**: `approved_plan`, `worker_outputs` (list), `user_request`
- **Output**: `FinalArticle` (markdown + metadata)
- **Logic**:
  - Kết hợp worker outputs theo thứ tự
  - Đảm bảo nhất quán về style dùng tone guide
  - Sửa lỗi ngữ pháp, flow, khả năng đọc
  - Thêm giới thiệu/kết luận nếu cần
  - Nhúng image references
- **Logging**: Ghi log quá trình tổng hợp, word count
- **LangSmith**: Trace việc tổng hợp

---

### **Node 7: Evaluator (Đánh Giá)**

- **Model**: Gemini 3.1-flash-lite
- **Input**: `FinalArticle`, `user_request`
- **Output**: `Evaluation` (điểm số + feedback)
- **Tiêu Chí Đánh Giá**:
  - Tính xác thực (0-10)
  - Mức độ đầy đủ (0-10)
  - Tính logic/mạch lạc (0-10)
  - Chất lượng văn phong (0-10)
  - Tuân thủ yêu cầu (0-10)
  - Điểm tổng thể = trung bình
- **Logic**:
  - Nếu overall_score >= 9:
    - `accepted = True` → KẾT THÚC
  - Nếu không:
    - `accepted = False` → Vòng lặp Revision
- **Max Revisions**: 5 (nếu đạt max, chấp nhận với điểm thấp)
- **Logging**: Ghi log điểm đánh giá + feedback
- **LangSmith**: Trace việc đánh giá

---

## 🔄 **Vòng Lặp Revision & Retry**

```
Evaluator
    ├─ score >= 9 → CHẤP NHẬN → KẾT THÚC
    └─ score < 9 → revision_count++
        ├─ revision_count < 5 → Quay lại Synthesizer
        │   └─ Synthesizer nhận feedback từ Evaluator
        │       └─ Tạo lại bài viết với cải thiện
        │           └─ Evaluator (retry)
        └─ revision_count >= 5 → CHẤP NHẬN ANYWAY (buộc kết thúc)
```

---

## 💾 **Chiến Lược Checkpoint & Resume**

### **Các Mốc Checkpoint**

1. **Sau Input Guardrails** (kiểm tra input người dùng)
2. **Sau Supervisor** (quyết định mode research)
3. **Sau Planner** (plan được tạo)
4. **Sau HITL** (plan được phê duyệt/chỉnh sửa)
5. **Sau Executor** (tất cả workers hoàn thành)
6. **Sau Synthesizer** (bài viết được dự thảo)
7. **Sau Evaluator** (đánh giá hoàn thành)

### **Checkpoint Schema**

```python
class Checkpoint(BaseModel):
    workflow_id: str
    milestone: str  # "after_guardrails", "after_executor", etc
    state: WriterState  # Full state snapshot
    timestamp: datetime
    status: str  # "in_progress", "completed", "failed"
    error: str | None = None
```

### **Logic Resume**

- Lưu checkpoint vào PostgreSQL sau mỗi mốc
- Nếu workflow bị lỗi:
  - Xác định checkpoint hợp lệ mới nhất
  - Resume từ checkpoint đó (bỏ qua giai đoạn đã hoàn thành)
  - Chỉ retry giai đoạn bị lỗi
- Nếu một worker bị lỗi:
  - Retry worker đó mà không phải chạy lại các worker khác

---

## 🔌 **Tích Hợp Tools**

### **Tavily Search (qua MCP)**

```
Task → Worker
    └─ nếu requires_research:
        └─ Gọi Tavily MCP
            └─ Lấy kết quả tìm kiếm
                └─ Normalize thành ResearchResult
                    └─ Cache với TTL=24h
```

### **Wikimedia Images (qua MCP)**

```
Worker → image_queries
    └─ Gọi Wikimedia MCP
        └─ Lấy ảnh candidate
            └─ Tạo ImageSpec
                └─ Cache với TTL=7d
```

---

## 💾 **Chiến Lược Cache**

### **Cache Keys** (SHA-256)

```
Tavily:
  key = SHA256(f"tavily::{query}::{language}")
  ttl = 24h

Wikimedia:
  key = SHA256(f"wikimedia::{query}::{language}")
  ttl = 7d
```

### **Cache Backend**: PostgreSQL

```sql
CREATE TABLE cache (
    key VARCHAR(64) PRIMARY KEY,  -- SHA-256 hash
    value JSONB NOT NULL,
    provider VARCHAR(50),  -- "tavily", "wikimedia"
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    ttl_seconds INT
);

-- Index for fast lookups
CREATE INDEX idx_cache_expires ON cache(expires_at);
```

---

## 📊 **Logging & Monitoring**

### **Mức Độ Logging**

```
DEBUG: Luồng thực hiện chi tiết (mỗi function call)
INFO:  Các mốc quan trọng (chuyển node, quyết định)
WARN:  Lỗi không quan trọng (API retry, fallback)
ERROR: Lỗi quan trọng (dừng workflow)
```

### **Tích Hợp LangSmith**

- Bật qua `LANGSMITH_TRACING=true`
- Trace mỗi lần thực hiện node
- Theo dõi token usage cho mỗi model
- Giám sát API latency

### **Log Output**

```
logs/
├── workflow_{id}_{timestamp}.log
└── errors.log
```

---

## 🧪 **Chiến Lược Testing**

### **Phase 1: Unit Tests**

- Test mỗi agent độc lập
- Mock external APIs (Tavily, Gemini, etc.)
- Test schema validation
- Test cache operations

### **Phase 2: Integration Tests**

- Test workflow end-to-end với mock APIs
- Test HITL timeout/approval flow
- Test retry/revision loop
- Test checkpoint save/resume

### **Phase 3: E2E Tests**

- Real API calls (với test credentials)
- Full workflow từ input → markdown output
- Performance testing (latency, token usage)

### **Test Tools**

- `pytest` cho unit/integration tests
- `pytest-asyncio` cho async testing
- `unittest.mock` cho mocking (không gọi real API trong tests)

---

## 📅 **Timeline Triển Khai**

### **Phase 1: Nền Tảng (Tuần 1)**

- [ ] Setup cấu trúc project
- [ ] Tạo Pydantic schemas
- [ ] Setup PostgreSQL + migrations
- [ ] Tải models config + prompts
- [ ] Setup logging + LangSmith

### **Phase 2: Core Agents (Tuần 2-3)**

- [ ] Input Guardrails
- [ ] Supervisor
- [ ] Planner
- [ ] HITL Handler
- [ ] Unit tests cho mỗi agent

### **Phase 3: Executor & Tools (Tuần 3-4)**

- [ ] Worker logic
- [ ] Task dependency handling (DAG)
- [ ] Parallel execution orchestrator
- [ ] Tavily integration
- [ ] Wikimedia integration
- [ ] Caching layer

### **Phase 4: Synthesizer & Evaluator (Tuần 4)**

- [ ] Synthesizer
- [ ] Evaluator
- [ ] Retry loop logic
- [ ] Integration tests

### **Phase 5: API & Frontend Integration (Tuần 5)**

- [ ] FastAPI routes
- [ ] WebSocket cho HITL
- [ ] Checkpoint save/load
- [ ] Error handling middleware
- [ ] E2E tests

### **Phase 6: Polish & Optimization (Tuần 6)**

- [ ] Performance tuning
- [ ] Cost optimization (token tracking)
- [ ] Documentation
- [ ] Deployment setup

---

## 🚀 **Triển Khai**

### **Local Development**

```bash
docker-compose up  # PostgreSQL + Redis (optional)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### **Production**

- Deploy FastAPI tới AWS/GCP/Vercel
- Sử dụng RDS cho PostgreSQL
- Sử dụng managed Redis cho caching (optional)
- Bật HTTPS + auth

---

## 📝 **Các File Chính Cần Tạo Trước**

1. **`agents/base_agent.py`** - Base class cho tất cả agents
2. **`agents/schemas/state.py`** - Main WriterState + tất cả Pydantic models
3. **`agents/prompts/prompts_loader.py`** - Load YAML prompts
4. **`config/model_config.py`** - Tập trung hóa model configs
5. **`agents/graph.py`** - LangGraph workflow definition
6. **`agents/cache.py`** - Caching implementation
7. **`backend/main.py`** - FastAPI application (làm sau)

---

## ✅ **Checklist Trước Khi Triển Khai**

- [ ] `.env` file được cấu hình với tất cả API keys
- [ ] PostgreSQL database được tạo + migrations sẵn sàng
- [ ] LangSmith project được tạo
- [ ] Tavily & Wikimedia MCP servers có thể truy cập được
- [ ] Tất cả models (Groq, Gemini, OpenAI) API keys hợp lệ
- [ ] Cấu trúc project được tạo (folders + `__init__.py`)
- [ ] requirements.txt sẵn sàng

---

## 📞 **Những Câu Hỏi Trong Quá Trình Triển Khai**

Khi bắt đầu code, theo dõi:

1. Bất kỳ thay đổi API nào (phiên bản model mới, endpoints deprecated)
2. Bottlenecks về hiệu suất (agents chậm, high latency)
3. Edge cases (empty research results, image not found)
4. Feedback từ người dùng (HITL timeout quá ngắn/dài, etc.)

---

**Được Tạo**: 2025-08-26  
**Trạng Thái**: Sẵn sàng triển khai
