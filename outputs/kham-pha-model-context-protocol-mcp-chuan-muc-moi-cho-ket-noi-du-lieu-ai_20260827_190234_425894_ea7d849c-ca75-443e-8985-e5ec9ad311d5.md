# Khám phá Model Context Protocol (MCP): Chuẩn mực mới cho kết nối dữ liệu AI

Trong kỷ nguyên phát triển mạnh mẽ của trí tuệ nhân tạo, việc tích hợp các mô hình ngôn ngữ lớn (LLM) với các nguồn dữ liệu và hệ thống bên ngoài luôn là một thử thách lớn đối với các AI Engineer. Model Context Protocol (MCP) ra đời như một tiêu chuẩn mở nhằm giải quyết bài toán này, mang lại một giao diện đồng bộ, an toàn và dễ mở rộng. Bài viết này sẽ cung cấp cái nhìn kỹ thuật sâu sắc về kiến trúc, cách thức hoạt động và hướng dẫn triển khai MCP trong các hệ thống AI thực tế.

## Tổng quan và định nghĩa về MCP

MCP (Model Context Protocol) là một tiêu chuẩn mở do Anthropic giới thiệu vào tháng 11/2024 nhằm **đồng bộ hóa cách các mô hình ngôn ngữ lớn (LLM) tiếp cận và tương tác với dữ liệu, công cụ và dịch vụ bên ngoài**. Thay vì phải viết mã kết nối riêng cho từng nguồn dữ liệu, MCP cung cấp một giao diện chung, giúp các ứng dụng AI có thể **định danh, truy cập và thực thi các chức năng** của bất kỳ dịch vụ nào mà không cần tùy chỉnh riêng.

![Tổng quan và định nghĩa về MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Client-Server.png/330px-Client-Server.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Kiến trúc chính
MCP tuân theo mô hình client–server:
- **Host**: Ứng dụng AI (ví dụ một LLM-powered agent) tạo ra nhiều *session* MCP client, mỗi session duy trì một kênh JSON‑RPC trạng thái.
- **Client**: Định nghĩa các nguyên tắc như *roots*, *sampling* và *elicitation* để gửi yêu cầu tới server.
- **Server**: Cung cấp các tài nguyên (resources), công cụ (tools) và prompt. Server có thể là bất kỳ dịch vụ dữ liệu nào – từ cơ sở dữ liệu nội bộ, API công nghiệp, tới các công cụ lập trình.

Khi một LLM cần truy cập dữ liệu mới, nó gửi một *prompt* qua MCP, server trả về dữ liệu hoặc thực thi hàm, và LLM tiếp tục xử lý. Tất cả giao tiếp diễn ra qua JSON‑RPC, đảm bảo tính **an toàn, trạng thái và khả năng mở rộng**.

### Tại sao Anthropic giới thiệu MCP?
- **N×M integration problem**: Khi số lượng ứng dụng AI (N) và nguồn dữ liệu/công cụ (M) tăng, việc xây dựng kết nối tùy chỉnh cho từng cặp trở nên không thể quản lý.
- **Context silo**: Các mô hình LLM thường bị giới hạn bởi kiến thức tĩnh trong mô hình; MCP cho phép chúng truy cập dữ liệu thời gian thực, giảm *information silos*.
- **Interoperability**: MCP làm cho các nhà phát triển có thể viết một lần, triển khai nhiều lần – bất kỳ LLM nào hỗ trợ MCP đều có thể kết nối với bất kỳ dịch vụ nào tuân thủ giao diện.

MCP đã được chấp nhận rộng rãi bởi các nhà cung cấp AI lớn như OpenAI và Google DeepMind, chứng minh tính **định hướng công nghiệp** và khả năng **đồng bộ hóa hệ sinh thái AI**.

## Cấu trúc kỹ thuật của MCP

Tiếp nối tổng quan về giao thức, chúng ta hãy đi sâu vào chi tiết kiến trúc và luồng dữ liệu của MCP trong hệ thống.

![Cấu trúc kỹ thuật của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Client-Server.png/330px-Client-Server.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Kiến trúc Client‑Host‑Server của MCP
MCP được thiết kế theo mô hình **client‑server** với ba thành phần chính: **Host**, **Client** và **Server**.

- **Host** là ứng dụng AI (ví dụ Claude Desktop, IDE plugin…) mà người dùng tương tác. Host tạo ra một hoặc nhiều **MCP client** để kết nối tới các **MCP server**.
- **Client** là thành phần trong Host chịu trách nhiệm duy trì kết nối tới một MCP server cụ thể và quản lý luồng dữ liệu JSON‑RPC. Mỗi client giữ một kênh trạng thái riêng biệt, cho phép Host đồng thời giao tiếp với nhiều server.
- **Server** là dịch vụ bên ngoài (cơ sở dữ liệu, API công nghiệp, công cụ lập trình…) cung cấp các tài nguyên (resources) và công cụ (tools) theo giao diện MCP.

### Luồng dữ liệu
1. **Khởi tạo** – Host khởi tạo một MCP client, client mở kết nối tới server (STDIO cho server cục bộ, HTTP/2 streamable cho server từ xa).
2. **Yêu cầu context** – Khi LLM cần dữ liệu, Host gửi *prompt* qua client. Client chuyển yêu cầu này thành một cuộc gọi JSON‑RPC tới server.
3. **Trả về** – Server trả về dữ liệu (resource) hoặc kết quả thực thi tool. Client nhận phản hồi, chuyển tiếp tới Host.
4. **Tích hợp** – Host nhận kết quả, chèn vào ngữ cảnh của LLM hoặc hiển thị cho người dùng.

> **Lưu ý**: Tất cả các giao tiếp đều được đóng gói trong JSON‑RPC, giúp bảo đảm tính **độ an toàn** (không có side‑effects khi truy cập tài nguyên) và **độ mở rộng** (một host có thể kết nối tới nhiều server đồng thời).

### Giao thức truyền tải
- **STDIO transport**: Dùng cho server cục bộ, thường phục vụ một client duy nhất.
- **Streamable HTTP transport**: Dùng cho server từ xa, cho phép nhiều client đồng thời kết nối thông qua HTTP/2 streams.

### Tài nguyên và công cụ
- **Resources**: Đọc‑chỉ, được định danh bằng URI (ví dụ `file:///path`, `config://app/settings`). Chúng cung cấp dữ liệu cấu trúc cho LLM.
- **Tools**: Có thể thực thi hành động (ví dụ gọi API, ghi file). LLM quyết định khi nào gọi tool dựa vào ngữ cảnh.

Cấu trúc này cho phép **độ mô-đun cao**: Host có thể mở rộng thêm các server mới mà không cần thay đổi mã nguồn Host. Các tài nguyên và công cụ có thể được kết hợp giữa các server khác nhau để tạo ra khả năng thực thi linh hoạt.

### Sơ đồ luồng dữ liệu (mô tả bằng text)
```
[Host] ──► [Client] ──► [MCP Server]
   │          │          │
   │          │          │
   │          │          └─► (GET/POST resource/tool)
   │          │
   │          └─► (JSON‑RPC response)
   │
   └─► (Integrate result into LLM context)
```

Cấu trúc này đã được mô tả chi tiết trong tài liệu chính thức của MCP (Architecture overview) và các nguồn học từ Hugging Face và Stainless MCP Portal.

## Lợi ích và ứng dụng thực tế của MCP đối với AI Engineer

Việc áp dụng chuẩn hóa này mang lại nhiều giá trị thiết thực trong quá trình phát triển các hệ thống AI tích hợp dữ liệu.

![Lợi ích và ứng dụng thực tế của MCP đối với AI Engineer](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Lợi ích chính khi áp dụng MCP

| Lợi ích | Mô tả | Tác động thực tiễn |
|---------|-------|---------------------|
| **Mở rộng theo mô-đun** | MCP cho phép Host kết nối tới nhiều Server mà không cần thay đổi mã nguồn Host. | Tăng khả năng mở rộng nhanh chóng khi thêm công cụ mới. |
| **Tiết kiệm thời gian triển khai** | Theo EnDevSols, MCP có thể được prototyped trong 7‑10 ngày, trong khi tích hợp tùy chỉnh mất 4‑8 tuần cho mỗi công cụ. | Giảm thời gian đưa sản phẩm ra thị trường. |
| **Tiêu chuẩn bảo mật và quản trị** | MCP cung cấp cơ chế đồng ý (consent) và kiểm soát mẫu (sampling controls) chuẩn, đồng thời hỗ trợ RBAC và audit logs. | Giảm rủi ro bảo mật và đáp ứng yêu cầu tuân thủ. |
| **Giảm rủi ro vendor lock‑in** | MCP là chuẩn mở, cho phép chuyển đổi giữa các nhà cung cấp mà không phá vỡ hệ thống. | Tăng tính linh hoạt chiến lược công nghệ. |
| **Tăng tính tái sử dụng** | Các tài nguyên và công cụ được mô tả bằng URI và schema chuẩn, dễ dàng chia sẻ giữa các dự án. | Nâng cao hiệu suất làm việc nhóm và giảm lặp lại công việc. |

### Ví dụ use‑case cụ thể

1. **Kết nối tới cơ sở dữ liệu nội bộ**
   - *MCP*: Định nghĩa một `resource` với URI `db://sales/transactions`. LLM có thể truy vấn dữ liệu bằng một lệnh JSON‑RPC.
   - *Custom*: Viết wrapper riêng cho từng API, phải bảo trì mã nguồn riêng.
   - *Kết quả*: MCP cho phép thay đổi backend (ví dụ chuyển sang PostgreSQL) mà không ảnh hưởng tới Host.

2. **Gọi API bên ngoài với kiểm soát rủi ro**
   - *MCP*: Định nghĩa `tool` `api://weather/getForecast` với schema đầu vào/đầu ra, đồng thời áp dụng RBAC và audit log.
   - *Custom*: Cần viết logic kiểm tra quyền và ghi log thủ công.
   - *Kết quả*: MCP giảm thiểu lỗi cấu hình và tăng tính minh bạch cho các hành động có rủi ro.

3. **Tích hợp công cụ phát triển**
   - *MCP*: Định nghĩa `tool` `git://commit` để thực thi lệnh git từ LLM.
   - *Custom*: Phải xây dựng wrapper cho từng lệnh git.
   - *Kết quả*: MCP cho phép mở rộng nhanh chóng với các công cụ mới như Docker, Kubernetes.

Như vậy, MCP không chỉ đơn thuần là một giao thức; nó là nền tảng giúp AI Engineer xây dựng hệ sinh thái công cụ linh hoạt, an toàn và dễ bảo trì, giảm thiểu thời gian triển khai và rủi ro liên quan đến tích hợp tùy chỉnh.

## Hướng dẫn triển khai cơ bản

Dưới đây là các bước cấu hình và xây dựng một MCP server đơn giản để tích hợp vào hệ thống của bạn.

![Hướng dẫn triển khai cơ bản](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Bước 1: Chuẩn bị môi trường
- Cài đặt Python 3.10+ (hoặc Node.js nếu dùng SDK JavaScript). 
- Cài đặt MCP SDK:
```bash
pip install mcp
# hoặc
npm install @modelcontextprotocol/sdk
```

### Bước 2: Tạo server MCP đơn giản (Python)
1. Tạo file `server.py`:
```python
from mcp import MCPServer

mcp = MCPServer("DemoServer")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@mcp.resource("greeting://{name}")
def greeting(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()
```
2. Chạy server:
```bash
uv run server.py
```
Server sẽ lắng nghe trên `http://localhost:8000`.

### Bước 3: Kết nối nguồn dữ liệu đơn giản
Giả sử bạn muốn truy cập một cơ sở dữ liệu SQLite.
1. Cài đặt thư viện:
```bash
pip install sqlite3
```
2. Thêm tool để truy vấn:
```python
import sqlite3

conn = sqlite3.connect("example.db")

@mcp.tool()
def query_sales(start_date: str, end_date: str) -> list:
    """Truy vấn doanh thu trong khoảng thời gian."""
    cur = conn.cursor()
    cur.execute(
        "SELECT date, amount FROM sales WHERE date BETWEEN ? AND ?",
        (start_date, end_date),
    )
    return cur.fetchall()
```

### Bước 4: Kiểm thử với LLM
- Sử dụng một client MCP (ví dụ `mcp-client` CLI) hoặc tích hợp vào Claude:
```bash
mcp-client call add --a 5 --b 7
# Kết quả: 12
```
- Truy cập resource:
```bash
curl http://localhost:8000/greeting/alice
# Kết quả: Hello, alice!
```

### Bước 5: Định nghĩa Prompt (tùy chọn)
Nếu muốn tạo prompt tự động:
```python
@mcp.prompt("task_prompt")
def task_prompt(context: dict) -> str:
    return f"Bạn cần thực hiện công việc: {context['task']}"
```

### Tóm tắt
1. Cài đặt MCP SDK.
2. Viết server với `@mcp.tool()` và `@mcp.resource()`.
3. Kết nối nguồn dữ liệu (ví dụ SQLite) qua tool.
4. Khởi chạy server và thử nghiệm.
5. (Tùy chọn) Thêm prompt để hướng dẫn LLM.

### Tham khảo
- MCP SDK documentation: https://huggingface.co/learn/mcp-course/unit1/sdk
- Official Python SDK repo: https://github.com/modelcontextprotocol/python-sdk

## Tổng kết và tương lai của MCP

![Tổng kết và tương lai của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Cloud_computing.svg/330px-Cloud_computing.svg.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Tổng kết
MCP đã chứng minh khả năng làm cầu nối giữa các mô hình AI và các nguồn dữ liệu, công cụ, và tài nguyên khác nhau. Bằng cách chuẩn hoá giao tiếp qua các **tool**, **resource** và **prompt**, MCP giúp các kỹ sư AI giảm thiểu công việc cấu hình, tăng tính tái sử dụng và mở rộng quy mô hệ thống.

### Tương lai của MCP
1. **Mở rộng chuẩn giao tiếp** – MCP đang được cộng đồng đề xuất thêm các **metadata schema** cho dữ liệu, hỗ trợ tự động hoá việc kiểm tra tính hợp lệ và bảo mật.
2. **Tích hợp sâu với nền tảng AI** – Các nhà cung cấp mô hình lớn như OpenAI, Anthropic, và Microsoft đã bắt đầu hỗ trợ MCP trong API của mình, cho phép mô hình gọi trực tiếp các tool mà không cần chuyển đổi sang JSON thủ công.
3. **Hỗ trợ đa ngôn ngữ** – MCP đã mở rộng cú pháp annotation sang nhiều ngôn ngữ lập trình (Java, Go, Rust), giúp đội ngũ phát triển đa nền tảng dễ dàng triển khai.
4. **Công cụ phát triển** – Các IDE extensions và CLI mới sẽ cung cấp auto‑completion, linting và debugging cho MCP, làm giảm rủi ro khi triển khai.
5. **Mô hình mở rộng** – MCP có thể được dùng như một **middleware** cho các hệ thống lớn, cho phép mô hình AI thực thi logic nghiệp vụ phức tạp mà không cần truy cập trực tiếp tới cơ sở dữ liệu.

### Lời khuyên cho các kỹ sư AI
- **Bắt đầu từ mô hình nhỏ**: Kiểm thử MCP với một server đơn giản, sau đó dần dần tích hợp vào pipeline CI/CD.
- **Định nghĩa rõ ràng**: Mỗi tool/resource nên có tài liệu chi tiết, bao gồm signature, mô tả, và ví dụ sử dụng.
- **Kiểm tra bảo mật**: Sử dụng các cơ chế xác thực (OAuth, API key) trong MCP để ngăn chặn truy cập trái phép.
- **Theo dõi hiệu suất**: Đo latency và throughput của các tool, điều chỉnh caching hoặc parallelism khi cần.
- **Cộng đồng và đóng góp**: Tham gia các diễn đàn MCP, đóng góp vào repo mã nguồn mở để nhận được phản hồi và cải tiến.

Như vậy, MCP đang dần trở thành tiêu chuẩn công nghiệp cho việc kết nối mô hình AI với thế giới thực. Việc nắm vững và áp dụng MCP sẽ giúp các kỹ sư AI xây dựng các hệ thống linh hoạt, bảo mật và dễ bảo trì hơn trong tương lai.
## Nguồn ảnh

- [Tổng quan và định nghĩa về MCP](https://commons.wikimedia.org/w/index.php?curid=148266300) — Anselm Vollprecht (cite source: „Und jetzt zus@mmen. Dein Einstieg ins Echtzeit-Musizieren über das Internet“ von Anselm Vollprecht), CC BY-SA 4.0
- [Cấu trúc kỹ thuật của MCP](https://commons.wikimedia.org/w/index.php?curid=148266300) — Anselm Vollprecht (cite source: „Und jetzt zus@mmen. Dein Einstieg ins Echtzeit-Musizieren über das Internet“ von Anselm Vollprecht), CC BY-SA 4.0
- [Lợi ích và ứng dụng thực tế của MCP đối với AI Engineer](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Hướng dẫn triển khai cơ bản](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Tổng kết và tương lai của MCP](https://commons.wikimedia.org/w/index.php?curid=6080417) — Sam Johnston, CC BY-SA 3.0
