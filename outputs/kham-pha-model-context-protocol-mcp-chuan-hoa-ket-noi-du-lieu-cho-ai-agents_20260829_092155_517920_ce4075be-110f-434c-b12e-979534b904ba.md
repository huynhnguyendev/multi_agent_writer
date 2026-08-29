# Khám phá Model Context Protocol (MCP): Chuẩn hóa kết nối dữ liệu cho AI Agents

Trong bối cảnh các Large Language Models (LLM) ngày càng đóng vai trò cốt lõi trong các ứng dụng doanh nghiệp, bài toán lớn nhất mà các AI Engineer phải đối mặt không chỉ là năng lực suy luận của mô hình, mà là khả năng kết nối dữ liệu thời gian thực và tích hợp công cụ bên ngoài. Mô hình Retrieval-Augmented Generation (RAG) truyền thống hay các custom connector đơn lẻ thường dẫn đến độ phức tạp cao, khó bảo trì và vấn đề *N×M integration*. Bài viết này sẽ cung cấp cái nhìn kỹ thuật sâu sắc về Model Context Protocol (MCP) – chuẩn mở do Anthropic công bố nhằm giải quyết triệt để bài toán này, giúp tối ưu hóa context-window và chuẩn hóa giao tiếp giữa AI Agents và hệ thống hạ tầng.

## Tổng quan về Model Context Protocol (MCP)

Model Context Protocol (MCP) là một tiêu chuẩn mở được Anthropic công bố vào tháng 11 năm 2024. MCP được thiết kế để **định nghĩa ngôn ngữ và giao diện chuẩn** cho các mô hình ngôn ngữ lớn (LLM) khi truy cập và tương tác với dữ liệu, công cụ và dịch vụ bên ngoài. Nhờ MCP, một LLM không còn bị giới hạn trong kiến thức tĩnh mà có thể **lấy dữ liệu thời gian thực** và thực hiện hành động qua các API, file system, database, hay các hệ thống quản lý doanh nghiệp.

![Tổng quan về MCP và bối cảnh ra đời](https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Cloud_computing.svg/330px-Cloud_computing.svg.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Bối cảnh và nhu cầu
- Trước MCP, mỗi ứng dụng AI thường phải viết **connector tùy chỉnh** cho từng nguồn dữ liệu hoặc công cụ. Khi số lượng ứng dụng (N) và số lượng nguồn (M) tăng, vấn đề *N×M integration* trở nên khó quản lý và chi phí phát triển tăng vọt.
- Anthropic nhận thấy nhu cầu một giao diện chuẩn để **tách biệt logic LLM** khỏi các dịch vụ phụ trợ, giúp các nhà phát triển dễ dàng mở rộng, bảo trì và bảo mật.

### Kiến trúc cơ bản
MCP định nghĩa ba thành phần chính:
1. **Client** – phần mềm hoặc dịch vụ gọi MCP để gửi yêu cầu tới LLM.
2. **Server** – thực thi các *tool* (ví dụ đọc file, gọi API, thực thi hàm) và trả về kết quả cho LLM.
3. **Tool definitions** – mô tả cấu trúc JSON của các công cụ, bao gồm tên, mô tả, tham số và cách gọi.

Khung này tương tự như một *định dạng chuẩn* giữa LLM và các nguồn dữ liệu, giống như cách USB-C cho phép các thiết bị kết nối mà không cần cài driver riêng.

### Ảnh hưởng trong kiến trúc AI hiện đại
- **Tính mở rộng**: Các nhà cung cấp lớn như OpenAI và Google DeepMind đã nhanh chóng chấp nhận MCP, cho phép các AI assistant của họ truy cập dữ liệu doanh nghiệp mà không cần viết code riêng.
- **Tính bảo mật**: MCP cho phép xác thực và phân quyền rõ ràng cho từng tool, giảm nguy cơ lộ dữ liệu nhạy cảm.
- **Tính linh hoạt**: MCP hỗ trợ **stateful agents** có thể lưu trữ ngữ cảnh và thực hiện các tác vụ phức tạp trong vòng lặp.

Như vậy, MCP không chỉ là một giao diện, mà là **động cơ thúc đẩy sự hợp nhất** giữa LLM và hệ sinh thái dữ liệu thực tiễn, giải quyết vấn đề thông tin silo và tăng cường tính ứng dụng thực tiễn của AI.

## Cơ chế hoạt động của MCP
MCP được xây dựng trên mô hình **host–client–server**. Mỗi thành phần có vai trò rõ ràng:

| Thành phần | Vai trò | Mô tả |
|------------|---------|-------|
| **Host** | Ứng dụng AI (ví dụ Claude Desktop) | Khởi tạo kết nối và điều phối các client |
| **Client** | Kết nối tới một MCP server | Quản lý phiên, gửi/nhận JSON‑RPC |
| **Server** | Cung cấp context và tool | Thực thi yêu cầu, trả về kết quả |

![Phân tích kỹ thuật: Cách MCP hoạt động](https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Client-Server.png/330px-Client-Server.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Chu trình giao tiếp qua JSON‑RPC
1. **Khởi tạo** – Khi host muốn kết nối tới server, nó tạo một *client* và gửi message `initialize` (JSON‑RPC 2.0). Thông tin bao gồm `protocolVersion`, `capabilities` và `clientInfo`.
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "initialize",
     "params": {
       "protocolVersion": "2024-11-05",
       "capabilities": {"roots": {"listChanged": true}},
       "clientInfo": {"name": "Claude Desktop", "version": "1.0.0"}
     }
   }
   ```
2. **Yêu cầu tool** – Khi LLM cần thực thi một tool, client gửi request `tools/execute` với `method` và `params` tương ứng.
   ```json
   {
     "jsonrpc": "2.0",
     "id": "unique-id-123",
     "method": "tools/execute",
     "params": {"toolName": "read_file", "arguments": {"path": "/data/report.txt"}}
   }
   ```
3. **Phản hồi** – Server thực thi và trả về kết quả cùng `id`.
   ```json
   {
     "jsonrpc": "2.0",
     "id": "unique-id-123",
     "result": {"content": "..."}
   }
   ```
4. **Notification** – Đối với các hành động không cần phản hồi, client gửi `notification` (fire‑and‑forget).
   ```json
   {
     "jsonrpc": "2.0",
     "method": "log",
     "params": {"message": "Tool executed"}
   }
   ```

### Luồng dữ liệu mẫu
```
Host (AI app)  ──►  Client  ──►  Server
   ▲                 │          │
   │                 │          ▼
   └─────────────────┘  Response
```
- Host gửi yêu cầu tới client.
- Client chuyển tiếp qua JSON‑RPC tới server.
- Server thực thi tool, trả về kết quả.
- Client chuyển kết quả lại cho host, host tích hợp vào ngữ cảnh LLM.

### Lợi ích
- **Modular**: Host có thể kết nối tới nhiều server đồng thời.
- **Sandboxed**: Mỗi server có quyền riêng, giảm rủi ro bảo mật.
- **Composable**: Các tool có thể được kết hợp linh hoạt trong workflow.

## Hướng dẫn triển khai MCP Server cơ bản

![Hướng dẫn triển khai MCP Server cơ bản](https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Client-Server.png/330px-Client-Server.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### 1. Chuẩn bị môi trường
- **Python 3.11+** là phiên bản được khuyến nghị (các ví dụ dưới sử dụng Python 3.11).
- Cài đặt **uv** – trình quản lý dự án và môi trường ảo được khuyên dùng trong tài liệu:
  ```bash
  pip install uv
  ```
- Tạo thư mục dự án và khởi tạo cấu trúc:
  ```bash
  mkdir my-mcp-server && cd my-mcp-server
  uv init mix_server
  ```
  Lệnh `uv init` tạo file `pyproject.toml` và thư mục `src/`.

### 2. Tạo môi trường ảo và cài đặt phụ thuộc
```bash
uv venv
source .venv/bin/activate
```
Cài đặt **mcp** SDK và một số công cụ hỗ trợ:
```bash
uv add mcp
uv add uvicorn  # nếu muốn chạy server qua ASGI
```

### 3. Tạo file server
Tạo file `src/mix_server/server.py` với nội dung mẫu:
```python
from mcp import MCPServer, tool, resource

mcp = MCPServer("Demo Server")

@tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@resource("greeting://{name}")
def greeting(name: str) -> str:
    """Return a greeting for the given name."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()
```
- `@tool()` đăng ký một tool có thể được gọi bởi LLM.
- `@resource()` đăng ký một tài nguyên có thể truy cập qua URL.
- `mcp.run()` khởi động server theo cấu hình mặc định (port 8000).

### 4. Chạy và kiểm thử
```bash
uv run python src/mix_server/server.py
```
Server sẽ lắng nghe tại `http://localhost:8000`.

#### Kiểm thử tool
Sử dụng curl hoặc Postman gửi JSON‑RPC:
```bash
curl -X POST http://localhost:8000 -H "Content-Type: application/json" \
  -d '{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/execute",
        "params": {"toolName": "add", "arguments": {"a": 5, "b": 7}}
      }'
```
Kết quả trả về:
```json
{"jsonrpc":"2.0","id":1,"result":12}
```

#### Kiểm thử resource
```bash
curl http://localhost:8000/greeting/alice
```
Kết quả:
```
Hello, alice!
```

### 5. Đóng gói và phát hành (tùy chọn)
Để đóng gói thành package PyPI:
```bash
uv build
uv publish
```
Tài liệu của FastMCP và CI/CD (CircleCI) cũng hỗ trợ quy trình này.

## Kết luận và Hướng phát triển của MCP

![Kết luận: Tiềm năng và Hướng phát triển của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

MCP (Model Context Protocol) không chỉ đơn thuần là một giao thức truyền dữ liệu giữa AI và nguồn dữ liệu; nó là một khung chuẩn hoá cho việc **định danh, truy cập và thực thi** các tài nguyên (tool, resource) một cách nhất quán. Khi so sánh với phương pháp RAG thủ công, MCP mang lại những lợi ích sau:

| Ưu điểm | Mô tả |
|---|---|
| **Tính mở rộng** | Thêm tool/resource chỉ cần đăng ký decorator; không cần viết lại logic giao tiếp. |
| **Độ tin cậy** | Giao thức JSON‑RPC/HTTP được kiểm thử rộng rãi, giảm thiểu lỗi khi truyền dữ liệu. |
| **Tích hợp dễ dàng** | Các mô-đun có thể được triển khai độc lập (microservice) và được gọi qua URL hoặc RPC, phù hợp với kiến trúc micro‑service hiện đại. |
| **Bảo mật** | MCP hỗ trợ xác thực OAuth2/Token, cho phép kiểm soát quyền truy cập chi tiết cho từng tool/resource. |
| **Hiệu suất** | Sử dụng async/await (ví dụ với Uvicorn) giúp xử lý nhiều yêu cầu đồng thời, giảm độ trễ so với RAG truyền thống. |

### Hướng phát triển
1. **Chuẩn hoá metadata** – Định nghĩa schema cho tool/resource để tự động sinh API docs và client SDK.
2. **Caching & Versioning** – Thêm cơ chế cache nội bộ và quản lý phiên bản tool/resource, giúp tránh tải lại dữ liệu lặp lại.
3. **Observability** – Tích hợp logging, metrics (Prometheus) và tracing (OpenTelemetry) để giám sát hiệu suất và lỗi.
4. **Marketplace** – Xây dựng kho lưu trữ công cộng cho các tool/resource, tạo cộng đồng đóng góp và chia sẻ.
5. **Hybrid RAG** – Kết hợp MCP với retrieval‑augmented generation: LLM gọi `mcp.tools/execute` để lấy dữ liệu, sau đó sử dụng trong prompt.

Tóm lại, MCP cung cấp một nền tảng **đều nhất, mở rộng và an toàn** cho việc xây dựng hệ sinh thái AI. Khi cộng đồng chấp nhận và triển khai rộng rãi, MCP có thể trở thành tiêu chuẩn công nghiệp cho giao tiếp giữa mô hình AI và dữ liệu.
## Nguồn ảnh

- [Tổng quan về MCP và bối cảnh ra đời](https://commons.wikimedia.org/w/index.php?curid=6080417) — Sam Johnston, CC BY-SA 3.0
- [Phân tích kỹ thuật: Cách MCP hoạt động](https://commons.wikimedia.org/w/index.php?curid=148266300) — Anselm Vollprecht (cite source: „Und jetzt zus@mmen. Dein Einstieg ins Echtzeit-Musizieren über das Internet“ von Anselm Vollprecht), CC BY-SA 4.0
- [Hướng dẫn triển khai MCP Server cơ bản](https://commons.wikimedia.org/w/index.php?curid=148266300) — Anselm Vollprecht (cite source: „Und jetzt zus@mmen. Dein Einstieg ins Echtzeit-Musizieren über das Internet“ von Anselm Vollprecht), CC BY-SA 4.0
- [Kết luận: Tiềm năng và Hướng phát triển của MCP](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
