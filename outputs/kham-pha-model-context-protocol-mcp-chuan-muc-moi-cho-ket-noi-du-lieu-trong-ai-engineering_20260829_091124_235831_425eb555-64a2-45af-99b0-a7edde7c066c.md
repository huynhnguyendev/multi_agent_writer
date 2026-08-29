# Khám phá Model Context Protocol (MCP): Chuẩn mực mới cho kết nối dữ liệu trong AI Engineering

Trong kỷ nguyên phát triển mạnh mẽ của các ứng dụng Trí tuệ Nhân tạo, việc kết nối các Large Language Models (LLM) với dữ liệu nội bộ và công cụ bên ngoài luôn là một thử thách lớn đối với các AI Engineers và Software Architects. Sự phân mảnh ngữ cảnh và vấn đề tích hợp phức tạp giữa nhiều hệ thống đặt ra nhu cầu cấp thiết về một tiêu chuẩn mở. Model Context Protocol (MCP) ra đời như một giải pháp đột phá, giải quyết bài toán giao tiếp và đồng bộ hóa dữ liệu. Bài viết này sẽ cung cấp cái nhìn kỹ thuật sâu sắc về MCP, cách thức hoạt động, hướng dẫn triển khai thực tế cũng như những đánh giá toàn diện về lợi ích và thách thức khi áp dụng vào hệ thống.

## Tổng quan về MCP và bối cảnh ra đời

Model Context Protocol (MCP) là một chuẩn mở được Anthropic giới thiệu vào tháng 11/2024, nhằm **đồng bộ hóa cách các mô hình AI truy cập và chia sẻ dữ liệu** với các hệ thống bên ngoài như kho dữ liệu, công cụ quản lý doanh nghiệp và môi trường phát triển. MCP cung cấp một giao diện chuẩn cho việc đọc tệp, thực thi chức năng và xử lý các prompt ngữ cảnh, giúp các ứng dụng LLM tránh được vấn đề *context fragmentation*—khi dữ liệu bị tách rời giữa nhiều nguồn và không thể được truy cập một cách liên tục và nhất quán.

![Tổng quan về MCP và bối cảnh ra đời](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Lý do ra đời
- **Fragmentation of context**: Trước MCP, mỗi ứng dụng AI cần viết mã kết nối riêng cho từng nguồn dữ liệu hoặc công cụ, dẫn tới sự lặp lại công việc và khó khăn trong việc mở rộng.
- **N×M integration problem**: Khi số lượng ứng dụng AI (N) và số lượng công cụ/điểm dữ liệu (M) tăng, số lượng kết nối cần thiết tăng theo N×M, gây tốn kém và khó quản lý.
- **Siloed information**: Các hệ thống legacy và dữ liệu nội bộ thường được giữ riêng biệt, khiến AI không thể truy cập thông tin thời gian thực.

### Vai trò trong kiến trúc AI hiện đại
- **Chuẩn hóa giao tiếp**: MCP định nghĩa ngôn ngữ và quy tắc giao tiếp giữa mô hình và các nguồn dữ liệu, giúp giảm thiểu mã glue và tăng tính tái sử dụng.
- **Tính tương thích đa nền tảng**: Các nhà cung cấp lớn như OpenAI và Google DeepMind đã chấp nhận MCP, cho phép các agent từ các nền tảng khác nhau tương tác với cùng một bộ công cụ.
- **Tăng tính linh hoạt**: MCP cho phép agent khám phá và gọi các công cụ một cách động, hỗ trợ xây dựng quy trình làm việc đa bước mà không cần mã cứng.

Nhờ những lợi ích này, MCP đã trở thành một thành phần quan trọng trong việc xây dựng các hệ thống AI tự động, đặc biệt là trong các ứng dụng doanh nghiệp cần tích hợp nhiều nguồn dữ liệu phức tạp.

## Kiến trúc client‑host‑server của MCP

MCP được thiết kế theo mô hình **client‑server** truyền thống nhưng với những đặc trưng riêng để phục vụ LLM. Mỗi **host** (ứng dụng AI) tạo ra một hoặc nhiều **client** để kết nối tới **server** riêng biệt. Các thành phần này hoạt động trên cùng một máy chủ hoặc qua mạng, tùy thuộc vào môi trường triển khai (địa phương – stdio, hoặc từ xa – HTTP).

![Phân tích kiến trúc kỹ thuật của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Client-Server.png/330px-Client-Server.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

```
Host (AI application) ──► Client ──► Server
```

- **Host**: Giao diện người dùng cuối, ví dụ Claude Desktop, IDE tích hợp hoặc trình duyệt mở rộng. Host quyết định cần truy cập tài nguyên nào và khởi tạo client tương ứng.
- **Client**: Thực hiện giao tiếp chuẩn MCP, duy trì kênh JSON‑RPC có trạng thái (stateful) với server. Client thực hiện các lệnh như `invokeTool`, `fetchResource`, hoặc `providePrompt`.
- **Server**: Cung cấp các khả năng cụ thể – truy cập cơ sở dữ liệu, thực thi công cụ, đọc/ghi tệp, hoặc cung cấp prompt mẫu. Server trả về kết quả qua JSON‑RPC.

### Giao tiếp qua JSON‑RPC

MCP sử dụng **JSON‑RPC 2.0** làm lớp giao tiếp. Đặc trưng của giao thức:

| Tính năng | Mô tả |
|-----------|-------|
| **Stateful session** | Client và server duy trì một phiên làm việc liên tục, cho phép đa luồng và lưu trữ ngữ cảnh giữa các lời gọi. |
| **Bidirectional** | Cả hai bên có thể gửi request và response; server có thể gửi `notification` (ví dụ: cảnh báo lỗi) mà không cần request. |
| **Transport agnostic** | JSON‑RPC có thể chạy qua stdio, TCP, hoặc HTTP, tùy thuộc vào môi trường. |

Mỗi tin nhắn JSON‑RPC bao gồm `jsonrpc`, `method`, `params`, và `id`. Ví dụ:

```json
{
  "jsonrpc": "2.0",
  "method": "invokeTool",
  "params": {
    "toolId": "db_query",
    "arguments": {"sql": "SELECT COUNT(*) FROM users"}
  },
  "id": 42
}
```

### Cơ chế trao đổi tài nguyên, prompts và tools

1. **Capability negotiation** – Khi client kết nối, server gửi danh sách **capabilities** (resources, tools, prompts). Client lưu trữ danh sách này để quyết định hành động.
2. **Resources** – Định danh các nguồn dữ liệu (tệp, database, API). Client có thể `fetchResource` để lấy nội dung hoặc metadata.
3. **Tools** – Các hành động thực thi (ví dụ: `search_web`, `run_script`). Client gọi `invokeTool` với tham số cụ thể.
4. **Prompts** – Định dạng prompt mẫu được server cung cấp, giúp client xây dựng ngữ cảnh cho LLM.

#### Ví dụ luồng công việc

1. Host nhận yêu cầu người dùng: *"Tính số khách hàng đăng ký hôm nay"*.
2. Host quyết định cần truy vấn database → khởi tạo client cho `db_server`.
3. Client gửi `invokeTool` tới server với SQL.
4. Server thực thi truy vấn, trả về kết quả.
5. Client trả về dữ liệu cho host, host gửi prompt cho LLM.
6. LLM trả về câu trả lời cuối cùng cho người dùng.

### Đặc điểm nổi bật

- **Modular**: Mỗi server có thể triển khai một bộ khả năng riêng, dễ dàng mở rộng.
- **Scalable**: Nhiều client có thể kết nối tới một server, hoặc một client tới nhiều server.
- **Secure**: JSON‑RPC cho phép xác thực và mã hóa (khi sử dụng HTTP/HTTPS).
- **Cross‑platform**: Các nhà cung cấp LLM lớn (OpenAI, Google) đã hỗ trợ MCP, cho phép agent đa nền tảng.

> **Tham khảo**: Các nguồn nghiên cứu đã nêu chi tiết về giao diện, handshake, và khả năng mở rộng của MCP.

## Hướng dẫn triển khai MCP Server cơ bản

![Hướng dẫn triển khai MCP Server cơ bản](https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/802.11_Network_Architecture.svg/330px-802.11_Network_Architecture.svg.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### 1. Chuẩn bị môi trường
- **Python**: 3.10+ (hoặc 3.11) – dùng `uv` để chạy server.
- **Node.js**: 20+ – dùng `npm` để cài đặt SDK.
- **MCP SDK**: Cả hai ngôn ngữ đều có gói chính thức.

### 2. Tạo server Python
1. **Cài đặt SDK**
   ```bash
   pip install mcp-server
   ```
2. **Viết server** (`server.py`):
   ```python
   from mcp.server import MCPServer

   @MCPServer.tool()
   def add(a: int, b: int) -> int:
       """Add two numbers."""
       return a + b

   @MCPServer.resource("greeting://{name}")
   def greeting(name: str) -> str:
       return f"Hello, {name}!"

   if __name__ == "__main__":
       server = MCPServer("Demo Server", version="1.0.0")
       server.run()
   ```
   - `@MCPServer.tool()` khai báo tool `add` với schema tự động từ type hints.
   - `@MCPServer.resource()` khai báo resource có tham số `name`.
3. **Chạy server**
   ```bash
   uv run mcp dev server.py
   ```
   - `mcp dev` khởi động server qua **STDIO** và mở **MCP Inspector** ở `http://localhost:3000`.
   - Inspector cho phép xem danh sách tool/resource và thử gọi.

### 3. Tạo server TypeScript
1. **Khởi tạo dự án**
   ```bash
   mkdir mcp-ts && cd mcp-ts
   npm init -y
   npm install @modelcontextprotocol/sdk zod
   ```
2. **Viết server** (`src/index.ts`):
   ```ts
   import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
   import { z } from "zod";

   const server = new McpServer({ name: "Demo Server", version: "1.0.0" });

   server.tool(
     "add",
     z.object({ a: z.number(), b: z.number() }),
     ({ a, b }) => a + b
   );

   server.resource(
     "greeting://{name}",
     z.object({ name: z.string() }),
     ({ name }) => `Hello, ${name}!`
   );

   server.run();
   ```
3. **Chạy server**
   ```bash
   npx ts-node src/index.ts
   ```
   - Server chạy qua **STDIO**; mở `http://localhost:3000` để truy cập Inspector.

### 4. Kiểm thử với MCP Inspector
- Mở trình duyệt tới `http://localhost:3000`.
- Trên tab **Tools**, chọn `add` và nhập `a=5`, `b=7` → kết quả `12`.
- Trên tab **Resources**, nhập `greeting://Alice` → trả về `Hello, Alice!`.

### 5. Kết nối tới host
- Sử dụng SDK client (Python/TS) để gọi server qua HTTP:
  ```python
  from mcp.client import MCPClient
  client = MCPClient("http://localhost:3000")
  result = client.invoke_tool("add", {"a": 3, "b": 4})
  ```
- Hoặc dùng `mcp run` để expose server qua `streamable-http`:
  ```bash
  uv run mcp run server.py --transport streamable-http
  ```

### 6. Tóm tắt
- **Python**: 5 dòng khai báo tool + resource, chạy `mcp dev`.
- **TypeScript**: 10 dòng khai báo, chạy `ts-node`.
- **Inspector**: UI trực quan cho thử nghiệm.
- **Client**: Gọi dễ dàng từ host.

Như vậy, bạn đã có một MCP Server đơn giản, có thể mở rộng thêm tool/resource tùy ý và tích hợp ngay vào các ứng dụng AI Engineer.

## Đánh giá lợi ích và thách thức khi áp dụng MCP

![Đánh giá lợi ích và thách thức khi áp dụng MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/802.11_Network_Architecture.svg/330px-802.11_Network_Architecture.svg.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Lợi ích của MCP
- **Tính tương tác (interoperability)**
  - MCP định nghĩa giao diện chuẩn JSON‑RPC, cho phép các server, client và host giao tiếp một cách đồng nhất.
  - Khả năng **điều phối đa công cụ** (tool chaining) giúp LLM thực thi chuỗi hành động phức tạp mà không cần viết lại logic.
- **Modularity & mở rộng**
  - Mỗi server triển khai một *capability set* riêng; khi cần thêm tính năng mới chỉ cần triển khai server mới mà không ảnh hưởng tới host.
- **Cải thiện hiệu suất**
  - Bằng cách chia nhỏ các tác vụ (truy vấn DB, gọi API, thực thi script) vào các server chuyên biệt, ta giảm tải cho LLM và tận dụng tài nguyên tính toán tối ưu.
- **Bảo mật nâng cao**
  - JSON‑RPC hỗ trợ xác thực (token, JWT) và mã hóa (HTTPS), giúp ngăn chặn truy cập trái phép tới dữ liệu nhạy cảm.

### Thách thức khi triển khai MCP
| Thách thức | Mô tả | Ảnh hưởng |
|------------|-------|-----------|
| **Bảo mật** | Việc mở rộng số lượng server và client làm tăng bề mặt tấn công. Cần quản lý **credential** và **access control** chặt chẽ. | Rủi ro rò rỉ dữ liệu, truy cập trái phép. |
| **Hiệu năng** | Mỗi lần gọi `invokeTool` hoặc `fetchResource` đều là một cuộc gọi mạng, có thể gây latency cao nếu mạng không ổn định hoặc server quá tải. | Trễ phản hồi, giảm trải nghiệm người dùng. |
| **Quản lý phiên** | MCP yêu cầu trạng thái session, cần đồng bộ và lưu trữ context giữa client và server. | Khó khăn trong scaling, đặc biệt khi triển khai đa node. |
| **Khả năng mở rộng** | Khi số lượng client tăng, server phải chịu tải cao; cần cân bằng tải (load balancer) và khả năng tự động scale. | Chi phí infrastructure tăng, phức tạp quản lý. |
| **Tương thích phiên bản** | Các server có thể được cập nhật độc lập, dẫn đến sự khác biệt trong API hoặc format dữ liệu. | Lỗi runtime, cần hệ thống kiểm tra tính tương thích. |

## Tổng kết và tương lai của MCP

![Tổng kết và tương lai của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/802.11_Network_Architecture.svg/330px-802.11_Network_Architecture.svg.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

MCP đã chứng minh tiềm năng trong việc chuẩn hóa giao tiếp giữa các thành phần AI, mang lại lợi ích về **tính tương tác**, **modularity** và **hiệu suất**. Tuy nhiên, để khai thác tối đa, các AI Engineer cần chú trọng vào **bảo mật** (quản lý credential, token JWT), **độ trễ** (cân bằng tải, tối ưu latency) và **quản lý phiên** (đồng bộ context). Việc thiết lập các chính sách bảo mật chặt chẽ, triển khai load balancer và sử dụng các công cụ giám sát sẽ giúp giảm thiểu rủi ro và tăng tính ổn định. Trong tương lai, MCP có thể mở rộng sang các nền tảng đa ngôn ngữ và hỗ trợ các giao thức mới như gRPC, đồng thời tích hợp với các hệ thống quản lý dữ liệu lớn để đáp ứng nhu cầu AI quy mô doanh nghiệp. Đối với các engineer, việc nắm vững kiến trúc MCP và thực hành triển khai theo best‑practice sẽ là chìa khóa thành công để xây dựng các hệ thống AI thế hệ mới mạnh mẽ, an toàn và dễ bảo trì.
## Nguồn ảnh

- [Tổng quan về MCP và bối cảnh ra đời](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Phân tích kiến trúc kỹ thuật của MCP](https://commons.wikimedia.org/w/index.php?curid=148266300) — Anselm Vollprecht (cite source: „Und jetzt zus@mmen. Dein Einstieg ins Echtzeit-Musizieren über das Internet“ von Anselm Vollprecht), CC BY-SA 4.0
- [Hướng dẫn triển khai MCP Server cơ bản](https://commons.wikimedia.org/w/index.php?curid=168502265) — Superspritz, CC BY-SA 4.0
- [Đánh giá lợi ích và thách thức khi áp dụng MCP](https://commons.wikimedia.org/w/index.php?curid=168502265) — Superspritz, CC BY-SA 4.0
- [Tổng kết và tương lai của MCP](https://commons.wikimedia.org/w/index.php?curid=168502265) — Superspritz, CC BY-SA 4.0
