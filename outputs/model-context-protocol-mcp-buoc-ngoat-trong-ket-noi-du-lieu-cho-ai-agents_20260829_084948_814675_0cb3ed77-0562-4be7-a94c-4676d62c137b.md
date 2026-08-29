# Model Context Protocol (MCP): Bước ngoặt trong kết nối dữ liệu cho AI Agents

Trong kỷ nguyên phát triển mạnh mẽ của các hệ thống AI, việc kết nối các mô hình ngôn ngữ lớn (LLMs) với nguồn dữ liệu và công cụ bên ngoài luôn là một thách thức kỹ thuật lớn đối với các AI Engineer. Việc thiếu vắng một tiêu chuẩn chung khiến các nhà phát triển phải liên tục xây dựng các giải pháp tích hợp tùy chỉnh, dẫn đến sự phân mảnh và khó mở rộng. Bài viết này sẽ phân tích chi tiết về Model Context Protocol (MCP) – chuẩn mở giải quyết triệt để bài toán này.

## Tổng quan về Model Context Protocol (MCP)
Model Context Protocol (MCP) là một chuẩn mở do Anthropic giới thiệu vào tháng 11 năm 2024. MCP được thiết kế để **đồng bộ hóa** cách các hệ thống AI, đặc biệt là các mô hình ngôn ngữ lớn (LLMs), truy cập và tương tác với các nguồn dữ liệu và công cụ bên ngoài. Trước MCP, mỗi ứng dụng AI thường phải xây dựng các kết nối tùy chỉnh với từng nguồn dữ liệu, dẫn đến vấn đề *N×M integration problem* khi số lượng ứng dụng (N) và nguồn dữ liệu (M) tăng lên.

![Tổng quan về MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Mục tiêu chính
- **Chuẩn hoá giao tiếp** giữa LLM và các hệ thống dữ liệu (tệp, API, cơ sở dữ liệu, công cụ quản lý doanh nghiệp, môi trường phát triển, v.v.).
- **Giảm fragmentation**: thay vì học cách giao tiếp với từng dịch vụ riêng biệt, MCP cung cấp một ngôn ngữ và giao diện chung.
- **Tăng tính mở rộng**: các nhà phát triển có thể thêm các server mới mà không cần thay đổi host hiện có.

### Bối cảnh ra đời
Anthropic nhận thấy thách thức lớn trong việc kết nối AI với thế giới thực: các dữ liệu luôn thay đổi và các công cụ đa dạng. MCP được phát triển bởi các kỹ sư David Soria Parra và Justin Spahr‑Summers tại Anthropic để giải quyết vấn đề này, và đã nhanh chóng được các nhà cung cấp AI lớn như OpenAI và Google DeepMind chấp nhận.

Như vậy, MCP không chỉ là một giao thức mà còn là một nền tảng giúp AI trở thành một *đồng hành thực thụ* với các hệ thống doanh nghiệp, thay vì chỉ dựa vào kiến thức tĩnh trong mô hình.

## Kiến trúc Client‑Host‑Server của MCP
Tiếp nối nền tảng tổng quan, để hiểu rõ cách MCP vận hành trong thực tế, chúng ta cần xem xét kỹ lưỡng kiến trúc kỹ thuật của nó. MCP được thiết kế theo mô hình **client‑server** với một lớp **host** trung gian để điều phối giao tiếp. Các thành phần chính và vai trò của chúng được mô tả như sau:

![Kiến trúc kỹ thuật của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/802.11_Network_Architecture.svg/330px-802.11_Network_Architecture.svg.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

| Thành phần | Vai trò | Giao tiếp chính |
|------------|---------|-----------------|
| **Host** | Ứng dụng AI (ví dụ Claude Desktop, IDE, extension) mà người dùng tương tác | Tạo và quản lý một hoặc nhiều *client* để kết nối tới *server* |
| **Client** | Phần phụ trợ của host, thực hiện giao thức MCP (JSON‑RPC 2.0) | Gửi yêu cầu và nhận phản hồi qua *transport layer* tới *server* |
| **Server** | Dịch vụ cung cấp khả năng truy cập dữ liệu hoặc công cụ (cơ sở dữ liệu, API, file system,…) | Thực thi hành động và trả kết quả cho *client* |

### Luồng dữ liệu chi tiết
1. **Khởi tạo kết nối** – Host khởi tạo một *client* cho mỗi *server* cần truy cập. Client mở một kênh giao tiếp (STDIO cho server cục bộ, Streamable HTTP cho server từ xa).<br>
2. **Handshake** – Khi client kết nối, server gửi thông tin phiên bản và danh sách *capabilities* (định nghĩa các phương thức có sẵn). Client lưu trữ danh sách này để quyết định hành động phù hợp. Tham khảo: WorkOS blog.
3. **Giao tiếp yêu cầu‑phản hồi** – Client gửi yêu cầu JSON‑RPC (ví dụ `create_issue`, `prompts/list`) tới server. Server thực thi và trả về kết quả dưới dạng JSON‑RPC response. Nếu không cần trả về, server có thể gửi *notification*.
4. **Quản lý ngữ cảnh** – MCP định nghĩa một *data layer* chứa các *primitives* (định dạng dữ liệu, schema). Các dữ liệu này được chia sẻ giữa server và client, giúp LLM hiểu ngữ cảnh thực tế.
5. **Bảo mật và kiểm soát** – Mỗi kết nối được bảo vệ bởi cơ chế xác thực (token, chứng chỉ) và server có thể giới hạn quyền truy cập dựa trên *capabilities* đã thông báo.

### Đặc điểm kỹ thuật
- **JSON‑RPC 2.0** là giao thức RPC cơ bản, đảm bảo tính nhất quán trong định dạng request/response.
- **Transport Layer** có thể là STDIO (đối với server cục bộ) hoặc HTTP streaming (đối với server từ xa), cho phép mở rộng linh hoạt.
- **Capability Negotiation** giúp client biết trước các phương thức có sẵn, tránh lỗi “method not found” và tối ưu hoá luồng công việc.

Nhờ kiến trúc này, MCP cho phép các AI Engineer triển khai các *server* tùy chỉnh (ví dụ truy vấn database, gọi API bên thứ ba) mà không cần viết lại logic tích hợp cho từng ứng dụng, giảm thiểu fragmentation và tăng tính mở rộng.

## Lợi ích cho AI Engineer
Từ kiến trúc nền tảng trên, MCP mang lại những giá trị cốt lõi nào cho đội ngũ phát triển hệ thống? Dưới đây là những lợi ích kỹ thuật cụ thể, kèm so sánh với phương pháp tích hợp truyền thống.

![Lợi ích cho AI Engineer](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

| Lợi ích | Mô tả | So sánh với tích hợp truyền thống |
|---------|-------|------------------------------------|
| **Quản lý ngữ cảnh tập trung** | MCP định nghĩa một *data layer* chứa các primitives (định dạng, schema) được chia sẻ giữa client và server. Điều này giúp LLM hiểu ngữ cảnh thực tế một cách nhất quán, tránh lỗi “context fragmentation”. | Truyền thống thường lưu trữ ngữ cảnh trong bộ nhớ của từng mô hình, dẫn đến mất đồng bộ khi mở rộng hoặc di chuyển giữa các môi trường. |
| **Capability Negotiation** | Khi client kết nối, server gửi danh sách capabilities. Client biết trước các phương thức có sẵn, tránh lỗi “method not found” và tối ưu luồng công việc. | Trong các giải pháp cũ, các phương thức được hard‑code hoặc dựa trên cấu hình động, gây khó khăn trong việc kiểm tra và bảo trì. |
| **Transport Layer linh hoạt** | MCP hỗ trợ STDIO cho server cục bộ và HTTP streaming cho server từ xa. Điều này cho phép triển khai nhanh chóng trên nhiều nền tảng mà không cần thay đổi giao thức. | Phương pháp truyền thống thường yêu cầu viết adapter riêng cho từng giao thức, làm tăng độ phức tạp. |
| **Tích hợp công cụ một cách modular** | Các *server* có thể được triển khai như các micro‑service (ví dụ truy vấn database, gọi API bên thứ ba) mà không cần viết lại logic tích hợp cho từng ứng dụng. | Truyền thống thường đòi hỏi viết wrapper riêng cho từng công cụ, dẫn đến fragmentation. |
| **Bảo mật và kiểm soát truy cập** | Mỗi kết nối được bảo vệ bởi token hoặc chứng chỉ, và server có thể giới hạn quyền truy cập dựa trên capabilities. | Các giải pháp cũ thường không có cơ chế phân quyền rõ ràng, dễ dẫn đến lỗ hổng bảo mật. |

### Tóm tắt
MCP giúp AI Engineer giảm thiểu fragmentation ngữ cảnh, tăng tính mở rộng và bảo mật, đồng thời đơn giản hóa việc tích hợp công cụ. Thay vì phải viết lại logic cho từng ứng dụng, engineer chỉ cần triển khai server phù hợp và khai báo capabilities. Điều này không chỉ tiết kiệm thời gian phát triển mà còn nâng cao độ tin cậy và khả năng bảo trì của hệ thống.

## Ví dụ triển khai và kết luận
Để minh chứng tính khả thi trong thực tế, chúng ta cùng xem xét ví dụ triển khai MCP server truy cập cơ sở dữ liệu PostgreSQL để trả về dữ liệu bảng `orders`.

![Ví dụ triển khai và kết luận](https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Client-Server.png/330px-Client-Server.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

Server sẽ khai báo một method `db.query` và sử dụng JSON‑RPC 2.0 qua HTTP streaming. Dưới đây là một snippet Python đơn giản sử dụng thư viện `httpx` và `pydantic` để triển khai:

```python
import json
import httpx
from pydantic import BaseModel

class QueryRequest(BaseModel):
    sql: str
    params: list | None = None

class QueryResponse(BaseModel):
    rows: list[dict]

# MCP server endpoint
URL = "https://mcp.example.com/v1"

# Đăng ký capability
capabilities = {
    "name": "postgresql",
    "methods": ["db.query"],
    "schema": {
        "db.query": {
            "request": QueryRequest.schema(),
            "response": QueryResponse.schema(),
        }
    },
}

# Gửi request capability discovery
httpx.post(f"{URL}/capabilities", json=capabilities)

# Gọi method
payload = {
    "jsonrpc": "2.0",
    "method": "db.query",
    "params": {"sql": "SELECT * FROM orders WHERE status = $1", "params": ["shipped"]},
    "id": 1,
}
resp = httpx.post(f"{URL}/rpc", json=payload, stream=True)
for line in resp.iter_lines():
    if line:
        data = json.loads(line)
        print("Result:", data["result"]["rows"])  # rows là danh sách dict
```

Trong ví dụ trên:
1. Server khai báo capability `db.query` với schema Pydantic.
2. Client gửi request JSON‑RPC và nhận kết quả streaming.
3. MCP đảm bảo giao thức chuẩn, cho phép thay đổi backend (ví dụ chuyển sang MySQL) mà không cần sửa client.

## Kết luận
MCP đã chứng minh tính **độ mở rộng** và **độ bảo mật** khi kết nối tới các nguồn dữ liệu phức tạp như PostgreSQL. Nhờ khả năng khai báo capabilities và giao tiếp qua JSON‑RPC, các AI Engineer có thể:
- **Tích hợp nhanh** các dịch vụ dữ liệu mà không cần viết wrapper riêng.
- **Đảm bảo an toàn** bằng token và quyền truy cập được định nghĩa trong capability.
- **Tối ưu hoá luồng công việc** bằng streaming, giảm độ trễ khi xử lý dữ liệu lớn.

Trong tương lai, MCP sẽ tiếp tục mở rộng với các server chuẩn cho các dịch vụ lớn như Google Drive, Slack, GitHub, và PostgreSQL, tạo nên một **hệ sinh thái** nơi các AI Agent có thể tương tác với thế giới thực một cách mượt mà và an toàn. Điều này đặt MCP vào vị trí chuẩn mực cho việc xây dựng AI Agent hiện đại và dễ bảo trì.
## Nguồn ảnh

- [Tổng quan về MCP](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Kiến trúc kỹ thuật của MCP](https://commons.wikimedia.org/w/index.php?curid=168502265) — Superspritz, CC BY-SA 4.0
- [Lợi ích cho AI Engineer](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Ví dụ triển khai và kết luận](https://commons.wikimedia.org/w/index.php?curid=148266300) — Anselm Vollprecht (cite source: „Und jetzt zus@mmen. Dein Einstieg ins Echtzeit-Musizieren über das Internet“ von Anselm Vollprecht), CC BY-SA 4.0
