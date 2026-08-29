# Khám phá Model Context Protocol (MCP): Chuẩn mực mới cho kết nối dữ liệu trong AI Engineering

Trong bối cảnh kiến trúc hệ thống LLM ngày càng phức tạp, việc kết nối các Mô hình Ngôn ngữ Lớn với các nguồn dữ liệu và công cụ bên ngoài thường đối mặt với bài toán phân mảnh ngữ cảnh và chi phí bảo trì cao. Bài viết này cung cấp góc nhìn kỹ thuật sâu sắc về Model Context Protocol (MCP) – một định chuẩn mở giúp tối ưu hóa quy trình tích hợp và trao đổi ngữ cảnh cho các AI Engineer.

## Tổng quan về Model Context Protocol (MCP)

Model Context Protocol (MCP) là một **định chuẩn mở** do Anthropic giới thiệu vào tháng 11 năm 2024. MCP được thiết kế để **đồng bộ hóa cách các mô hình ngôn ngữ lớn (LLM) truy cập và tương tác với dữ liệu, công cụ, và dịch vụ bên ngoài** mà không cần viết mã kết nối riêng cho từng nguồn. Thay vì phải xây dựng một bộ adapter tùy chỉnh cho mỗi ứng dụng AI và mỗi nguồn dữ liệu, MCP cung cấp một ngôn ngữ chung và bộ quy tắc nhất quán, giúp các ứng dụng LLM “đọc file”, “gọi hàm” và “đưa ngữ cảnh” một cách chuẩn hóa.

![Tổng quan về MCP và bối cảnh ra đời](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Lý do Anthropic ra đời MCP
- **N×M integration problem**: Khi số lượng ứng dụng AI (N) và nguồn dữ liệu/công cụ (M) tăng, việc tạo kết nối tùy chỉnh cho mỗi cặp trở nên không thể quản lý được.
- **Silo dữ liệu và hệ thống legacy**: Các nhà phát triển thường phải viết mã riêng để kết nối với từng hệ thống, dẫn tới sự lặp lại và khó bảo trì.
- **Độ tin cậy và bảo mật**: MCP định nghĩa cách bảo mật dữ liệu khi truyền giữa LLM và nguồn bên ngoài, giúp giảm rủi ro lỗi và lỗ hổng.

Anthropic đã công bố MCP với mục tiêu **đơn giản hóa và chuẩn hóa** quá trình tích hợp AI vào thực tiễn, và ngay sau đó các nhà cung cấp AI lớn như OpenAI và Google DeepMind đã bắt đầu chấp nhận và triển khai chuẩn này.

### Vấn đề 'context fragmentation' MCP giải quyết
Trong các hệ thống LLM, ngữ cảnh (context) thường bị giới hạn bởi kích thước cửa sổ token. Khi một ứng dụng cần truy cập nhiều nguồn dữ liệu khác nhau, ngữ cảnh có thể bị **tách rời** (fragmented) và mất tính liên tục, dẫn tới:
- **Context rot**: Thông tin lỗi thời vẫn tồn tại trong bộ nhớ.
- **Context overflow**: Quá nhiều thông tin làm giảm khả năng chú ý tới các phần quan trọng.
- **Semantic noise**: Nội dung không liên quan làm nhiễu độ chính xác.

MCP giải quyết vấn đề này bằng cách **định nghĩa một giao diện chuẩn** để LLM lấy dữ liệu một cách **định hướng ngữ cảnh**. Thay vì gửi toàn bộ dữ liệu vào cửa sổ prompt, LLM chỉ cần yêu cầu dữ liệu cần thiết thông qua MCP, giúp giảm tải ngữ cảnh và tránh hiện tượng fragment hóa.

> *Theo nguồn Medium* “MCP is an open standard designed to facilitate seamless integration between LLM applications and external data sources and tools” (https://medium.com/@amanatulla1606/anthropics-model-context-protocol-mcp-a-deep-dive-for-developers-1d3db39c9fdc).

## Kiến trúc kỹ thuật của MCP

MCP được thiết kế theo mô hình **client‑host‑server** truyền thống, nhưng được điều chỉnh để phục vụ cho việc trao đổi ngữ cảnh giữa LLM và các nguồn dữ liệu bên ngoài. Mô hình này chia trách nhiệm thành ba thành phần chính:

![Kiến trúc kỹ thuật của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/802.11_Network_Architecture.svg/330px-802.11_Network_Architecture.svg.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

1. **Host** – Ứng dụng AI mà người dùng tương tác (ví dụ Claude Desktop, IDE, hoặc extension trình duyệt). Host chịu trách nhiệm quản lý toàn bộ vòng đời cuộc gọi, bao gồm việc tạo và duy trì các **client**.
2. **Client** – Thành phần trong Host chịu trách nhiệm duy trì kết nối tới một **server** cụ thể. Mỗi Client tương ứng với một MCP server và giữ một kênh giao tiếp độc lập, thường là qua STDIO (đối với server cục bộ) hoặc HTTP streamable (đối với server từ xa). Client nhận dữ liệu ngữ cảnh từ server và chuyển tiếp cho LLM hoặc hiển thị cho người dùng.
3. **Server** – Dịch vụ hoặc chương trình bên ngoài cung cấp ngữ cảnh, dữ liệu, hoặc chức năng công cụ. Server phát hành các *capability* (tính năng) và *schema* (định dạng dữ liệu) theo chuẩn JSON‑RPC 2.0, cho phép Client thực hiện các yêu cầu một cách có cấu trúc.

### Giao tiếp giữa các thành phần

- **Discovery**: Khi Host khởi động, Client gửi yêu cầu discovery tới Server để lấy danh sách các công cụ và dữ liệu có sẵn. Server trả về một tài liệu JSON chứa mô tả chi tiết về các *capabilities*.
- **Invocation**: LLM, thông qua Host, gửi yêu cầu gọi công cụ (tool call) dưới dạng JSON payload. Client chuyển tiếp yêu cầu tới Server, nhận phản hồi dạng JSON và gửi lại cho Host.
- **Result Integration**: Host nhận kết quả và tích hợp vào ngữ cảnh của LLM, hoặc hiển thị trực tiếp cho người dùng. Nhờ cách này, LLM không cần lưu trữ toàn bộ dữ liệu trong cửa sổ prompt, giảm thiểu *context fragmentation*.

### Lợi ích của kiến trúc này
- **Modularity**: Một Host có thể kết nối với nhiều Server đồng thời, mỗi Client độc lập. Khi cần thêm một nguồn dữ liệu mới, chỉ cần triển khai Server mới mà không thay đổi Host.
- **Security & Isolation**: Mỗi Client giữ một kênh riêng, giúp cô lập truy cập và giảm rủi ro lộ dữ liệu. MCP định nghĩa cách bảo mật dữ liệu khi truyền qua JSON‑RPC, giúp giảm lỗi và lỗ hổng.
- **Scalability**: Server có thể được triển khai trong môi trường phân tán, hỗ trợ tải cao và độ trễ thấp nhờ giao thức HTTP streamable.

### Sơ đồ logic

```text
[Host] ──► [Client 1] ──► [Server A]
   │                │
   └──► [Client 2] ──► [Server B]
```

Trong sơ đồ, Host tạo hai Client để kết nối tới Server A và Server B. Khi LLM yêu cầu truy cập dữ liệu từ Server A, Client 1 thực hiện giao tiếp, nhận dữ liệu và trả về cho Host, rồi Host đưa vào ngữ cảnh LLM.

### Tham khảo
- Architecture overview (https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)
- Architectural Components of MCP · Hugging Face (https://huggingface.co/learn/mcp-course/en/unit1/architectural-components)
- What Is the Model Context Protocol (MCP) and How It Works (https://www.descope.com/learn/post/mcp)

Như vậy, kiến trúc client‑host‑server của MCP cung cấp một khung chuẩn hóa, an toàn và mở rộng, giúp LLM truy cập dữ liệu và công cụ một cách có cấu trúc, đồng thời giải quyết vấn đề *context fragmentation* mà các hệ thống LLM truyền thống gặp phải.

## Lợi ích kỹ thuật và ứng dụng thực tế cho AI Engineer

![Lợi ích và ứng dụng thực tế cho AI Engineer](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Lợi ích kỹ thuật của MCP
- **Giảm boilerplate**: MCP định nghĩa một giao diện chuẩn JSON‑RPC, giúp các engineer viết một lần khai báo *capability* và *schema* cho một tool, sau đó mọi LLM có thể gọi tool đó qua một client duy nhất. Điều này loại bỏ việc phải viết mã wrapper riêng cho từng API, giảm đáng kể số dòng code và thời gian triển khai.
- **Tăng khả năng tương tác giữa tool và dữ liệu**: Nhờ mô hình client‑host‑server, LLM có thể truy cập dữ liệu thời gian thực từ các nguồn như cơ sở dữ liệu, dịch vụ SaaS, hoặc các hệ thống nội bộ mà không cần phải tái lập chỉ mục hay lưu trữ toàn bộ dữ liệu trong prompt. Điều này giúp tránh *context fragmentation* và cho phép mô hình trả lời dựa trên dữ liệu mới nhất.
- **Modularity & extensibility**: Khi một công cụ mới được triển khai dưới dạng MCP server, chỉ cần cập nhật *capability* trong server và đăng ký client. Host và LLM không cần thay đổi; tính năng mới có thể được sử dụng ngay lập tức.
- **Security & governance**: MCP hỗ trợ truyền dữ liệu qua JSON‑RPC với khả năng mã hóa và kiểm soát truy cập, giúp tuân thủ các chính sách bảo mật trong môi trường doanh nghiệp.
- **Scalability**: Server có thể được triển khai trong môi trường phân tán, hỗ trợ tải cao và giảm độ trễ nhờ HTTP streamable.

### Ví dụ ứng dụng thực tế
| Mô hình | Công cụ | Mô tả |
|---------|---------|-------|
| **AI‑Driven Reporting** | MCP server kết nối tới data warehouse | LLM truy vấn dữ liệu bán hàng theo thời gian thực, tự động tạo báo cáo tài chính. Công cụ trả về dữ liệu dạng JSON, LLM tổng hợp và xuất ra PDF. |
| **Intelligent Process Automation** | MCP server giao tiếp với hệ thống ERP | Khi LLM nhận yêu cầu đặt hàng, nó gọi tool *CreateOrder* qua MCP, hệ thống ERP thực thi và trả về mã đơn. LLM cập nhật giao diện người dùng ngay lập tức. |
| **Real‑Time Decision Support** | MCP server truy cập API dự báo thời tiết | Ứng dụng AI hỗ trợ quản lý kho: LLM lấy dữ liệu thời tiết, dự báo nhu cầu, tự động điều chỉnh mức tồn kho. |
| **Multi‑Agent Orchestration** | Nhiều MCP server (CRM, ticketing, BI) | Một agent tổng hợp thông tin từ nhiều nguồn, trả về bản tóm tắt tình trạng dịch vụ cho quản lý. |

Những ví dụ trên minh họa cách MCP cho phép AI Engineer nhanh chóng tích hợp các nguồn dữ liệu và công cụ, giảm thiểu công việc lập trình thủ công và tăng tính linh hoạt trong phát triển ứng dụng AI.

## Hướng dẫn bắt đầu với MCP

![Hướng dẫn bắt đầu với MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Cloud-elements-logo_standard.png/330px-Cloud-elements-logo_standard.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

### Bước 1: Chuẩn bị môi trường
- Cài đặt Node.js 20+ và npm.
- Khởi tạo project mới:
```bash
mkdir mcp-demo && cd mcp-demo
npm init -y
```
- Cài đặt SDK MCP chính thức:
```bash
npm i @modelcontextprotocol/sdk
```

### Bước 2: Tạo server MCP
Tạo file `server.ts` sử dụng chuẩn Model Context Protocol SDK:
```ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server(
  {
    name: "mcp-demo-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "echo",
      description: "Trả về chuỗi đã nhập",
      inputSchema: {
        type: "object",
        properties: {
          message: { type: "string" },
        },
        required: ["message"],
      },
    },
  ],
}));

const transport = new StdioServerTransport();
await server.connect(transport);
```

### Bước 3: Kiểm thử và tích hợp
Sau khi cấu hình server và client qua SDK chính thức, bạn có thể kiểm thử trực tiếp thông qua các AI Host hỗ trợ MCP như Claude Desktop bằng cách khai báo file cấu hình cục bộ (`claude_desktop_config.json`).

---

**Lưu ý**: Các ví dụ trên dựa trên tài liệu chính thức của Model Context Protocol SDK.

## Tổng kết và tương lai của MCP

![Tổng kết và tương lai của MCP](https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Cloud_computing.svg/330px-Cloud_computing.svg.png?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail)

Model Context Protocol đã chứng minh khả năng chuẩn hóa giao tiếp giữa LLM và các dịch vụ backend thông qua mô hình ngữ cảnh đồng nhất. Việc tích hợp MCP vào pipelines CI/CD, monitoring, và versioning giúp giảm thiểu lỗi serialisation và tăng tính tái sử dụng của các tool. Trong tương lai, MCP có thể trở thành chuẩn công nghiệp khi các nhà cung cấp LLM lớn mở rộng hỗ trợ API chuẩn này. Hãy bắt đầu áp dụng MCP ngay hôm nay để tối ưu hóa kiến trúc tích hợp hệ thống LLM của bạn.
## Nguồn ảnh

- [Tổng quan về MCP và bối cảnh ra đời](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Kiến trúc kỹ thuật của MCP](https://commons.wikimedia.org/w/index.php?curid=168502265) — Superspritz, CC BY-SA 4.0
- [Lợi ích và ứng dụng thực tế cho AI Engineer](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Hướng dẫn bắt đầu với MCP](https://commons.wikimedia.org/w/index.php?curid=100089880) — Cloud elements, CC BY-SA 4.0
- [Tổng kết và tương lai của MCP](https://commons.wikimedia.org/w/index.php?curid=6080417) — Sam Johnston, CC BY-SA 3.0
