"""
Cấu hình tập trung cho tất cả LLM models dùng trong project.

Mỗi "role" (vai trò node) map tới 1 model cụ thể. Muốn đổi model cho
1 node nào đó, chỉ cần sửa ở đây, không cần đụng vào code của agent.

Cách dùng:

    from agents.models import get_llm

    llm = get_llm("planner")       # -> ChatGoogleGenerativeAI (gemini-3.1-flash-lite)
    llm = get_llm("worker")        # -> ChatGroq (openai/gpt-oss-20b)
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


@dataclass
class ModelConfig:
    """Cấu hình cho 1 model cụ thể."""

    provider: str  # "groq" | "gemini"
    model_name: str
    temperature: float = 0.3
    max_tokens: int | None = None

    # Chỉ áp dụng cho các model GPT-OSS trên Groq (worker, research_worker,
    # fallback). "low" giúp model dành ít token hơn cho việc "suy nghĩ",
    # tránh trường hợp reasoning ngốn hết token budget khiến content
    # trả về bị RỖNG (đặc biệt với các task có prompt dài, ví dụ task có
    # nhiều dependency_context). None = không set (model tự quyết định).
    reasoning_effort: str | None = None


# ============================================================
# BẢNG CẤU HÌNH MODEL THEO TỪNG ROLE (theo bảng bạn đã chốt)
# ============================================================

MODEL_REGISTRY: dict[str, ModelConfig] = {
    "input_guardrails": ModelConfig(
        provider="groq",
        model_name="meta-llama/llama-prompt-guard-2-86m",
        temperature=0.0,
    ),
    "supervisor": ModelConfig(
        provider="gemini",
        model_name="gemini-3.1-flash-lite",
        temperature=0.2,
    ),
    "planner": ModelConfig(
        provider="gemini",
        model_name="gemini-3.1-flash-lite",
        temperature=0.4,
    ),
    "worker": ModelConfig(
        provider="groq",
        model_name="openai/gpt-oss-20b",
        temperature=0.5,
        max_tokens=2048,
        reasoning_effort="low",
    ),
    "research_worker": ModelConfig(
        provider="groq",
        model_name="openai/gpt-oss-20b",
        temperature=0.5,
        max_tokens=2048,
        reasoning_effort="low",
    ),
    "synthesizer": ModelConfig(
        provider="gemini",
        model_name="gemini-3.5-flash-lite",
        temperature=0.5,
    ),
    "evaluator": ModelConfig(
        provider="gemini",
        model_name="gemini-3.1-flash-lite",
        temperature=0.0,
    ),
    "fallback": ModelConfig(
        provider="groq",
        model_name="openai/gpt-oss-120b",
        temperature=0.5,
        max_tokens=2048,
        reasoning_effort="low",
    ),
}


def get_model_config(role: str) -> ModelConfig:
    """Lấy config model theo role. Raise lỗi rõ ràng nếu role không tồn tại."""
    if role not in MODEL_REGISTRY:
        raise ValueError(
            f"Role '{role}' không tồn tại trong MODEL_REGISTRY. "
            f"Các role hợp lệ: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[role]


def get_llm(role: str):
    """
    Trả về instance LLM (LangChain chat model) tương ứng với role.

    Lưu ý: role "input_guardrails" dùng model classifier
    (llama-prompt-guard-2-86m), KHÔNG phải chat model sinh JSON như
    các role khác. Model này sẽ được gọi theo cách riêng ở
    input_guardrails.py (không dùng qua BaseAgent.run() thông thường).
    """
    config = get_model_config(role)

    if config.provider == "groq":
        kwargs = {
            "model": config.model_name,
            "temperature": config.temperature,
            "api_key": GROQ_API_KEY,
        }
        if config.max_tokens is not None:
            kwargs["max_tokens"] = config.max_tokens
        if config.reasoning_effort is not None:
            kwargs["reasoning_effort"] = config.reasoning_effort

        return ChatGroq(**kwargs)

    if config.provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=config.model_name,
            temperature=config.temperature,
            google_api_key=GEMINI_API_KEY,
        )

    raise ValueError(f"Provider không được hỗ trợ: {config.provider}")