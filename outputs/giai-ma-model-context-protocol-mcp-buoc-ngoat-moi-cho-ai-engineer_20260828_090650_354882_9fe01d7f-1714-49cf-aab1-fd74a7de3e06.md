# Giải mã Model Context Protocol (MCP): Bước ngoặt mới cho AI Engineer

Trong kỷ nguyên phát triển bùng nổ của Trí tuệ Nhân tạo, việc kết nối các mô hình ngôn ngữ lớn (LLM) với dữ liệu và công cụ doanh nghiệp luôn là một bài toán hóc búa đối với các AI Engineer. Bài viết này sẽ cung cấp cái nhìn kỹ thuật chuyên sâu về Model Context Protocol (MCP), cách thức hoạt động của giao thức này, và cách áp dụng thực tế để xây dựng các ứng dụng AI mạnh mẽ, mạch lạc.

## Tổng quan về Model Context Protocol (MCP)

Model Context Protocol (MCP) là một chuẩn mở do Anthropic giới thiệu vào tháng 11 năm 2024 nhằm chuẩn hóa cách các mô hình ngôn ngữ lớn (LLM) tương tác với dữ liệu, công cụ và dịch vụ bên ngoài. MCP cung cấp một *ngôn ngữ* chung và tập hợp các quy tắc để:

- **Đọc dữ liệu** từ file, cơ sở dữ liệu hoặc API.
- **Thực thi chức năng** (function calls) trên các hệ thống khác.
- **Xử lý prompt** có ngữ cảnh động, cho phép LLM truy cập thông tin cập nhật thay vì chỉ dựa vào kiến thức cố định.

![Tổng quan về MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Động cơ thiết kế

MCP được phát triển để giải quyết “N×M integration problem” – khi số lượng ứng dụng AI (N) và nguồn dữ liệu/công cụ (M) tăng, việc viết mã kết nối riêng cho mỗi cặp trở nên không khả thi. Chuẩn MCP cho phép bất kỳ ứng dụng AI nào tuân thủ giao diện này kết nối với bất kỳ nguồn dữ liệu nào mà không cần viết code tùy chỉnh.

### Giải quyết vấn đề *context fragmentation*

Trong các luồng công việc AI, *context fragmentation* xảy ra khi AI mất liên kết với ngữ cảnh hiện tại của người dùng khi chuyển giữa các ứng dụng hoặc khi mở một phiên mới. MCP khắc phục điều này bằng cách:

1. **Đồng bộ ngữ cảnh**: Lưu trữ và chia sẻ trạng thái ngữ cảnh giữa các thành phần AI và nguồn dữ liệu.
2. **Tích hợp sâu**: Đưa AI vào tầng hệ điều hành hoặc ứng dụng, giúp nó nhận diện ngữ cảnh hoạt động (cửa sổ đang mở, tệp đang chỉnh sửa, v.v.) mà không cần người dùng mô tả lại.

Kết quả là AI trở thành một *đồng hành* thực sự, có thể truy cập dữ liệu mới nhất và thực hiện hành động mà không bị gián đoạn bởi việc mất ngữ cảnh.

### Khả năng mở rộng

Sau khi ra mắt, MCP đã được các nhà cung cấp lớn như OpenAI và Google DeepMind chấp nhận, chứng minh tính khả thi và lợi ích của một chuẩn mở trong cộng đồng AI.

---

**Tóm tắt**: MCP là một chuẩn mở giúp LLM kết nối linh hoạt với dữ liệu và công cụ bên ngoài, đồng thời khắc phục *context fragmentation* bằng cách đồng bộ ngữ cảnh và tích hợp sâu vào môi trường làm việc của người dùng.

## Kiến trúc Client‑Host‑Server của MCP

MCP được thiết kế theo mô hình **client‑server** với một lớp **host** trung gian để điều phối các tương tác. Các thành phần chính và vai trò của chúng được mô tả dưới đây:

| Thành phần | Vị trí trong hệ thống | Vai trò chính |
|------------|-----------------------|---------------|
| **Host** | Ứng dụng AI (ví dụ Claude Desktop) | Khởi tạo và quản lý các kết nối client, quyết định server phù hợp cho mỗi yêu cầu của LLM |
| **Client** | Chạy bên trong Host | Giao tiếp với server qua JSON‑RPC 2.0, thực hiện handshake, nhận danh sách khả năng, gửi yêu cầu và nhận phản hồi |
| **Server** | Dịch vụ bên ngoài (ví dụ database, workflow, API) | Cung cấp các capability (tính năng), thực thi yêu cầu và trả về kết quả, duy trì trạng thái context qua session |

![Kiến trúc kỹ thuật của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/802.11_Network_Architecture.svg/330px-802.11_Network_Architecture.svg.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### 1. Handshake và Negotiation
- Khi một Client kết nối tới Server, **handshake** được thực hiện: Server gửi phiên bản giao thức và danh sách *capabilities* mà nó hỗ trợ.
- Client nhận thông tin này, xác nhận phiên bản và chọn capability phù hợp với nhu cầu của LLM.

### 2. Transport Layer
- MCP hỗ trợ nhiều lớp truyền tải: **STDIO** (đối với server cục bộ), **Streamable HTTP** (đối với server từ xa) và **WebSocket**.
- Lớp này quyết định cách dữ liệu được gửi/nhận giữa Client và Server nhưng không ảnh hưởng đến logic giao thức.

### 3. JSON‑RPC 2.0
- MCP dựa trên JSON‑RPC 2.0 làm cơ sở truyền dữ liệu. Mỗi yêu cầu/đáp ứng được mã hóa dưới dạng JSON, bao gồm `id`, `method`, `params` và `result`/`error`.
- **Notification** được sử dụng khi không cần phản hồi (ví dụ: cập nhật context).

### 4. Context Management
- Server duy trì trạng thái *context* trong suốt session. Khi một yêu cầu được gửi, Server có thể truy cập context đã lưu từ các yêu cầu trước, giúp tránh *context fragmentation*.
- Host và Client làm việc cùng nhau để đồng bộ context giữa LLM và Server.

### 5. Flow Example
1. **Host** nhận yêu cầu từ LLM: *"Tìm số lượng khách hàng đăng ký hôm nay"*.
2. Host quyết định gửi yêu cầu tới **Analytics MCP Server**.
3. **Client** tạo request JSON‑RPC `get_customer_count` và gửi tới Server.
4. Server thực thi truy vấn database, trả về kết quả JSON.
5. Client chuyển kết quả cho Host, Host gửi back to LLM.

### 6. Định nghĩa Capabilities
- Mỗi Server khai báo một tập hợp **capabilities** (ví dụ: `prompts/list`, `create_issue`, `get_test_report`).
- Client có thể lặp qua danh sách này để lựa chọn hành động phù hợp.

> Tham khảo: *MCP architecture explained: Structure and key components* (Celigo) và *Architecture overview* (modelcontextprotocol.io).

## Sơ đồ luồng dữ liệu

```
+----------------+      +----------------+      +----------------+
|     Host       |<---->|     Client     |<---->|     Server     |
+----------------+      +----------------+      +----------------+
        |                       |                       |
        | 1. LLM request        |                       |
        |---------------------->|                       |
        |                       | 2. Initialize &       |
        |                       |    capability list   |
        |                       |<----------------------|
        |                       | 3. Send JSON‑RPC      |
        |                       |    request            |
        |                       |---------------------->|
        |                       |                       | 4. Execute & return |
        |                       |                       |<----------------------|
        | 5. Forward result     |                       |
        |<----------------------|                       |
```

## Tóm tắt kiến trúc
MCP cung cấp một kiến trúc rõ ràng, nơi Host điều phối, Client giao tiếp qua JSON‑RPC, và Server cung cấp các capability. Transport layer linh hoạt cho phép triển khai cục bộ hoặc từ xa mà không thay đổi logic giao thức. Việc duy trì context qua session giúp giảm *context fragmentation* và làm cho LLM có thể truy cập dữ liệu mới nhất một cách liên tục.

## Use cases và triển khai thực tế

![Use cases và triển khai thực tế](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### 1. Kết nối LLM với Cơ sở dữ liệu nội bộ

#### Mô tả
MCP cho phép một LLM như Claude truy cập trực tiếp tới cơ sở dữ liệu nội bộ (ví dụ PostgreSQL, MongoDB) thông qua một *MCP server* triển khai logic truy vấn. LLM gửi yêu cầu `sql/query` hoặc `nosql/get` và nhận kết quả dưới dạng JSON.

#### Hướng dẫn triển khai
1. **Tạo MCP server**: Sử dụng SDK `mcp.server.fastmcp` (Python) hoặc `mcp-go` (Go). Định nghĩa capability `db/query`.
2. **Kết nối tới DB**: Trong handler, dùng thư viện chuẩn (psycopg2, pymongo) để thực thi truy vấn.
3. **Xử lý context**: Server lưu `session_id` để giữ trạng thái truy vấn liên quan (ví dụ, lọc theo user).
4. **Đăng ký server**: Host (Claude Desktop) đăng ký server qua `mcp://localhost:8080`.
5. **Gọi từ LLM**: LLM viết prompt: "Tìm số lượng khách hàng đăng ký hôm nay" → Host chuyển thành JSON‑RPC `db/query` với SQL `SELECT COUNT(*) FROM customers WHERE signup_date = CURRENT_DATE`.

#### Lợi ích
- Tránh trích xuất dữ liệu qua API trung gian.
- Giữ dữ liệu an toàn trong mạng nội bộ.
- Tăng tốc độ phản hồi nhờ truy vấn trực tiếp.

---

### 2. Tích hợp MCP với IDE (VS Code)

#### Mô tả
MCP được dùng làm *bridge* giữa LLM và các công cụ phát triển như VS Code. LLM có thể tạo, sửa, chạy code, hoặc truy cập thông tin dự án mà không cần plugin riêng.

#### Hướng dẫn triển khai
1. **MCP server**: Viết server Node.js sử dụng `mcp-node` để khai báo capabilities `code/create`, `code/modify`, `code/run`.
2. **Kết nối với VS Code**: Sử dụng API `vscode.commands.executeCommand` trong handler để thực hiện thao tác.
3. **Host**: Claude Desktop được cấu hình để tự động gọi server khi nhận prompt "Tạo hàm tính tổng".
4. **Context**: Server lưu trạng thái file mở, commit history để LLM có thể tham chiếu.

#### Lợi ích
- Đơn giản hoá workflow: LLM viết code, chạy test, commit ngay.
- Giảm thiểu plugin phức tạp; MCP làm trung gian.
- Hỗ trợ multi‑language và multi‑framework.

---

### 3. Kết nối MCP với API bên thứ ba (Azure, GitHub, Web Scraping)

#### Mô tả
MCP cho phép LLM gọi bất kỳ API bên thứ ba nào thông qua một *MCP server* trung gian, chuyển đổi JSON‑RPC thành HTTP/REST hoặc GraphQL.

#### Hướng dẫn triển khai
1. **Server wrapper**: Viết server Python sử dụng `mcp.server.fastmcp` với capability `http/get`, `http/post`.
2. **Mapping**: Trong handler, ánh xạ `method` và `params` sang endpoint, headers, body.
3. **Authentication**: Lưu token trong context; server tự động thêm header `Authorization`.
4. **Host**: Claude Desktop gọi `http/get` khi nhận prompt "Lấy danh sách repo GitHub của tôi".
5. **Ví dụ thực tế**: Cisco blogs cho thấy MCP được dùng để quản lý CI/CD, Kubernetes APIs, và các dịch vụ observability.

#### Lợi ích
- Tránh viết wrapper riêng cho từng dịch vụ.
- Tích hợp nhanh chóng với API mới.
- Duy trì một giao thức chuẩn, giảm lỗi.

---

## Tổng kết use cases
Ba use case trên minh họa cách MCP chuyển đổi LLM thành một *agent* có thể tương tác với dữ liệu nội bộ, công cụ phát triển và API bên ngoài mà không cần viết plugin phức tạp. Các server MCP giữ nguyên logic nghiệp vụ, đồng thời cung cấp context management giúp LLM duy trì trạng thái qua session.

## Kết luận và tương lai

![Kết luận và tương lai](https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Programmers.jpg/330px-Programmers.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

## Kết luận
MCP đã chứng minh khả năng chuyển đổi LLM thành một *agent* linh hoạt, có thể giao tiếp với các nguồn dữ liệu nội bộ, công cụ phát triển và API bên thứ ba mà không cần viết plugin riêng. Nhờ cơ chế **context management** và **capability registration**, MCP giúp:

- Giữ an toàn dữ liệu trong mạng nội bộ.
- Đơn giản hoá workflow phát triển phần mềm.
- Tích hợp nhanh chóng với các dịch vụ mới.

### Tác động tới AI Engineering
- **Tăng năng suất**: Các engineer có thể nhờ LLM thực hiện truy vấn, viết code, chạy test và commit trong một lần tương tác.
- **Giảm độ phức tạp**: Thay vì quản lý nhiều wrapper API, MCP cung cấp một giao thức chuẩn.
- **Mở rộng linh hoạt**: Khi một dịch vụ mới ra đời, chỉ cần triển khai một MCP server mới với capability tương ứng.

## Tương lai của MCP
1. **Chuẩn công nghiệp** – MCP có thể trở thành một tiêu chuẩn cho việc kết nối LLM với hệ sinh thái công cụ, tương tự như OpenAPI cho REST.
2. **Mở rộng capabilities** – Các nhà phát triển sẽ định nghĩa thêm các capability như `ml/model/train`, `ml/model/evaluate`, `ml/model/deploy` để hỗ trợ vòng đời ML end‑to‑end.
3. **Tích hợp AI‑as‑a‑Service** – Các nhà cung cấp cloud có thể triển khai MCP server như một dịch vụ, cho phép khách hàng gọi LLM trực tiếp tới tài nguyên của họ.
4. **Tăng cường bảo mật** – Sử dụng xác thực token, mã hoá truyền dữ liệu và audit trail trong context để đáp ứng các tiêu chuẩn bảo mật doanh nghiệp.

Nhìn chung, MCP mở ra một mô hình kiến trúc mới cho AI Engineering, nơi LLM không chỉ là công cụ hỗ trợ mà còn là *đồng nghiệp* thực thụ trong quy trình phát triển phần mềm và dữ liệu.
## Nguồn ảnh

- [Tổng quan về MCP](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Kiến trúc kỹ thuật của MCP](https://commons.wikimedia.org/w/index.php?curid=168502265) — Superspritz, CC BY-SA 4.0
- [Use cases và triển khai thực tế](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Kết luận và tương lai](https://commons.wikimedia.org/w/index.php?curid=125320432) — Lbronn, CC BY-SA 4.0
