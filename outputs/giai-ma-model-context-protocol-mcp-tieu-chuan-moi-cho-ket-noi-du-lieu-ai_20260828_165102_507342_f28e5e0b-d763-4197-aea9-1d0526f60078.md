# Giải mã Model Context Protocol (MCP): Tiêu chuẩn mới cho kết nối dữ liệu AI

Trong kỷ nguyên phát triển mạnh mẽ của các ứng dụng Trí tuệ Nhân tạo, việc kết nối các mô hình ngôn ngữ lớn (LLM) với các nguồn dữ liệu và công cụ bên ngoài luôn là một thử thách lớn về kỹ thuật. Đối với các AI Engineer, việc xây dựng các custom integration riêng biệt cho từng cặp ứng dụng và nguồn dữ liệu dẫn đến sự phức tạp và lãng phí tài nguyên. Bài viết này sẽ phân tích chi tiết về Model Context Protocol (MCP), kiến trúc kỹ thuật cũng như hướng dẫn triển khai thực tế giúp tối ưu hóa quy trình phát triển ứng dụng AI.

## Tổng quan về Model Context Protocol (MCP)

Model Context Protocol (MCP) là một chuẩn mở được Anthropic giới thiệu vào tháng 11 năm 2024, nhằm chuẩn hoá cách các mô hình ngôn ngữ lớn (LLM) tương tác với dữ liệu và công cụ bên ngoài. MCP được thiết kế để giải quyết **vấn đề “M×N integration problem”**: khi số lượng ứng dụng AI (M) và nguồn dữ liệu/công cụ (N) tăng, việc xây dựng một kết nối riêng cho mỗi cặp trở nên không khả thi. Thay vì cần M×N kết nối tùy chỉnh, MCP cho phép mỗi ứng dụng AI và mỗi công cụ chỉ cần triển khai một giao diện duy nhất, giảm số kết nối xuống M+N.

![Tổng quan về Model Context Protocol](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Kiến trúc cơ bản

MCP xây dựng trên JSON‑RPC 2.0, cung cấp một ngôn ngữ chuẩn để LLM:
- **Đọc file**: `read_file` – truy cập nội dung tài liệu.
- **Thực thi hàm**: `invoke_function` – gọi API hoặc thực thi lệnh.
- **Xử lý prompt ngữ cảnh**: `context_prompt` – truyền dữ liệu thời gian thực vào prompt.

Các ứng dụng AI triển khai một **MCP Client** để gửi yêu cầu theo định dạng chuẩn, trong khi các dịch vụ dữ liệu hoặc công cụ triển khai một **MCP Server** để hiểu và trả lời. Khi một AI muốn truy cập một file hoặc gọi một API, nó chỉ cần gửi một yêu cầu JSON‑RPC; bất kỳ dịch vụ nào hỗ trợ MCP đều có thể hiểu và thực thi.

### Mục tiêu và lợi ích
- **Chuẩn hoá**: Loại bỏ sự đa dạng các connector riêng biệt, giảm thiểu công sức phát triển.
- **Tương thích**: Các ứng dụng AI mới chỉ cần học MCP; các công cụ mới chỉ cần triển khai MCP Server.
- **Bảo mật**: MCP hỗ trợ xác thực và mã hoá, giúp bảo vệ dữ liệu khi truyền giữa AI và nguồn dữ liệu.
- **Giảm hallucination**: Khi AI có thể truy cập dữ liệu thời gian thực, khả năng sai lệch thông tin giảm đáng kể.

Nhờ MCP, các AI Engineer có thể nhanh chóng kết nối mô hình với các kho dữ liệu, API, và hệ thống quản lý mà không cần viết mã tùy chỉnh cho từng trường hợp, mở ra khả năng tự động hoá và tích hợp sâu hơn trong các ứng dụng thực tế.

Để hiểu rõ hơn về cách thức vận hành bên dưới của tiêu chuẩn này, chúng ta sẽ cùng đi sâu vào kiến trúc kỹ thuật của MCP.

## Kiến trúc kỹ thuật của MCP

MCP được thiết kế theo mô hình **client‑host‑server** với ba thành phần chính: **host**, **client** và **server**. Mỗi thành phần có vai trò riêng biệt nhưng cùng làm việc để cho phép một LLM truy cập dữ liệu và công cụ bên ngoài một cách chuẩn hóa.

![Kiến trúc kỹ thuật của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Client-Server.png/330px-Client-Server.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### 1. Host (ứng dụng AI)
- Là giao diện người dùng cuối (ví dụ: Claude Desktop, IDE, trình duyệt). 
- Tạo một hoặc nhiều **MCP client** để kết nối tới các **MCP server**.
- Xử lý yêu cầu người dùng, quyết định khả năng cần thiết và chuyển giao cho client.

### 2. Client (đại diện của host)
- Chỉ thực hiện giao tiếp theo giao thức JSON‑RPC 2.0 với một server cụ thể.
- Mỗi client duy trì một kết nối **dedicated** tới server, thường là qua **STDIO** cho server cục bộ hoặc **Streamable HTTP** cho server remote.
- Khi client nhận được yêu cầu từ host, nó đóng gói thành một **JSON‑RPC request** và gửi tới server.

### 3. Server (công cụ/điện năng ngoại vi)
- Cung cấp một tập hợp các **capabilities** (ví dụ: `read_file`, `invoke_function`, `context_prompt`).
- Khi client kết nối lần đầu, server thực hiện **handshake**: gửi phiên bản giao thức và danh sách khả năng.
- Khi nhận request, server thực thi hành động (ví dụ truy vấn database, đọc file) và trả về kết quả dưới dạng JSON‑RPC response.

### Luồng dữ liệu chi tiết
1. **Handshake**: Client kết nối tới server, server trả về `protocol_version` và `capabilities`.
2. **Capability negotiation**: Client lưu trữ danh sách khả năng, host quyết định sử dụng capability nào.
3. **Request–response**:
   - Host gửi yêu cầu tới client (ví dụ: `invoke_function` với tham số `function_name`).
   - Client chuyển request thành JSON‑RPC, gửi tới server.
   - Server thực thi, trả về kết quả.
   - Client chuyển response trở lại host.
4. **Notifications**: Khi không cần trả lời (ví dụ gửi log), server có thể gửi `notification` mà client không cần phản hồi.

### Giao thức truyền tải
- **STDIO**: Dùng cho server cục bộ, cho phép client và server chạy trên cùng một tiến trình.
- **Streamable HTTP**: Dùng cho server remote, hỗ trợ truyền dữ liệu lớn và streaming.

Sau khi đã nắm vững cấu trúc lý thuyết và luồng dữ liệu của hệ thống, bước tiếp theo là tiến hành cài đặt thực tế. Dưới đây là hướng dẫn chi tiết cách xây dựng một MCP Server cơ bản bằng Python.

## Hướng dẫn triển khai MCP Server cơ bản

![Hướng dẫn triển khai MCP Server cơ bản](https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Client-Server.png/330px-Client-Server.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### 1. Chuẩn bị môi trường

```bash
# Cài đặt Python 3.10+ và pip
python -m venv venv
source venv/bin/activate

# Cài đặt FastMCP (SDK MCP Python)
pip install fastmcp
```

FastMCP là thư viện chính để xây dựng MCP server trong Python, được đề cập trong nguồn *Building and deploying a Python MCP server with FastMCP*.

### 2. Khởi tạo server

```python
# file: demo_server.py
from fastmcp import MCPServer

# Tạo một server với tên mô tả
mcp = MCPServer("DemoServer")
```

- `MCPServer` nhận một tên, dùng để nhận diện trong MCP Inspector.
- Khi server khởi động, nó sẽ thực hiện handshake tự động, gửi `protocol_version` và danh sách `capabilities` cho client.

### 3. Định nghĩa tool

Tools là các hàm được gắn `@mcp.tool()`.

```python
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
```

- Tham số và kiểu trả về được khai báo bằng type hints.
- Docstring sẽ được chuyển thành mô tả capability trong MCP.

### 4. Định nghĩa resource

Resources là các endpoint có thể truy cập qua URL mẫu.

```python
@mcp.resource("greeting://{name}")
def greeting(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"
```

- URL mẫu `greeting://{name}` cho phép client gọi `mcp.invoke("greeting://Alice")`.

### 5. Khởi chạy server

```bash
# Chạy server trong chế độ phát triển
uv run mcp dev demo_server.py
```

- Lệnh `mcp dev` được hỗ trợ bởi FastMCP, tự động mở MCP Inspector tại `http://localhost:8000`.
- Bạn có thể thử gọi tool `add` và resource `greeting` từ Inspector.

### 6. Kiểm thử bằng MCP Inspector

1. Mở `http://localhost:8000`.
2. Chọn *New Request* → *Invoke Tool*.
3. Gõ `add` và truyền tham số `a=5`, `b=7`.
4. Nhận kết quả `12`.

### 7. Tóm tắt các thành phần chính

| Thành phần | Vai trò | Ví dụ |
|------------|---------|-------|
| `MCPServer` | Khởi tạo server, quản lý capabilities | `MCPServer("DemoServer")` |
| `@mcp.tool()` | Định nghĩa hàm có thể được gọi | `def add(a: int, b: int)` |
| `@mcp.resource()` | Định nghĩa endpoint truy cập qua URL mẫu | `def greeting(name: str)` |
| `uv run mcp dev` | Chạy server và mở MCP Inspector | `uv run mcp dev demo_server.py` |

Như vậy, với chỉ vài dòng code và một số cấu hình, bạn đã có một MCP server đơn giản, có thể mở rộng bằng cách thêm nhiều tool và resource khác.

## Đánh giá lợi ích và tương lai của MCP

![Đánh giá lợi ích và tương lai của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Cloud_computing.svg/330px-Cloud_computing.svg.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

Model Context Protocol đã được thiết kế để chuẩn hoá cách các mô hình AI chia sẻ và truy cập ngữ cảnh, tài nguyên và công cụ. Dưới đây là phân tích sâu về tác động thực tiễn, khả năng thay thế các custom integration và triển vọng chuẩn hoá context trong tương lai.

### 1. Lợi ích thực tiễn

| Lợi ích | Mô tả | Ảnh hưởng cho dự án |
|---------|-------|----------------------|
| **Tính nhất quán** | MCP định nghĩa một giao diện chuẩn cho việc truyền dữ liệu ngữ cảnh (context) giữa các mô hình và hệ thống. | Giảm thiểu lỗi do định dạng dữ liệu khác nhau, dễ dàng tích hợp nhiều mô hình. |
| **Tính mở rộng** | Các tool và resource được khai báo bằng decorator, có thể được đăng ký và phát hiện tự động qua MCP Inspector. | Dễ dàng mở rộng mô hình mà không cần viết lại code client. |
| **Hiệu suất** | Giao thức nhẹ, sử dụng HTTP/JSON, cho phép thực thi nhanh trên các mạng nội bộ. | Giảm độ trễ khi gọi các tool hoặc resource. |
| **Bảo mật** | MCP hỗ trợ xác thực token và quyền truy cập (ACL) cho từng capability. | Kiểm soát truy cập tới các tài nguyên nhạy cảm. |

### 2. Khả năng thay thế custom integration

Trong nhiều dự án hiện tại, các engineer thường xây dựng custom adapters để truyền dữ liệu ngữ cảnh giữa mô hình và backend. MCP cung cấp:

1. **Định nghĩa chuẩn**: Thay vì tự viết JSON schema, MCP tự động sinh schema từ type hints.
2. **Khởi tạo server**: FastMCP cho phép khởi tạo server chỉ với vài dòng code, giảm thời gian triển khai.
3. **Khả năng tương thích**: Các client MCP (ví dụ: LangChain, LlamaIndex) có thể gọi trực tiếp các tool/resource mà không cần custom wrapper.
4. **Quản lý phiên**: MCP hỗ trợ session ID, giúp theo dõi lịch sử ngữ cảnh giữa các lần gọi.

Vì vậy, trong hầu hết các trường hợp, MCP có thể thay thế hoàn toàn các custom integration, đặc biệt là khi dự án cần hỗ trợ nhiều mô hình và dịch vụ.

### 3. Tương lai của chuẩn hoá context

- **Sự chấp nhận rộng rãi**: Các công ty lớn như OpenAI, Anthropic đang thử nghiệm giao thức tương tự để chia sẻ context giữa mô hình.
- **Mở rộng tính năng**: MCP có thể mở rộng để hỗ trợ streaming context, metadata tags, và versioning.
- **Ecosystem**: Sự phát triển của FastMCP và các client SDK sẽ tạo ra một ecosystem phong phú, giảm rào cản cho các developer.
- **Chuẩn công nghiệp**: Nếu MCP được chuẩn hoá bởi các tổ chức như IETF hoặc ISO, nó sẽ trở thành tiêu chuẩn công nghiệp cho AI services.

## Kết luận

MCP mang lại lợi ích rõ rệt về tính nhất quán, mở rộng và bảo mật cho các dự án AI. Khả năng thay thế custom integration làm giảm chi phí phát triển và bảo trì. Với xu hướng chuẩn hoá context ngày càng tăng, MCP có tiềm năng trở thành tiêu chuẩn công nghiệp, giúp các AI Engineer tập trung vào việc xây dựng logic kinh doanh thay vì quản lý giao thức.

**Khuyến nghị**: Đối với các dự án mới, nên bắt đầu với MCP để tận dụng lợi ích ngay từ giai đoạn thiết kế. Đối với dự án hiện có, cân nhắc chuyển đổi dần dần bằng cách xây dựng adapter MCP cho các service hiện tại.
## Nguồn ảnh

- [Tổng quan về Model Context Protocol](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Kiến trúc kỹ thuật của MCP](https://commons.wikimedia.org/w/index.php?curid=148266300) — Anselm Vollprecht (cite source: „Und jetzt zus@mmen. Dein Einstieg ins Echtzeit-Musizieren über das Internet“ von Anselm Vollprecht), CC BY-SA 4.0
- [Hướng dẫn triển khai MCP Server cơ bản](https://commons.wikimedia.org/w/index.php?curid=148266300) — Anselm Vollprecht (cite source: „Und jetzt zus@mmen. Dein Einstieg ins Echtzeit-Musizieren über das Internet“ von Anselm Vollprecht), CC BY-SA 4.0
- [Đánh giá lợi ích và tương lai của MCP](https://commons.wikimedia.org/w/index.php?curid=6080417) — Sam Johnston, CC BY-SA 3.0
